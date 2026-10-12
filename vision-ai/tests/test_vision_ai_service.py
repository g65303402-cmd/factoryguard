"""
단위 테스트 - OPENAI_API_KEY 없이도 전체 로직을 검증할 수 있도록
Vision LLM 호출 부분은 목(mock)으로 대체한다.

실행: pytest tests/ -v
"""

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.danger_zone_detector import DangerZone, DangerZoneDetector
from app.core.yolo_detector import PersonDetection
from app.core.event_store import EventStore
from app.core.zone_config import load_zones
from app.core.report_generator import ReportGenerator, map_event_to_rag_request, RISK_TYPE_MAP
from app.core.report_store import ReportStore
from app.models.event import DetectionEvent, EventType, EventSeverity


@pytest.fixture
def tmp_event_store(tmp_path):
    return EventStore(storage_path=str(tmp_path / "events.jsonl"))


def test_event_to_dict_serializable():
    """DetectionEvent가 JSON 직렬화 가능한 dict로 잘 변환되는지"""
    event = DetectionEvent(event_type=EventType.DANGER_ZONE, severity=EventSeverity.HIGH)
    d = event.to_dict()
    assert d["event_type"] == "danger_zone"
    assert d["severity"] == "high"
    assert "timestamp" in d and "event_id" in d


def test_event_store_add_and_get_history(tmp_event_store):
    e1 = DetectionEvent(event_type=EventType.DANGER_ZONE)
    e2 = DetectionEvent(event_type=EventType.WORKER_APPROACH)
    tmp_event_store.add(e1)
    tmp_event_store.add(e2)

    history = tmp_event_store.get_history()
    assert len(history) == 2

    filtered = tmp_event_store.get_history(event_type=EventType.DANGER_ZONE)
    assert len(filtered) == 1
    assert filtered[0]["event_type"] == "danger_zone"


def test_event_store_stats(tmp_event_store):
    for _ in range(3):
        tmp_event_store.add(DetectionEvent(event_type=EventType.DANGER_ZONE, severity=EventSeverity.HIGH))
    stats = tmp_event_store.get_stats()
    assert stats["total_events"] == 3
    assert stats["by_type"]["danger_zone"] == 3
    assert stats["by_severity"]["high"] == 3


def _mock_person_detector(detections_per_call):
    """
    호출할 때마다 detections_per_call 리스트를 순서대로 반환하는 가짜 PersonDetector.
    실제 YOLO 모델(가중치 파일) 없이도 위험구역 겹침 판단 로직만 검증하기 위한 목(mock)이다.
    """
    mock = MagicMock()
    mock.detect.side_effect = detections_per_call
    return mock


def test_danger_zone_detector_no_detection_when_no_person():
    """YOLO가 사람을 하나도 못 찾으면, 위험구역 접근도 당연히 감지되지 않아야 한다"""
    zone = DangerZone(name="test_zone", polygon=[(10, 10), (100, 10), (100, 100), (10, 100)])
    mock_detector = _mock_person_detector([[]])  # 사람 탐지 결과 없음
    detector = DangerZoneDetector([zone], person_detector=mock_detector)

    frame = np.full((200, 200, 3), 50, dtype=np.uint8)
    results = detector.detect(frame)
    assert results == []


def test_danger_zone_detector_detects_person_overlapping_zone():
    """YOLO가 찾은 사람의 bbox가 위험구역과 충분히 겹치면 감지되어야 한다"""
    zone = DangerZone(name="test_zone", polygon=[(10, 10), (100, 10), (100, 100), (10, 100)])
    # 사람 bbox (20,20,60,60) → 대부분 구역(10,10)-(100,100) 안에 들어감
    person = PersonDetection(bbox=(20, 20, 60, 60), confidence=0.85)
    mock_detector = _mock_person_detector([[person]])
    detector = DangerZoneDetector([zone], overlap_threshold=0.5, person_detector=mock_detector)

    frame = np.full((200, 200, 3), 50, dtype=np.uint8)
    results = detector.detect(frame)

    assert len(results) == 1
    assert results[0]["zone_name"] == "test_zone"
    assert results[0]["overlap_ratio"] > 0.5
    assert results[0]["person_confidence"] == 0.85


