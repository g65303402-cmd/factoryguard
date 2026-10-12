# Vision AI 모듈 (공장수호대)

담당: 김현진 · CCTV 지속 감지 + Vision LLM 상황 분석 · 감지 이력/통계 · 사후 리포트 생성

## 이 모듈이 하는 일

기획서 2-3 핵심 개발 기능 ②에 대응하고, 팀 전체 아키텍처의 "Vision AI Server" 중
이벤트 처리(감지 → 이벤트 생성 → 이미지 캡처 → 결과 생성) 부분을 담당한다.

1. **CCTV 지속 감지** — YOLO로 사람을 찾고, 그 사람이 위험구역(컨베이어 하부 등)과
   얼마나 겹치는지 계산해서 접근 여부를 판단
2. **이력 축적 · 유형별 통계** — 감지될 때마다 이벤트를 저장하고, 대시보드가 바로 쓸 수 있는 통계로 집계
3. **Vision LLM 상황 분석** — 이벤트가 발생한 그 순간에만 OpenAI Vision API를 호출해 상황을 설명 (상시 호출 아님 → 비용 관리)
4. **사후 리포트 생성** — RAG 담당자 RAG API에서 법령 근거를 받아, LLM으로 최종 리포트 문장을 작성
   (박은희님 대시보드의 "사후 리포트 PDF 뷰어"가 보여줄 원본 텍스트)

## 위험구역 좌표는 위험구역 담당자와 공유해서 쓴다

위험구역 지정 도구는 위험구역 담당자(실시간 정지 트리거 파트)이 이미 만들어서 쓰고 계셨다.
처음엔 이 모듈에도 별도로 만들었었는데, 같은 카메라를 보고도 "정지 판단"과
"사후 기록 판단"이 서로 다른 좌표 기준으로 어긋나면 안 되므로, 중복 도구는
지우고 위험구역 담당자가 저장하는 파일을 그대로 읽어서 쓰도록 정리했다.

위험구역 담당자 도구 저장 형식:
```json
[
    {
        "zone_id": "drawn-zone-1",
        "name": "Danger-Zone-1",
        "points": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
        "severity": "high",
        "is_normalized": false
    }
]
```

`zone_config.py`가 이 형식을 그대로 읽는다. `is_normalized: true`(0~1 비율 좌표)는
아직 실제로 받아본 적이 없어서 변환 로직이 없다 — 그런 파일이 오면 경고를 출력하고
그 구역은 건너뛴다 (TODO로 남겨둠).

**위험구역을 새로 잡고 싶으면 위험구역 담당자 도구를 실행해서 `zones_config.json`을 만들고,
이 폴더 최상위에 복사해두면 된다.**

## 사후 리포트는 RAG 담당자 RAG API + 이 모듈의 LLM이 함께 만든다

원래 역할표에서 "사후 리포트 PDF 생성"이 RAG 담당자 담당으로 되어 있었는데,
역할표 수정 과정에서 문구가 빠졌던 걸 확인하고 이 모듈(Vision AI) 담당으로 가져왔다.
다만 법령 근거 검색(RAG)은 여전히 RAG 담당자가 만든 API를 그대로 가져다 쓴다 — 새로 안 만든다.

역할 분담:
- **RAG 담당자 RAG API** (`/rag/report`, 기본 `http://localhost:8010`): 법령·지침 근거를
  검색해서 `llm_context`로 반환. 출처·페이지·인용 주의사항은 이 응답을 그대로 신뢰한다.
- **이 모듈의 LLM** (`report_generator.py`): 그 근거를 받아 "상황 요약 → 위험도 →
  법령 근거 → 권장 조치" 순서의 자연스러운 문장으로 정리. 새로운 법적 주장을 만들어내지 않도록
  프롬프트에서 명시적으로 금지해뒀다.

