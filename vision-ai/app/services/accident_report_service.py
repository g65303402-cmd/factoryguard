"""
사고 이미지 분석 + RAG 법령 근거 통합 서비스

기존 analyze_accident()는 그대로 유지 (Vision LLM만으로 사람이 읽기 좋은 6섹션 리포트 생성).
새로 추가된 generate_report_with_legal_basis()는:
  1) analyze_accident()로 사람이 읽을 리포트를 그대로 생성하고
  2) 별도의 짧고 구체적인 상황 요약(위험유형/1~2문장 설명)을 뽑아서
  3) 백엔드 담당자 RAG 서버(/rag/report)에 그 요약만 보내 법령 근거를 받아온다.

(2)에서 굳이 별도 요약을 쓰는 이유:
  analyze_accident()가 만드는 6섹션 리포트 전체를 그대로 RAG 쿼리에 넣으면
  문장이 너무 길고 일반적인 표현이 섞여서 검색 정확도가 떨어지는 문제가
  실제 테스트에서 확인됨 (짧고 구체적인 설명일수록 관련 법 조항이 검색 1위로 잘 나옴).

RAG 서버가 꺼져있거나 응답이 없어도 예외를 던지지 않고,
Vision 분석 결과(vision_report)는 항상 반환한다 (법령 근거만 비어있게 처리).

(원본은 서버 ai_server/app/services/... 에서 받아온 코드를 기반으로 확장함)
"""

import base64
import json
import os
from pathlib import Path

import requests
from openai import OpenAI

# OPENAI_API_KEY는 .env에서 자동으로 읽힌다 (OpenAI() 기본 동작).
# 기존 코드에 client가 정의되어 있지 않았다면 아래 줄을 추가해야 한다.
client = OpenAI()

# 백엔드 담당자 RAG 서버 주소. .env에 RAG_API_URL이 있으면 그걸 쓰고, 없으면 기본값 사용.
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8010")


def encode_image(image_path: str | Path) -> str:
    """이미지를 Base64 문자열로 변환합니다."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_accident(
    image_path: str | Path,
    mime_type: str = "image/jpeg",
) -> str:
    """Vision LLM을 이용해 산업재해 사고 상황을 분석합니다. (기존 로직, 변경 없음)"""

    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": """
당신은 산업안전 전문가입니다.

제공된 이미지를 분석하여 사고 상황을 객관적으로 판단하고
아래 형식으로 보고서를 작성하세요.

■ 사고 개요

■ 현재 관찰된 상황

■ 추정 사고 유형

■ 위험도
(상 / 중 / 하)

■ 즉시 필요한 조치

■ 추가 확인 사항

이미지에서 확인 가능한 사실만 작성하고,
불확실한 내용은 "추정"이라고 명시하세요.
""",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "이미지를 분석하여 산업재해 사고 보고서를 작성하세요.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{mime_type};base64,"
                                f"{base64_image}"
                            )
                        },
                    },
                ],
            },
        ],
    )

    report = response.choices[0].message.content

    if not report:
        raise RuntimeError("사고 분석 결과가 비어 있습니다.")

    return report


def _extract_situation_summary(image_path: str | Path, mime_type: str = "image/jpeg") -> dict:
    """
    RAG 검색용으로 쓸 '짧고 구체적인' 상황 설명만 별도로 뽑는다.
    analyze_accident()의 6섹션 리포트 전체를 RAG 쿼리에 그대로 쓰면
    검색 정확도가 떨어지므로, 여기서는 JSON으로 핵심만 받는다.
    """
    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 산업안전 사고 이미지를 분석하는 보조 담당자다. "
                    "아래 JSON 형식으로만 답하라(다른 텍스트나 설명 없이 JSON만):\n"
                    '{"risk_type": "끼임/추락/화재 등 한 단어", '
                    '"description": "누가 어디서 무엇을 하다 어떤 위험에 노출됐는지 1~2문장", '
                    '"hazard_tags": ["끼임", "보호구미착용"]}'
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "이미지 속 사고 상황을 분석해서 JSON으로만 답해줘."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
    )

    try:
        return json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return {"risk_type": "기타", "description": "", "hazard_tags": []}


def _call_rag_report(event_payload: dict, route: str = "safety", timeout_sec: float = 10.0) -> dict | None:
    """백엔드 담당자 RAG 서버(/rag/report)를 호출해서 법령 근거를 받아온다."""
    try:
        resp = requests.post(
            f"{RAG_API_URL}/rag/report",
            json={
                "event": event_payload,
                "route": route,
                "top_k": 5,
                "candidate_multiplier": 8,
                "include_markdown": True,
            },
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[accident-report] RAG API 호출 실패: {e}")
        return None


def generate_report_with_legal_basis(
    image_path: str | Path,
    mime_type: str = "image/jpeg",
) -> dict:
    """
    이미지를 분석해서 (1) Vision LLM 사고 리포트 + (2) RAG 법령 근거를 합쳐서 반환한다.

    반환 형식:
        {
            "vision_report": str,           # 기존 analyze_accident() 결과 (6섹션 리포트)
            "legal_basis": list[dict],      # RAG가 찾은 법령 근거 (제목/출처/페이지/조문 등)
            "recommended_action": list[str],# RAG 기반 권장 조치
            "rag_available": bool,          # RAG 서버 응답 성공 여부
        }

    RAG 서버가 꺼져있거나 실패해도 예외를 던지지 않는다 -
    vision_report는 항상 채워지고, legal_basis/recommended_action만 빈 리스트가 된다.
    """
    vision_report = analyze_accident(image_path, mime_type)
    situation = _extract_situation_summary(image_path, mime_type)

    event_payload = {
        "source": "vision",
        "risk_type": situation.get("risk_type", "기타"),
        "description": situation.get("description", ""),
        "hazard_tags": situation.get("hazard_tags", []),
    }

    rag_response = _call_rag_report(event_payload)

    result = {
        "vision_report": vision_report,
        "legal_basis": [],
        "recommended_action": [],
        "rag_available": False,
    }

    if rag_response:
        # 실제 RAG 서버 스키마(ReportResponse) 기준 - "results"나 "sources"가 아니라 "legal_basis"임에 주의.
        # (오늘 이 키 이름 착각으로 근거자료가 항상 0건 나오던 버그를 다른 곳에서 이미 한 번 발견했음)
        result["legal_basis"] = rag_response.get("legal_basis", [])
        result["recommended_action"] = rag_response.get("recommended_action", [])
        result["rag_available"] = True

    return result