def test_danger_zone_detector_ignores_person_outside_zone():
    """사람이 위험구역과 전혀 겹치지 않는 위치에 있으면 감지되지 않아야 한다"""
    zone = DangerZone(name="test_zone", polygon=[(10, 10), (100, 10), (100, 100), (10, 100)])
    # 구역(10~100, 10~100)과 전혀 안 겹치는 위치
    person = PersonDetection(bbox=(150, 150, 30, 30), confidence=0.9)
    mock_detector = _mock_person_detector([[person]])
    detector = DangerZoneDetector([zone], person_detector=mock_detector)

    frame = np.full((200, 200, 3), 50, dtype=np.uint8)
    results = detector.detect(frame)
    assert results == []


def test_danger_zone_detector_keeps_detecting_stationary_person():
    """
    회귀 확인: 사람이 위험구역에 '가만히 멈춰있어도' 계속 감지되어야 한다.

    배경: 이전 버전(OpenCV 배경차분)은 정지한 물체를 배경으로 흡수해버려서
    사람이 끼여서 움직이지 못하는 가장 위험한 순간에 감지가 끊기는 결함이 있었다.
    YOLO는 매 프레임을 독립적으로 판단하므로(배경 학습 개념 자체가 없음),
    이 문제가 애초에 구조적으로 발생하지 않는다는 걸 확인한다.
    """
    zone = DangerZone(name="test_zone", polygon=[(10, 10), (100, 10), (100, 100), (10, 100)])
    same_person = PersonDetection(bbox=(20, 20, 60, 60), confidence=0.85)
    # 80프레임 내내 '같은 위치에 가만히 있는' 동일한 탐지 결과를 반환하도록 목 설정
    mock_detector = _mock_person_detector([[same_person] for _ in range(80)])
    detector = DangerZoneDetector([zone], overlap_threshold=0.5, person_detector=mock_detector)

    frame = np.full((200, 200, 3), 50, dtype=np.uint8)
    detection_flags = [len(detector.detect(frame)) > 0 for _ in range(80)]

    assert all(detection_flags), (
        "정지한 사람이 중간에 감지되지 않는 프레임이 있습니다 "
        f"(끊긴 위치: {[i for i, f in enumerate(detection_flags) if not f]})."
    )


@patch("app.core.vision_llm.OpenAI")
def test_vision_llm_analyzer_mocked(mock_openai_cls):
    """OpenAI API를 실제로 호출하지 않고, 인터페이스가 맞는지만 검증"""
    from app.core.vision_llm import VisionLLMAnalyzer

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "테스트 분석 결과: 작업자 1명 확인, 위험도 중간"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    analyzer = VisionLLMAnalyzer(api_key="dummy-key-for-test")
    frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    result = analyzer.analyze(frame, context="테스트 컨텍스트")

    assert "테스트 분석 결과" in result
    mock_client.chat.completions.create.assert_called_once()


def test_load_zones_returns_default_when_no_config_file(tmp_path):
    """설정 파일이 없으면 기본 좌표(데모 영상 기준)를 반환해야 한다"""
    nonexistent_path = str(tmp_path / "no_such_file.json")
    zones = load_zones(nonexistent_path)
    assert len(zones) == 1
    assert zones[0].name == "컨베이어_하부"


def test_load_zones_reads_zone_tool_format(tmp_path):
    """위험구역 담당자의 위험구역 도구가 저장하는 형식(배열, points, is_normalized)을 정확히 읽어야 한다"""
    import json

    config_path = tmp_path / "zones_config.json"
    config = [
        {
            "zone_id": "drawn-zone-1",
            "name": "Danger-Zone-1",
            "points": [[100, 200], [300, 200], [300, 400], [100, 400]],
            "severity": "high",
            "is_normalized": False,
        },
        {
            "zone_id": "drawn-zone-2",
            "name": "Danger-Zone-2",
            "points": [[400, 100], [500, 100], [500, 200], [400, 200]],
            "severity": "medium",
            "is_normalized": False,
        },
    ]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    zones = load_zones(str(config_path))
    assert len(zones) == 2
    assert zones[0].name == "Danger-Zone-1"
    assert zones[0].polygon == [(100, 200), (300, 200), (300, 400), (100, 400)]
    assert zones[1].name == "Danger-Zone-2"


def test_load_zones_skips_normalized_zone_with_warning(tmp_path, capsys):
    """is_normalized=true인 구역은 아직 변환 로직이 없으므로 건너뛰고 경고만 출력해야 한다"""
    import json

    config_path = tmp_path / "zones_config.json"
    config = [
        {
            "zone_id": "drawn-zone-1",
            "name": "Normalized-Zone",
            "points": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.4], [0.1, 0.4]],
            "severity": "high",
            "is_normalized": True,
        }
    ]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    zones = load_zones(str(config_path))
    assert len(zones) == 0

    captured = capsys.readouterr()
    assert "정규화 좌표 변환이 아직 구현" in captured.out


