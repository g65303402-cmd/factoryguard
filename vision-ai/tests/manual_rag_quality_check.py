"""
RAG 검색 품질 검증 스크립트

RAG 담당자가 "청킹값 사람 검수 없이, 임베딩 모델 비교 없이 확정했고
검색 품질 검증이 안 됐다"고 하신 부분을 실제로 확인하기 위한 스크립트다.

여러 위험 시나리오로 /rag/search를 호출해서, 검색된 근거 조각들을
사람이 눈으로 읽고 "이게 맞는 조항인지, 문맥이 잘려서 이상하지 않은지"
판단할 수 있게 출력한다.

사용법:
    python tests/manual_rag_quality_check.py

RAG 담당자 RAG 서버(agent/rag-api-service 브랜치)가 localhost:8010에 떠 있어야 한다.

⚠️ 주의: 아래 print_search_result()가 읽는 필드명(source, page, score, text 등)은
RAG 담당자 README에 응답 스키마가 명시되어 있지 않아 합리적으로 추측한 것이다.
실제 실행해보고 필드명이 다르면(예: "citation" 대신 "source" 등), 이 부분만 맞춰 고치면 된다.
raw JSON을 보고 싶으면 print(result) 한 줄만 추가해서 실제 구조를 먼저 확인해도 된다.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests

RAG_API_URL = "http://localhost:8010"

# 실제로 우리 시스템이 만들어낼 법한 이벤트들로 검증한다.
# (RAG 담당자 README의 vision/kws 예시 형식 그대로)
TEST_CASES = [
    {
        "label": "케이스 1) 컨베이어 하부 위험구역 접근 (우리 시스템의 핵심 시나리오)",
        "event": {
            "event_id": "quality-check-1",
            "source": "vision",
            "risk_type": "끼임",
            "object": "컨베이어",
            "location": "하부 점검구역",
            "description": "컨베이어 풀리 물림점에 작업자 손 접근 감지",
            "vision_labels": ["danger_zone_entry", "hand_near_pulley"],
        },
    },
    {
        "label": "케이스 2) 비상정지 음성 명령 (KWS 시나리오)",
        "event": {
            "event_id": "quality-check-2",
            "source": "kws",
            "risk_type": "비상정지",
            "object": "컨베이어",
            "description": "작업자가 정지 요청 음성을 발화함",
            "kws_keywords": ["멈춰", "정지"],
        },
    },
    {
        "label": "케이스 3) 야간 단독 작업 중 접근 (기획서 핵심 근거 - 뚜안 사건 유형)",
        "event": {
            "event_id": "quality-check-3",
            "source": "vision",
            "risk_type": "끼임",
            "object": "컨베이어",
            "location": "하부 점검구역",
            "description": "새벽 시간대 작업자 단독 접근, 비상정지 장치 접근성 우려",
            "vision_labels": ["danger_zone_entry", "night_shift", "single_worker"],
        },
    },
]


def check_server() -> bool:
    try:
        response = requests.get(f"{RAG_API_URL}/health", timeout=3)
        response.raise_for_status()
        print(f"✅ RAG 서버 연결 확인됨: {response.json()}\n")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ RAG 서버({RAG_API_URL})에 연결할 수 없습니다: {e}")
        print("먼저 RAG 담당자 RAG 서버를 켜주세요.\n")
        return False


def print_search_result(result: dict, idx: int):
    """검색 결과 1건을 사람이 품질 판단하기 좋게 출력"""
    source = result.get("source") or result.get("title") or "(출처 필드 없음)"
    page = result.get("page", "?")
    score = result.get("score", result.get("similarity", "?"))
    text = result.get("text") or result.get("content") or result.get("chunk", "")
    safety_authority = result.get("safety_authority")
    historical_reference = result.get("historical_reference")

    print(f"  [{idx}] 출처: {source} (p.{page}) | 유사도: {score}")
    if safety_authority is not None:
        print(f"      safety_authority={safety_authority}, historical_reference={historical_reference}")
    print(f"      본문: {text[:200]}{'...' if len(text) > 200 else ''}")

    # 품질 경고 신호 - 이런 경우는 청킹이나 검색이 이상할 가능성
    if len(text.strip()) < 20:
        print("      ⚠️  본문이 너무 짧음 - 청킹이 과도하게 잘렸을 수 있음")
    if not text.strip().endswith((".", "다", "함", ")")):
        print("      ⚠️  문장이 중간에 끊긴 것처럼 보임 - 청킹 경계 확인 필요")
    print()


def main():
    if not check_server():
        sys.exit(1)

    for case in TEST_CASES:
        print("=" * 70)
        print(case["label"])
        print("=" * 70)

        payload = {"event": case["event"], "top_k": 5}

        try:
            response = requests.post(f"{RAG_API_URL}/rag/search", json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"검색 실패: {e}\n")
            continue

        results = data.get("results", [])
        print(f"검색된 근거: {len(results)}건\n")

        if not results:
            print("⚠️  검색 결과가 0건입니다. 이 시나리오에 맞는 근거가 인덱싱되어 있는지 확인 필요\n")
            continue

        # 첫 번째 케이스의 첫 결과는 실제 필드 구조를 먼저 보여준다
        # (print_search_result의 필드명 추측이 맞는지 확인용)
        if case is TEST_CASES[0]:
            print("  [원본 구조 확인용 - 첫 결과의 실제 키 목록]")
            print(f"  {list(results[0].keys())}\n")

        for i, result in enumerate(results, 1):
            print_search_result(result, i)

    print("=" * 70)
    print("확인할 것:")
    print("1. 컨베이어/끼임 관련 질문에 실제로 관련 있는 조항이 상위에 나오는지")
    print("2. 본문이 문장 중간에 뚝 끊기지 않고 의미가 통하는지 (청킹 품질)")
    print("3. safety_authority=true인 자료가 historical_reference보다 우선 노출되는지")
    print("=" * 70)


if __name__ == "__main__":
    main()
