"""
사후 리포트 생성 데모

RAG 담당자 RAG 서버(rag_service.api:app, 기본 8010번 포트)가 실제로 켜져 있어야 동작한다.
RAG 담당자 README 실행법 그대로:
    .\\.rag_venv\\Scripts\\python.exe -m uvicorn rag_service.api:app --host 0.0.0.0 --port 8010

사용법:
    python run_report_demo.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import requests

from app.core.report_generator import ReportGenerator
from app.models.event import DetectionEvent, EventType

RAG_API_URL = "http://localhost:8010"


def check_rag_server() -> bool:
    """RAG 담당자 RAG 서버가 켜져 있는지 미리 확인. 안 켜져 있으면 뭘 해야 하는지 바로 안내한다."""
    try:
        response = requests.get(f"{RAG_API_URL}/health", timeout=3)
        response.raise_for_status()
        print(f"✅ RAG 서버 연결 확인됨: {response.json()}\n")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ RAG 서버({RAG_API_URL})에 연결할 수 없습니다: {e}\n")
        print("RAG 담당자 브랜치(agent/rag-api-service)를 받아서 먼저 서버를 켜주세요:")
        print("  .\\.rag_venv\\Scripts\\python.exe -m uvicorn rag_service.api:app --host 0.0.0.0 --port 8010\n")
        return False


def main():
    if not check_rag_server():
        sys.exit(1)

    # 실제로는 vision_ai_service.py가 감지한 이벤트를 그대로 넘기면 된다.
    # 데모에서는 감지된 상황을 흉내낸 이벤트를 직접 만든다.
    event = DetectionEvent(
        event_type=EventType.DANGER_ZONE,
        zone_name="컨베이어_하부",
        confidence=0.82,
        vision_llm_description="작업자가 컨베이어 하부 점검구역에 접근했습니다. "
                                 "손이 풀리 물림점 근처에서 확인되어 위험도가 높습니다.",
    )

    print(f"=== 리포트 생성 시작 (event_id={event.event_id}) ===\n")

    generator = ReportGenerator(rag_api_url=RAG_API_URL)
    report = generator.generate(event)

    print(f"생성 실패 여부: {report.generation_failed}")
    print(f"\n=== 리포트 본문 ===\n{report.report_text}")
    print(f"\n=== 근거 자료 ({len(report.rag_sources)}건) ===")
    for src in report.rag_sources:
        print(f"  - {src}")


if __name__ == "__main__":
    main()
