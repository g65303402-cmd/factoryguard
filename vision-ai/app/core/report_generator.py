"""
사후 리포트 생성기

RAG 담당자의 RAG API(/rag/report)에서 법령 근거를 받아온 뒤,
LLM으로 최종 리포트 문장을 만든다.

역할 분담 (RAG 담당자 README 기준):
  - RAG API: 근거 검색 + 출처·페이지·인용 주의사항 제공 (법적 근거의 '사실' 부분)
  - 이 모듈의 LLM: 그 근거를 자연스러운 문장으로 정리 ('문장화'만 담당, 새 법적 주장을 지어내지 않음)

중요: 이 리포트 생성은 위험구역 감지(실시간)와 분리된 별도 흐름이다.
RAG API가 느리거나 실패해도 감지·정지 자체에는 영향을 주지 않는다
(RAG 담당자 README의 "RAG 지연이나 LLM 실패가 컨베이어 긴급정지를 막아서는 안 된다" 원칙과 일치).
"""

import logging
from typing import Optional

import requests
from openai import OpenAI

from app.config import get_openai_api_key
from app.core.report_store import IncidentReport, ReportStore
from app.models.event import DetectionEvent, EventType

logger = logging.getLogger("vision_ai.report_generator")

# 우리 이벤트 유형 → RAG 담당자 RAG API가 기대하는 risk_type 문자열
# (RAG 담당자 README 예시: "끼임", "비상정지")
RISK_TYPE_MAP = {
    EventType.DANGER_ZONE: "끼임",
    EventType.WORKER_APPROACH: "끼임",
    EventType.DANGEROUS_POSTURE: "끼임",
    EventType.FALLEN: "쓰러짐",
    EventType.UNKNOWN: "기타",
}

CONVEYOR_OBJECT_NAME = "컨베이어"  # 기획서 확정 범위: 컨베이어 벨트 특화

REPORT_SYSTEM_PROMPT = """당신은 제조업 산업안전 사후 리포트를 작성하는 보조 담당자다.
아래에 주어진 '법령·지침 근거 자료'만을 사실 근거로 사용해 리포트 문단을 작성하라.

반드시 지킬 것:
1. 근거 자료에 없는 법 조항이나 수치를 새로 만들어내지 않는다 (환각 금지).
2. 다음 순서로 자연스러운 한국어 문단을 작성한다: 상황 요약 → 위험도 → 관련 법령 근거 → 권장 조치.
3. 근거 자료의 출처 표기(법령명·조항 등)는 그대로 살려서 인용한다.
4. 과장하지 말고, 담백하고 사실적인 어조로 작성한다."""


def map_event_to_rag_request(event: DetectionEvent, top_k: int = 5) -> dict:
    """DetectionEvent를 RAG 담당자 RAG API가 기대하는 요청 형식으로 변환한다."""
    description = event.vision_llm_description or (
        f"{event.zone_name or '위험구역'} 접근 감지 (신뢰도 {event.confidence:.0%})"
    )
    return {
        "event": {
            "event_id": event.event_id,
            "source": "vision",
            "risk_type": RISK_TYPE_MAP.get(event.event_type, "기타"),
            "object": CONVEYOR_OBJECT_NAME,
            "location": event.zone_name or "미지정 구역",
            "description": description,
            "vision_labels": ["danger_zone_entry"],
        },
        "top_k": top_k,
    }


class ReportGenerator:
    def __init__(
        self,
        rag_api_url: str = "http://localhost:8010",
        report_store: Optional[ReportStore] = None,
        openai_api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout_sec: float = 10.0,
    ):
        """
        rag_api_url: RAG 담당자 RAG 서버 주소 (README 기준 기본 포트 8010)
        timeout_sec: RAG API 응답을 얼마나 기다릴지. 이 시간을 넘기면 실패로 처리하고
                     리포트 생성을 포기한다 (실시간 정지 흐름과 무관하므로 재시도는 하지 않음).
        """
        self.rag_api_url = rag_api_url.rstrip("/")
        self.report_store = report_store or ReportStore()
        self.client = OpenAI(api_key=openai_api_key or get_openai_api_key())
        self.model = model
        self.timeout_sec = timeout_sec

    def _call_rag_report_api(self, event: DetectionEvent) -> Optional[dict]:
        payload = map_event_to_rag_request(event)
        try:
            response = requests.post(
                f"{self.rag_api_url}/rag/report",
                json=payload,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"RAG API 호출 실패 (event_id={event.event_id}): {e}")
            return None

    def _compose_report_text(self, llm_context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": f"법령·지침 근거 자료:\n{llm_context}"},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        return response.choices[0].message.content

    def generate(self, event: DetectionEvent) -> IncidentReport:
        """
        이벤트 1건에 대한 사후 리포트를 생성해서 저장하고 반환한다.
        RAG API나 LLM 호출이 실패해도 예외를 던지지 않고,
        generation_failed=True인 IncidentReport를 반환한다 (호출부가 감지 흐름을 계속 진행할 수 있도록).
        """
        rag_response = self._call_rag_report_api(event)

        if rag_response is None or "llm_context" not in rag_response:
            report = IncidentReport(
                event_id=event.event_id,
                report_text="[리포트 생성 실패: RAG 근거 검색 서버에 연결할 수 없습니다. "
                             "감지 기록 자체는 정상 저장되었습니다.]",
                generation_failed=True,
            )
            self.report_store.add(report)
            return report

        llm_context = rag_response["llm_context"]

        try:
            report_text = self._compose_report_text(llm_context)
        except Exception as e:
            logger.error(f"리포트 문장화 LLM 호출 실패 (event_id={event.event_id}): {e}")
            report = IncidentReport(
                event_id=event.event_id,
                report_text=f"[리포트 문장화 실패, 근거 자료만 남김]\n{llm_context}",
                rag_sources=rag_response.get("legal_basis", []),
                generation_failed=True,
            )
            self.report_store.add(report)
            return report

        report = IncidentReport(
            event_id=event.event_id,
            report_text=report_text,
            rag_sources=rag_response.get("legal_basis", []),
        )
        self.report_store.add(report)
        logger.info(f"사후 리포트 생성 완료 (event_id={event.event_id})")
        return report
