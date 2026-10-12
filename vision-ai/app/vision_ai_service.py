"""
Vision AI 서비스 - 메인 오케스트레이터

흐름:
  CCTV 프레임 캡처 (camera_capture)
        ↓
  위험구역 접근 감지 (danger_zone_detector, YOLO 사람 탐지 + 구역 겹침 판단 - 매 프레임)
        ↓
  감지되면 → 이력에 기록 (event_store)
        ↓
  일정 쿨다운 이상 지속되거나 심각도가 높으면 → Vision LLM 호출 (vision_llm, 이벤트 발생시에만)
        ↓
  Vision LLM 분석 결과를 이벤트에 채워서 다시 저장 (사후 리포트용 근거)

Backend와의 연동 지점: on_event 콜백을 주입하면, 이벤트 발생 시 FastAPI로 전송하도록
쉽게 확장할 수 있다 (팀 아키텍처상 Vision AI Server → Backend HTTP POST 지점).
"""

import logging
import time
from datetime import datetime
from typing import Callable, List, Optional

from app.core.camera_capture import CameraCapture
from app.core.danger_zone_detector import DangerZone, DangerZoneDetector
from app.core.event_store import EventStore
from app.core.vision_llm import VisionLLMAnalyzer
from app.models.event import DetectionEvent, EventSeverity, EventType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vision_ai.service")


class VisionAIService:
    def __init__(
        self,
        source,
        zones: List[DangerZone],
        camera_id: str = "cam-01",
        event_store: Optional[EventStore] = None,
        vision_llm: Optional[VisionLLMAnalyzer] = None,
        analysis_cooldown_sec: float = 15.0,
        on_event: Optional[Callable[[DetectionEvent], None]] = None,
        use_vision_llm: bool = True,
    ):
        """
        source: 카메라 소스 (0=웹캠, 또는 영상 파일 경로)
        zones: 감시할 위험구역 리스트
        analysis_cooldown_sec: 같은 구역에 대해 Vision LLM을 다시 호출하기까지 최소 간격.
                                너무 자주 호출되면 비용이 커지므로 쿨다운을 둔다.
        on_event: 이벤트 발생 시 실행할 콜백 (Backend 전송용 훅)
        use_vision_llm: False면 로컬 감지만 하고 Vision LLM은 호출 안 함 (API 키 없을 때 테스트용)
        """
        self.camera = CameraCapture(source, camera_id=camera_id)
        self.detector = DangerZoneDetector(zones)
        self.event_store = event_store or EventStore()

        # use_vision_llm=True인데 vision_llm 객체를 안 넘겼으면 기본 설정으로 자동 생성한다.
        # (이전 버전 버그: 여기서 자동 생성을 안 해서 --vision-llm 옵션을 줘도
        #  실제로는 한 번도 호출되지 않는 문제가 있었다. .env의 OPENAI_API_KEY는
        #  VisionLLMAnalyzer 생성 시점에 app.config.get_openai_api_key()가 읽어간다.)
        if use_vision_llm:
            self.vision_llm = vision_llm or VisionLLMAnalyzer()
        else:
            self.vision_llm = None
        self.analysis_cooldown_sec = analysis_cooldown_sec
        self.on_event = on_event
        self._last_analysis_time: dict = {}  # zone_name -> timestamp

        os_makedirs = __import__("os").makedirs
        os_makedirs("data/captures", exist_ok=True)

    def _should_call_vision_llm(self, zone_name: str) -> bool:
        last = self._last_analysis_time.get(zone_name, 0)
        return (time.time() - last) >= self.analysis_cooldown_sec

    def _save_capture(self, frame, event_id: str) -> str:
        import cv2
        path = f"data/captures/{event_id}.jpg"
        cv2.imwrite(path, frame)
        return path

    def process_frame(self, frame) -> List[DetectionEvent]:
        """프레임 1장을 처리해서, 발생한 이벤트 목록을 반환 (없으면 빈 리스트)"""
        detections = self.detector.detect(frame)
        events = []

        for det in detections:
            zone_name = det["zone_name"]
            severity = EventSeverity.HIGH if det["overlap_ratio"] > 0.15 else EventSeverity.MEDIUM

            event = DetectionEvent(
                event_type=EventType.DANGER_ZONE,
                severity=severity,
                confidence=det["overlap_ratio"],
                camera_id=self.camera.camera_id,
                zone_name=zone_name,
                bbox=det["bbox"],
                realtime_trigger=True,  # 위험구역 접근은 실시간 정지 모듈에도 알려야 함
            )

            event.frame_path = self._save_capture(frame, event.event_id)

            # Vision LLM은 쿨다운을 지켜서만 호출 (비용 관리)
            if self.vision_llm and self._should_call_vision_llm(zone_name):
                context = f"위험구역 '{zone_name}' 접근 감지, 겹침 비율 {det['overlap_ratio']*100:.1f}%"
                event.vision_llm_description = self.vision_llm.analyze(frame, context=context)
                self._last_analysis_time[zone_name] = time.time()

            self.event_store.add(event)
            events.append(event)

            logger.info(
                f"[감지] {zone_name} | 심각도={severity.value} | "
                f"겹침={det['overlap_ratio']*100:.1f}% | event_id={event.event_id}"
            )

            if self.on_event:
                self.on_event(event)

        return events

    def run(self, max_frames: Optional[int] = None, frame_interval_sec: float = 0.2):
        """
        실시간(또는 데모 영상) 처리 루프.
        max_frames: 테스트용으로 N프레임만 처리하고 종료하려면 지정. None이면 무한 루프.
        frame_interval_sec: 프레임 간 처리 간격 (CPU 부담 조절용)
        """
        if not self.camera.open():
            raise RuntimeError("카메라를 열 수 없습니다.")

        logger.info("Vision AI 서비스 시작")
        processed = 0
        try:
            for frame in self.camera.frame_stream(interval_sec=frame_interval_sec):
                self.process_frame(frame)
                processed += 1
                if max_frames and processed >= max_frames:
                    break
        finally:
            self.camera.close()
            logger.info(f"Vision AI 서비스 종료 (총 {processed} 프레임 처리)")

    def get_history(self, limit: int = 50):
        return self.event_store.get_history(limit=limit)

    def get_stats(self):
        return self.event_store.get_stats()
