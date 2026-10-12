"""
리포트 문장화 LLM 단독 테스트 (RAG 담당자 RAG 서버 불필요)

RAG 담당자 RAG 서버(localhost:8010)가 아직 안 켜져 있어도,
"근거 자료를 받아서 리포트 문장을 쓰는" LLM 부분만 따로 테스트할 수 있다.
실제 RAG API가 줄 법한 응답을 흉내낸 샘플 텍스트를 넣어서 확인한다.

RAG 서버가 실제로 켜져 있으면 run_report_demo.py를 대신 쓸 것 (진짜 통합 테스트).

사용법:
    python tests/manual_report_llm_test.py

key/openai_api_key 파일에 실제 키가 들어있어야 한다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.report_generator import ReportGenerator

# RAG 담당자 README에 나온 실제 예시를 참고해서 만든 샘플 근거 자료.
# 실제 RAG 서버가 켜지면 이 텍스트는 /rag/report가 실제로 검색해서 채워준다.
SAMPLE_LLM_CONTEXT = """
[근거 1] 산업안전보건기준에 관한 규칙 제88조 (원동기·회전축 등의 위험 방지)
사업주는 기계의 원동기·회전축·기어·풀리·플라이휠·벨트 및 체인 등 근로자가 위험에
처할 우려가 있는 부위에 덮개·울·슬리브 및 건널다리 등을 설치하여야 한다.
(safety_authority=true, historical_reference=false)

[근거 2] KOSHA GUIDE M-16-2020 컨베이어 안전작업 지침, 4.2절
컨베이어 벨트 하부 점검 시에는 반드시 운전을 정지하고 잠금장치(Lock-out)를
설치한 후 작업하여야 하며, 단독 작업을 금지한다.
(safety_authority=true, historical_reference=false)

[근거 3] 2018년 태안화력발전소 사고 조사보고서 요약
컨베이어 벨트 점검 중 2인 1조 원칙이 지켜지지 않아 사고 발견이 지연된 사례.
(safety_authority=false, historical_reference=true)
""".strip()


def main():
    print("=== 리포트 문장화 LLM 단독 테스트 ===")
    print("(RAG 서버 없이, 샘플 근거 자료로 실제 GPT 호출)\n")

    generator = ReportGenerator()  # key/openai_api_key에서 자동으로 키를 읽는다

    print("--- 입력한 샘플 근거 자료 ---")
    print(SAMPLE_LLM_CONTEXT)
    print()

    print("--- GPT가 작성한 리포트 ---")
    report_text = generator._compose_report_text(SAMPLE_LLM_CONTEXT)
    print(report_text)

    print("\n=== 확인할 것 ===")
    print("1. 근거 자료에 없는 법 조항이나 숫자를 지어내지 않았는지")
    print("2. '역사적 참고자료(태안화력 사고)'를 단독 법적 근거처럼 쓰지 않았는지")
    print("3. 상황 요약 → 위험도 → 법령 근거 → 권장 조치 순서로 자연스러운지")


if __name__ == "__main__":
    main()
