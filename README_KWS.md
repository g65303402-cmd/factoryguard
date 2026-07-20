# KWS 개발 방향과 테스트 방법

KWS는 음성 기반 긴급정지 트리거와 이벤트 메타데이터 생성기를 담당한다. RAG/LLM은 사후 근거 생성 경로이므로, KWS 감지 후 컨베이어 정지는 RAG 응답을 기다리지 않는다.

## 목표 흐름

```text
마이크 입력
  -> KWS 감지
  -> dry_run 또는 실제 액추에이터 정지 명령
  -> Backend 이벤트 저장
  -> RAG API 호출
  -> 리포트 생성 LLM이 근거를 문장화
```

## 현재 구현

현재는 실제 마이크 입력을 받는 경로와 openWakeWord 모델 어댑터를 포함한다. 모델 파일이 없을 때는 마이크 녹음까지는 가능하지만 감지는 `not configured`로 반환된다.

- `kws_service/microphone.py`: 마이크 장치 조회와 단발 녹음
- `kws_service/detector.py`: openWakeWord 오디오 감지기와 deprecated 텍스트 시뮬레이션 감지기
- `kws_service/event_builder.py`: KWS 감지 결과를 RAG/Backend 이벤트 JSON으로 변환
- `kws_service/actuator.py`: 실제 컨베이어가 없는 상태에서 쓰는 `dry_run` 정지 액추에이터
- `kws_service/api.py`: FastAPI 엔드포인트

## 실행

```powershell
.\.rag_venv\Scripts\python.exe -m uvicorn kws_service.api:app --host 0.0.0.0 --port 8020
```

문서:

```text
http://localhost:8020/docs
```

## 시뮬레이션 테스트

`/kws/simulate`는 텍스트 기반 smoke test 용도로만 남겨둔다. 실제 KWS 흐름은 아래 마이크 입력 엔드포인트를 사용한다.

```python
import requests

payload = {
    "text": "멈춰 위험해",
    "location": "컨베이어 1번 라인 하부",
    "line_id": "line-1",
    "force_stop": True,
    "call_rag": False
}

response = requests.post("http://localhost:8020/kws/simulate", json=payload, timeout=10)
print(response.json())
```

RAG API가 `8010` 포트에서 실행 중이면 `call_rag=True`로 두어 KWS 이벤트가 법령 근거 검색까지 이어지는지 확인할 수 있다.

## 마이크 입력 테스트

선택 의존성 설치:

```powershell
.\.rag_venv\Scripts\python.exe -m pip install -r requirements-kws.txt
```

마이크 장치 확인:

```text
GET http://localhost:8020/kws/mic/devices
```

마이크 캡처만 확인:

```python
import requests

payload = {"duration_seconds": 1, "device": 12}
response = requests.post("http://localhost:8020/kws/mic/check-capture", json=payload, timeout=15)
print(response.json())
```

`ok=true`, `captured_frames>0`, `rms>0`이면 마이크 입력 경로는 살아 있다.

openWakeWord 모델 파일 경로를 환경변수로 지정한다. 여러 개면 세미콜론으로 구분한다.

```powershell
$env:KWS_MODEL_PATHS="models\stop.onnx;models\help.onnx"
.\run_kws_api.ps1
```

단발 녹음 후 감지:

```python
import requests

payload = {
    "duration_seconds": 5,
    "location": "컨베이어 1번 라인 하부",
    "line_id": "line-1",
    "force_stop": True,
    "call_rag": False
}

response = requests.post("http://localhost:8020/kws/mic/listen-once", json=payload, timeout=15)
print(response.json())
```

`KWS_MODEL_PATHS`가 비어 있으면 `/kws/mic/listen-once`는 녹음하지 않고 설정 오류를 반환한다. 모델 없이 마이크 입력만 검증할 때는 `/kws/mic/check-capture`를 사용한다.

## 물리 컨베이어가 없을 때 정지 검증

실제 컨베이어가 없어도 정지 경로는 단계적으로 검증할 수 있다.

1. `dry_run` 검증
   - `/kws/simulate`에서 `stop_command.accepted=true`가 반환되는지 확인한다.
   - `event_id`, `command_id`, timestamp를 기록해 이벤트-정지 명령 연결을 검증한다.

2. UI/Backend 검증
   - Backend가 KWS 이벤트를 받으면 대시보드에 `STOP_REQUESTED` 상태를 표시하게 한다.
   - 실제 장비 대신 화면의 컨베이어 애니메이션이나 상태값을 `running -> stopped`로 바꾼다.

3. 전기적 대체 부하 검증
   - 모터 대신 LED, 부저, 릴레이 램프, 작은 DC 팬 같은 저위험 부하를 연결한다.
   - KWS 감지 후 릴레이 접점이 열리거나 LED가 꺼지는지 확인한다.

4. 계측 검증
   - 발화 시작, KWS 감지, stop command 생성, Backend 수신 시간을 각각 timestamp로 남긴다.
   - MVP 목표는 발화 후 0.5초 이내 이벤트 생성이다.

5. 실제 컨베이어 연동 전 안전 검증
   - 기본값은 항상 fail-safe로 둔다.
   - 네트워크/RAG/LLM 실패가 정지 명령을 막지 않아야 한다.
   - 실제 릴레이/PLC 연동 전에는 전기 담당자가 비상정지 회로와 절연을 확인해야 한다.

## 다음 단계

1. `KWS_MODEL_PATHS`에 팀 KWS 모델 파일 연결
2. 연속 스트리밍 모드 추가
3. 소음 샘플에서 오탐/미탐 평가
4. Backend 이벤트 API URL 연결
5. 실제 릴레이/PLC 어댑터 추가
