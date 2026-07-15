# 공장수호대 RAG 검색 API

이 API는 Vision AI/KWS가 만든 위험 이벤트를 받아 컨베이어 안전 법령·검사기준 근거를 검색하고, 리포트 생성 LLM에 넘길 근거 JSON을 반환한다.

긴급정지 제어는 Vision/KWS/Backend의 즉시 경로에서 처리하고, 이 RAG API는 사후 분석·리포트·교육자료 근거 생성에만 사용한다.

## 실행

```powershell
.\.rag_venv\Scripts\python.exe -m uvicorn rag_service.api:app --host 0.0.0.0 --port 8010
```

문서 확인:

```text
http://localhost:8010/docs
```

## 주요 엔드포인트

- `GET /health`: 모델과 FAISS 인덱스 로딩 확인
- `POST /rag/search`: 근거 검색 결과 반환
- `POST /rag/report`: 리포트 생성 LLM에 넣기 좋은 요약·권장조치·근거 반환

## Vision AI 위험 이벤트 연결 예시

```python
import requests

event = {
    "event": {
        "event_id": "evt_001",
        "source": "vision",
        "risk_type": "끼임",
        "object": "컨베이어",
        "location": "하부 점검구역",
        "description": "컨베이어 풀리 물림점에 작업자 손 접근 감지",
        "vision_labels": ["danger_zone_entry", "hand_near_pulley"],
    },
    "top_k": 5,
}

response = requests.post("http://localhost:8010/rag/report", json=event, timeout=30)
print(response.json()["llm_context"])
```

## KWS 이벤트 연결 예시

```python
import requests

event = {
    "event": {
        "event_id": "evt_kws_001",
        "source": "kws",
        "risk_type": "비상정지",
        "object": "컨베이어",
        "description": "작업자가 정지 요청 음성을 발화함",
        "kws_keywords": ["멈춰", "정지", "살려줘"],
    },
    "top_k": 5,
}

response = requests.post("http://localhost:8010/rag/search", json=event, timeout=30)
print(response.json()["results"][0])
```

## 리포트 생성 LLM 연결 방식

`/rag/report` 응답의 `llm_context`를 LLM 프롬프트에 넣는다. LLM은 문장화만 담당하고, 출처·페이지·인용 주의사항은 API 응답을 그대로 사용한다.

주의:

- `safety_authority`를 법적 근거로 우선 사용한다.
- `historical_reference=true` 자료는 단독 법적 결론으로 쓰지 않는다.
- `privacy` 결과는 CCTV·영상정보 문맥에서만 사용한다.
- RAG 지연이나 LLM 실패가 컨베이어 긴급정지를 막아서는 안 된다.

