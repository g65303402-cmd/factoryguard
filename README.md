# Camera Agent

로컬 웹캠 영상을 AI 서버로 전송하는 Camera Agent입니다.

웹캠에서 영상을 읽어 JPEG로 압축한 후 WebSocket을 통해 AI 서버로 스트리밍합니다.

---

## 요구사항

- Python 3.10 이상
- 웹캠
- 인터넷 연결

---

## 설치

### 1. 저장소 다운로드

```bash
git clone https://github.com/g65303402-cmd/factoryguard.git
cd camera-agent
```

### 2. 가상환경 생성 (권장)

Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

requirements.txt 예시

```txt
opencv-python
websockets
```

---

## 실행

기본 실행

```bash
python camera_agent.py
```

기본값

| 옵션 | 값 |
|-------|----|
| Server | wss://ai.j-jandy.com |
| Camera ID | cam-01 |
| Camera Index | 0 |
| FPS | 5 |
| Resolution | 640x480 |

---

## 실행 옵션

```bash
python camera_agent.py \
    --server wss://ai.j-jandy.com \
    --camera-id cam-01 \
    --camera-index 0 \
    --fps 5 \
    --width 640 \
    --height 480
```

### 옵션 설명

| 옵션 | 설명 | 기본값 |
|-------|------|--------|
| `--server` | AI 서버 주소 | `wss://ai.j-jandy.com` |
| `--camera-id` | 카메라 식별 ID | `cam-01` |
| `--camera-index` | 사용할 웹캠 번호 | `0` |
| `--fps` | 전송 FPS | `5` |
| `--width` | 영상 너비 | `640` |
| `--height` | 영상 높이 | `480` |

---

## 여러 대의 카메라 사용

카메라마다 서로 다른 Camera ID를 사용해야 합니다.

예시

PC 1

```bash
python camera_agent.py --camera-id cam-01
```

PC 2

```bash
python camera_agent.py --camera-id cam-02
```

PC 3

```bash
python camera_agent.py --camera-id warehouse-01
```

---

## 여러 개의 웹캠이 있는 경우

웹캠 번호를 변경합니다.

첫 번째 웹캠

```bash
python camera_agent.py --camera-index 0
```

두 번째 웹캠

```bash
python camera_agent.py --camera-index 1
```

세 번째 웹캠

```bash
python camera_agent.py --camera-index 2
```

---

## 정상 실행 예시

```text
AI 서버 연결 시도: wss://ai.j-jandy.com/ws/cameras/cam-01
서버 응답: {"status":"registered","camera_id":"cam-01"}
```

---

## 오류 해결

### 웹캠을 열 수 없습니다.

```
웹캠을 열 수 없습니다.
```

확인 사항

- 다른 프로그램(Zoom, Teams 등)이 웹캠을 사용 중인지 확인
- `--camera-index` 값을 변경
- 웹캠이 정상 연결되어 있는지 확인

---

### 서버 연결 실패

```
연결 오류
```

확인 사항

- 인터넷 연결
- 서버 주소 확인
- AI 서버가 실행 중인지 확인

---

### Camera ID 중복

동일한 Camera ID를 여러 대에서 사용할 경우 충돌이 발생할 수 있습니다.

각 PC마다 다른 Camera ID를 사용하세요.

예시

```
cam-01
cam-02
cam-03
factory-a
factory-b
```

---

## 네트워크 구조

```
┌──────────────┐
│ Local Webcam │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ Camera Agent     │
│ OpenCV           │
└──────┬───────────┘
       │ JPEG
       ▼
WebSocket (WSS)
       │
       ▼
┌──────────────────┐
│ AI Server        │
│ Detection        │
│ Tracking         │
│ Event Processing │
└──────────────────┘
```

---

## 종료

프로그램은 `Ctrl + C`를 눌러 종료할 수 있습니다.