**이벤트 형식이 RAG 담당자 API 스펙과 달라서 변환이 필요했다.** 우리 `DetectionEvent`에는
`risk_type`, `object`, `location`, `vision_labels` 같은 필드가 없어서(대신 `event_type`,
`zone_name` 등 다른 이름으로 갖고 있음), `map_event_to_rag_request()`가 이 변환을 담당한다.

**RAG API 실패는 감지 흐름을 막지 않는다.** RAG 담당자 README의 원칙("RAG 지연이나 LLM
실패가 컨베이어 긴급정지를 막아서는 안 된다")대로, 리포트 생성은 실시간 감지와 분리된
별도 흐름이다. RAG 서버가 꺼져있거나 응답이 없으면 `generation_failed=True`인 리포트를
만들고 넘어갈 뿐, 예외를 던지거나 감지를 멈추지 않는다 (`tests/test_vision_ai_service.py`의
`test_report_generator_handles_rag_api_down`으로 검증).

실행 (RAG 담당자 RAG 서버가 8010번 포트에 떠 있어야 함):
```bash
# 리포트 생성 전체 흐름 확인 (서버 켜져있는지 자동으로 먼저 체크함)
python run_report_demo.py

# 검색 품질만 따로 확인 (RAG 담당자가 아직 검증 안 하셨다고 한 부분 - 청킹/검색 정확도)
python tests/manual_rag_quality_check.py
```

`manual_rag_quality_check.py`는 RAG 담당자가 "청킹값 사람 검수, 임베딩 모델 비교 없이 확정했고
검색 품질 검증이 안 됐다"고 하신 부분을 실제로 눈으로 확인하기 위한 스크립트다. 여러 위험
시나리오로 `/rag/search`를 호출해서, 검색된 근거가 실제로 관련 있는지·문장이 중간에
끊기지 않았는지(청킹 품질)·안전 법령이 역사적 참고자료보다 우선 나오는지를 확인한다.

⚠️ 이 스크립트가 읽는 응답 필드명(`source`, `page`, `score` 등)은 RAG 담당자 README에
응답 스키마가 명시되어 있지 않아 추측한 것이다. 실행해보고 실제 필드명이 다르면
`print_search_result()` 함수만 고치면 된다 (스크립트가 첫 결과의 실제 키 목록을 출력해준다).

## 왜 YOLO로 바꿨는지 (이전엔 OpenCV 배경차분이었음)

처음엔 YOLO 없이 OpenCV 배경차분(MOG2)만으로 위험구역 접근을 감지했다.
가볍고 학습 데이터도 필요 없어서 3주 MVP에 적합하다고 판단했었다.

그런데 팀 전체 아키텍처(Vision AI Server = FastAPI + YOLO)가 확정되면서,
그리고 위험구역 담당자가 MediaPipe 다중 인식에서 겪은 것과 비슷하게, 배경차분 방식도
실측 테스트에서 두 가지 문제가 확인되어 YOLO 기반으로 전환했다.

- **벨트 표면의 움직임을 사람으로 오탐**하는 문제 (움직이는 건 뭐든 감지하는 방식의 근본적 한계)
- **정지한 사람이 배경으로 흡수**되어 감지가 끊기는 문제 (2초 만에 발생, 회귀 테스트로 확인했었음)

YOLO는 '사람'만 탐지하고 매 프레임을 독립적으로 판단하므로(배경 학습 개념 자체가 없음),
이 두 문제가 구조적으로 발생하지 않는다.

## ⚠️ 이 샌드박스에서는 YOLO 모델 다운로드가 안 됨 (팀원 컴퓨터에서는 정상)

여기(개발 환경)는 네트워크 제한 때문에 YOLO 가중치 파일(`yolo26n.pt`) 자동
다운로드가 막혀있다. 그래서 여기서는 실제 모델 없이 **mock으로 로직만 검증**했다
(`tests/test_vision_ai_service.py`). 실제 인터넷이 되는 컴퓨터에서 실행하면
최초 실행 시 자동으로 다운로드되고 정상 동작한다 (이미 팀원 컴퓨터에서 테스트 완료).

## 폴더 구조

```
vision-ai/
├── key/
│   ├── openai_api_key.example      # 키 템플릿 (git에 올라감, 안전)
│   └── openai_api_key              # 실제 키 (직접 만들어야 함, git 제외됨)
├── app/
│   ├── config.py                   # key/openai_api_key 읽는 로더
│   ├── core/
│   │   ├── camera_capture.py       # 웹캠/영상파일 캡처 (동일 인터페이스)
│   │   ├── yolo_detector.py        # YOLO 기반 사람 탐지 (얇은 래퍼)
│   │   ├── danger_zone_detector.py # 사람 탐지 결과 + 위험구역 겹침 판단
│   │   ├── zone_config.py          # zones_config.json 읽는 로더 (없으면 기본 좌표)
│   │   ├── vision_llm.py           # Vision LLM 분석 (OpenAI Vision API)
│   │   ├── event_store.py          # 이력 저장 + 통계 (로컬 JSON, Backend 연동 전 임시)
│   │   ├── report_generator.py     # RAG 담당자 RAG API 연동 + 리포트 LLM 문장화
│   │   └── report_store.py         # IncidentReport 저장 (로컬 JSON, DB INCIDENT_REPORT 대응)
│   ├── models/
│   │   └── event.py                # DetectionEvent 데이터 모델 (DB EVENT 컬렉션과 스키마 일치)
│   └── vision_ai_service.py        # 전체 흐름을 조립하는 오케스트레이터
├── tests/
│   ├── test_vision_ai_service.py           # pytest 단위 테스트 (YOLO·Vision LLM·RAG API 모두 mock)
│   ├── manual_yolo_integration_test.py     # 실제 YOLO 모델로 검증 (팀원 컴퓨터에서 직접 실행)
│   ├── manual_report_llm_test.py           # RAG 서버 없이 리포트 문장화 LLM만 단독 테스트
│   └── manual_rag_quality_check.py         # RAG 담당자 RAG 서버 검색 품질 검증 (실제 서버 필요)
├── sample_data/
│   └── demo.mp4                    # 파이프라인 동작 확인용 합성 영상 (사람 아님, YOLO 감지 안 됨 - 아래 참고)
├── zones_config.json               # 위험구역 좌표 (직접 만들어야 함, git 제외됨 - 카메라마다 다름)
├── run_demo.py                     # 실행 진입점 (감지)
├── run_report_demo.py              # 실행 진입점 (사후 리포트 생성, RAG 담당자 RAG 서버 필요)
└── requirements.txt
```

## 설치 및 실행

```bash
cd vision-ai
pip install -r requirements.txt
```

### API 키 설정 (key 폴더 방식)

API 키는 프로젝트 루트가 아니라 `key/` 폴더 안에 넣어서 관리한다.

```bash
cp key/openai_api_key.example key/openai_api_key
```

그다음 `key/openai_api_key` 파일을 열어서, **접두어 없이 키 값만** 한 줄로 바꿔 넣는다.

```
sk-실제_발급받은_키
```

`key/openai_api_key`(실제 키 파일)는 `.gitignore`에 등록되어 있어서 git에 올라가지 않는다.
**실제 키가 든 파일은 절대 디스코드 등에 직접 올리지 말 것.**
키가 없어도 로컬 감지(위험구역 접근 등)만 쓰는 건 문제없이 동작한다. `--vision-llm` 옵션을 쓸 때만 필요하다.

### 실행

**처음 웹캠으로 쓰는 경우, 위험구역 좌표부터 잡아야 한다.** 좌표 지정은 위험구역 담당자의
위험구역 도구로 하고(위 "위험구역 좌표는 위험구역 담당자와 공유해서 쓴다" 참고), 저장된
`zones_config.json`을 이 폴더 최상위에 복사해두면 `run_demo.py`가 자동으로 읽는다.
(아직 없으면 데모 영상 기준 기본 좌표로 동작한다.)

```bash
# 1) (참고용) 합성 영상으로 파이프라인 동작만 확인 - YOLO가 사람을 인식 못해 감지는 0건이 정상
python run_demo.py

# 2) 실제 웹캠으로 테스트 (진짜 탐지 확인은 이걸로, zones_config.json 있으면 그 좌표 사용)
python run_demo.py --webcam

# 3) 웹캠 + Vision LLM까지 포함
python run_demo.py --webcam --vision-llm

# 단위 테스트 (mock 기반, 네트워크/모델 불필요)
pytest tests/ -v

# 실제 모델 통합 테스트 (인터넷 되는 컴퓨터에서, 최초 실행 시 자동 다운로드)
python tests/manual_yolo_integration_test.py
```

## Backend와 연동하는 방법

`VisionAIService(on_event=콜백함수)`로 생성하면, 이벤트가 발생할 때마다 콜백이 호출된다.
지금은 `run_demo.py`에서 print만 하고 있는데, 팀 아키텍처의
"Vision AI Server → Backend (HTTP POST)" 흐름대로 이 부분을 실제 요청 코드로 바꾸면 연결된다.

```python
import requests

def on_event(event):
    requests.post(
        "http://localhost:8000/events",   # Backend API Server 주소
        json=event.to_dict(),
    )
```

`DetectionEvent.to_dict()`가 반환하는 필드는 기획서 DB 설계의 `EVENT` 컬렉션 구조와
동일하게 맞춰뒀다. (`camera_id`, `event_type`, `confidence`, `timestamp` 등 — 팀 아키텍처
예시 JSON과 필드명이 거의 일치한다. `image_url`은 아직 이미지 호스팅이 없어서
로컬 경로(`frame_path`)로 대체해뒀다. Backend에 업로드 API가 생기면 그때 교체할 부분.)

## 실시간 정지 트리거(위험구역 담당자 파트)와의 관계

`DetectionEvent.realtime_trigger = True`인 이벤트(위험구역 접근)는
이 모듈만 처리하고 끝나는 게 아니라, 실시간 자동 정지 모듈에도 즉시 알려서
컨베이어를 세워야 한다. 지금은 `on_event` 콜백 하나로 통합되어 있는데,
실제 연동 시엔 이 콜백 안에서 실시간 정지 모듈의 API도 함께 호출하면 된다.

이 모듈(Vision AI)과 위험구역 담당자 모듈(MediaPipe 제스처)은 코드상 완전히 분리되어 있어서
서로 건드릴 필요가 없다.

## 다음에 할 일 (TODO)

- [ ] `zones_config.json`의 `is_normalized: true`(비율 좌표) 케이스 변환 로직 추가
- [ ] Backend API 완성되면 `on_event` 콜백을 실제 HTTP 요청으로 교체
- [ ] `analysis_cooldown_sec`(Vision LLM 호출 간격) 값을 실제 카메라 환경에서 튜닝
- [ ] YOLO `confidence_threshold`, `overlap_threshold` 값을 실제 웹캠 환경에서 튜닝
- [ ] 3단계 확장(2027, 기획서 4-3): 이상 행동·정비 자세 감지 등 YOLO 활용 범위 확장
- [ ] `manual_rag_quality_check.py`로 RAG 담당자 RAG 검색 품질 실제 확인 (청킹·검색 정확도)
- [ ] 위 검증 결과에 따라 `report_generator.py`의 응답 필드 파싱(`results`/`sources` 등 키 이름) 실제 스키마에 맞게 조정
- [ ] `vision_ai_service.py`에서 감지 시 `ReportGenerator.generate()`를 자동 호출하도록 연결
  (지금은 `run_report_demo.py`로 수동 호출만 가능, 실시간 감지와는 분리된 별도 흐름으로 설계)
- [ ] 리포트를 박은희님 대시보드가 조회할 수 있도록 API로 노출 (Backend 완성 후)
