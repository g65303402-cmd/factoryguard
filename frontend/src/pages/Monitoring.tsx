import { useRef, useState } from "react";

type MonitoringProps = {
  addEvent: (
    type: string,
    location: string,
    level: string,
    status: string,
    message: string
  ) => void;
};

function Monitoring({ addEvent }: MonitoringProps) {
  const WS_URL = "wss://factoryguard.j-jandy.com/ws/events/cam-01";

  const socketRef = useRef<WebSocket | null>(null);
  const keepAliveRef = useRef<number | null>(null);
  const previousImageUrlRef = useRef<string | null>(null);

  const [cameraOn, setCameraOn] = useState(false);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] =
    useState("CCTV 연결 대기 중");

    const [result, setResult] = useState({
      title: "현재 감지된 위험 이벤트가 없습니다.",
      message: "위험구역 침입, 비상 제스처, 쓰러짐 상태가 감지되지 않았습니다.",
      level: "normal",
    });

type BackendEvent = {
    event_id: string;
    camera_id: string;
    timestamp: string;
    event_type: string;
    severity: string;
    message: string;
    object?: {
      track_id: number;
      class: string;
      confidence: number;
      bbox?: {
        x1: number;
        y1: number;
        x2: number;
        y2: number;
      };
    };
    snapshot_url?: string;
  };
  
  function convertEventType(eventType: string) {
    if (eventType === "ppe_missing") {
      return "안전모 미착용 감지";
    }
  
    if (eventType === "conveyor_approach") {
      return "컨베이어 접근 주의";
    }
  
    if (eventType === "pinch_risk") {
      return "끼임 위험 사전 경고";
    }
  
    if (eventType === "stop_required") {
      return "AI 작업중지 권고";
    }
  
    return "AI 감지 이벤트";
  }
  
  function convertSeverity(severity: string) {
    if (severity === "low") {
      return "낮음";
    }
  
    if (severity === "medium") {
      return "중간";
    }
  
    if (severity === "high") {
      return "높음";
    }
  
    if (severity === "critical") {
      return "매우 높음";
    }
  
    return "중간";
  }
  
  function convertStatus(severity: string) {
    if (severity === "critical") {
      return "작업중지 권고";
    }
  
    if (severity === "high") {
      return "현장 확인 중";
    }
  
    return "확인 필요";
  }
  
  function convertLocation(cameraId: string) {
    if (cameraId === "cam-01") {
      return "제조 1라인 컨베이어";
    }
  
    return cameraId;
  }

  function connectCameraView() {
    if (socketRef.current) {
      return;
    }

    setConnectionStatus("CCTV 연결 시도 중...");

    const socket = new WebSocket(WS_URL);
    socket.binaryType = "blob";

    socket.onopen = () => {
      console.log("CCTV WebSocket 연결 성공");
      setCameraOn(true);
      setConnectionStatus("CCTV 연결됨");

      keepAliveRef.current = window.setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send("ping");
        }
      }, 1000);
    };

    socket.onmessage = (event) => {
      console.log("WebSocket 데이터 수신:", event.data);
    
      if (event.data instanceof Blob) {
        const imageUrl = URL.createObjectURL(event.data);
    
        if (previousImageUrlRef.current) {
          URL.revokeObjectURL(previousImageUrlRef.current);
        }
    
        previousImageUrlRef.current = imageUrl;
        setFrameUrl(imageUrl);
        setConnectionStatus("CCTV 영상 수신 중");
        return;
      }
    
      if (typeof event.data === "string") {
        try {
          const backendEvent: BackendEvent = JSON.parse(event.data);
    
          const type = convertEventType(backendEvent.event_type);
          const location = convertLocation(backendEvent.camera_id);
          const level = convertSeverity(backendEvent.severity);
          const status = convertStatus(backendEvent.severity);
          const message = backendEvent.message;
    
          addEvent(type, location, level, status, message);
    
          setResult({
            title: type,
            message,
            level:
              backendEvent.severity === "critical"
                ? "stop"
                : backendEvent.severity === "high"
                ? "danger"
                : "warning",
          });
    
          setConnectionStatus("AI 감지 이벤트 수신됨");
        } catch (error) {
          console.error("감지 이벤트 JSON 변환 오류:", error);
        }
      }
    };

    socket.onerror = (error) => {
      console.error("CCTV WebSocket 오류:", error);

      setConnectionStatus("CCTV 연결 오류");

      setResult({
        title: "⚠️ CCTV 연결 오류",
        message:
          "CCTV WebSocket 서버에 연결할 수 없습니다. 서버 주소, 인증서, camera_id, 접속 허용 설정을 확인해야 합니다.",
        level: "warning",
      });
    };

    socket.onclose = (event) => {
      console.log("CCTV WebSocket 연결 종료", event.code, event.reason);

      setCameraOn(false);
      socketRef.current = null;
      setConnectionStatus(`CCTV 연결 종료 code: ${event.code}`);

      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current);
        keepAliveRef.current = null;
      }
    };

    socketRef.current = socket;
  }

  function disconnectCameraView() {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    if (keepAliveRef.current) {
      clearInterval(keepAliveRef.current);
      keepAliveRef.current = null;
    }

    if (previousImageUrlRef.current) {
      URL.revokeObjectURL(previousImageUrlRef.current);
      previousImageUrlRef.current = null;
    }

    setFrameUrl(null);
    setCameraOn(false);
    setConnectionStatus("CCTV 연결 대기 중");
  }

  function showIntrusion() {
    const message =
      "🚨 위험구역 컨베이어 롤러 위험구역에 작업자#7 침입 감지!";
  
    setResult({
      title: "🚨 위험구역 침입",
      message,
      level: "danger",
    });
  
    addEvent(
      "위험구역 침입",
      "제조 1라인 컨베이어",
      "높음",
      "위험 발생",
      message
    );
  }
  
  function showGestureX() {
    const message = "⚠️ 작업자#7 양팔 교차 제스처 감지!";
  
    setResult({
      title: "⚠️ 양팔 X자 교차 감지",
      message,
      level: "stop",
    });
  
    addEvent(
      "양팔 X자 교차 감지",
      "제조 1라인 컨베이어",
      "매우 높음",
      "작업중지 권고",
      message
    );
  }
  
  function showGestureWave() {
    const message = "🚨 [비상정지] 작업자#7 손 흔들기 감지!";
  
    setResult({
      title: "🚨 비상정지 / 손 흔들기",
      message,
      level: "stop",
    });
  
    addEvent(
      "비상정지 / 손 흔들기",
      "제조 1라인 컨베이어",
      "매우 높음",
      "작업중지 권고",
      message
    );
  }
  
  function showFallDown() {
    const message = "🚨 [비상상황] 작업자#7 쓰러짐(낙상 사고) 감지!";
  
    setResult({
      title: "🚨 작업자 쓰러짐 / 낙상",
      message,
      level: "stop",
    });
  
    addEvent(
      "작업자 쓰러짐 / 낙상",
      "제조 1라인 컨베이어",
      "매우 높음",
      "작업중지 권고",
      message
    );
  }

  return (
    <div>
      <h1>실시간 CCTV 모니터링</h1>
      <p className="page-desc">
        컨베이어 벨트 주변 작업자의 접근 여부를 모니터링합니다.
      </p>

      <section className="panel">
        <div className="panel-header">
          <h2>제조 1라인 컨베이어</h2>

          <button
            className={cameraOn ? "camera-toggle-btn off" : "camera-toggle-btn"}
            onClick={cameraOn ? disconnectCameraView : connectCameraView}
          >
            {cameraOn ? "CCTV 연결 종료" : "CCTV 연결"}
          </button>
        </div>

        <div className="camera-area">
          {frameUrl ? (
            <img
              src={frameUrl}
              className="camera-frame"
              alt="실시간 CCTV 처리 영상"
            />
          ) : (
            <div className="camera-placeholder">
              <p className="camera-icon">📹</p>
              <p>CCTV 영상 수신 대기 중</p>
              <small>CCTV 연결을 누르면 처리된 영상이 표시됩니다.</small>
            </div>
          )}
        </div>

        <p className="cctv-status-text">{connectionStatus}</p>

        <div className="button-wrap">
  <button onClick={showIntrusion}>위험구역 침입</button>

  <button onClick={showGestureX}>양팔 X자 교차</button>

  <button className="danger-btn" onClick={showGestureWave}>
    비상정지 / 손 흔들기
  </button>

  <button className="danger-btn" onClick={showFallDown}>
    작업자 쓰러짐 / 낙상
  </button>
</div>
      </section>

      <section className="panel">
        <h2>현재 감지 결과</h2>

        <div className={`alert-box ${result.level}`}>
          <strong>{result.title}</strong>
          <p>{result.message}</p>
        </div>
      </section>
    </div>
  );
}

export default Monitoring;