@pytest.fixture
def tmp_report_store(tmp_path):
    return ReportStore(storage_path=str(tmp_path / "reports.jsonl"))


def test_map_event_to_rag_request_fields():
    """DetectionEvent가 RAG 담당자 RAG API가 기대하는 형식으로 정확히 변환되어야 한다"""
    event = DetectionEvent(
        event_type=EventType.DANGER_ZONE,
        zone_name="컨베이어_하부",
        confidence=0.82,
        vision_llm_description="작업자가 컨베이어 하부 접근, 위험도 높음",
    )
    payload = map_event_to_rag_request(event, top_k=3)

    assert payload["top_k"] == 3
    ev = payload["event"]
    assert ev["event_id"] == event.event_id
    assert ev["source"] == "vision"
    assert ev["risk_type"] == "끼임"          # RISK_TYPE_MAP[DANGER_ZONE]
    assert ev["object"] == "컨베이어"
    assert ev["location"] == "컨베이어_하부"
    assert ev["description"] == "작업자가 컨베이어 하부 접근, 위험도 높음"
    assert "danger_zone_entry" in ev["vision_labels"]


def test_map_event_to_rag_request_uses_fallback_description():
    """Vision LLM 분석이 아직 없는 이벤트도 description을 자동으로 채워서 보내야 한다"""
    event = DetectionEvent(event_type=EventType.DANGER_ZONE, zone_name="구역A", confidence=0.5)
    payload = map_event_to_rag_request(event)
    assert "구역A" in payload["event"]["description"]


@patch("app.core.report_generator.OpenAI")
@patch("app.core.report_generator.requests.post")
def test_report_generator_success(mock_post, mock_openai_cls, tmp_report_store):
    """RAG API와 LLM 문장화가 둘 다 성공하면, 완성된 리포트가 저장되어야 한다"""
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "llm_context": "산업안전보건기준규칙 제88조: 동력차단장치는 접근 가능한 위치에...",
            "legal_basis": [{"source": "산업안전보건기준규칙 제88조", "page": 1}],
        },
    )
    mock_post.return_value.raise_for_status = lambda: None

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "작업자가 컨베이어 하부에 접근했다. 위험도는 높음이며..."
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_cls.return_value = mock_client

    generator = ReportGenerator(report_store=tmp_report_store, openai_api_key="dummy-key")
    event = DetectionEvent(event_type=EventType.DANGER_ZONE, zone_name="컨베이어_하부", confidence=0.8)

    report = generator.generate(event)

    assert report.generation_failed is False
    assert "컨베이어 하부" in report.report_text
    assert len(report.rag_sources) == 1
    assert tmp_report_store.get_by_event_id(event.event_id) is not None


@patch("app.core.report_generator.OpenAI")
@patch("app.core.report_generator.requests.post")
def test_report_generator_handles_rag_api_down(mock_post, mock_openai_cls, tmp_report_store):
    """
    RAG API 서버가 꺼져있거나 응답이 없어도 예외를 던지지 않고,
    generation_failed=True인 리포트를 반환해야 한다 (감지 흐름을 막으면 안 되므로).
    """
    import requests as real_requests
    mock_post.side_effect = real_requests.exceptions.ConnectionError("연결 거부")
    mock_openai_cls.return_value = MagicMock()

    generator = ReportGenerator(report_store=tmp_report_store, openai_api_key="dummy-key")
    event = DetectionEvent(event_type=EventType.DANGER_ZONE, zone_name="컨베이어_하부")

    report = generator.generate(event)

    assert report.generation_failed is True
    assert "RAG" in report.report_text or "연결" in report.report_text


@patch("app.core.report_generator.OpenAI")
@patch("app.core.report_generator.requests.post")
def test_report_generator_handles_llm_failure_but_keeps_rag_context(mock_post, mock_openai_cls, tmp_report_store):
    """RAG API는 성공했는데 문장화 LLM만 실패하면, 근거 자료라도 남겨야 한다 (완전 소실 방지)"""
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"llm_context": "제88조 근거 자료...", "legal_basis": []},
    )
    mock_post.return_value.raise_for_status = lambda: None

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("LLM 호출 실패")
    mock_openai_cls.return_value = mock_client

    generator = ReportGenerator(report_store=tmp_report_store, openai_api_key="dummy-key")
    event = DetectionEvent(event_type=EventType.DANGER_ZONE, zone_name="컨베이어_하부")

    report = generator.generate(event)

    assert report.generation_failed is True
    assert "제88조 근거 자료" in report.report_text
