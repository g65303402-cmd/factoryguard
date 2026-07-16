import { useState } from "react";
import type { DetectionEvent } from "../App";

type EventResponseProps = {
  events: DetectionEvent[];
  updateEventStatus: (id: number, newStatus: string) => void;
};

function EventResponse({ events, updateEventStatus }: EventResponseProps) {
  const [memo, setMemo] = useState("");

  const latestEvent = events[0];

  if (!latestEvent) {
    return (
      <div>
        <h1>감지 이벤트 알림 및 응답</h1>
        <p className="page-desc">
          AI가 감지한 위험 이벤트에 대해 관리자가 조치 상태를 기록합니다.
        </p>

        <section className="panel">
          <div className="alert-box normal">
            현재 응답할 감지 이벤트가 없습니다.
          </div>
        </section>
      </div>
    );
  }

  function handleStatusChange(newStatus: string) {
    updateEventStatus(latestEvent.id, newStatus);
    alert(`조치 상태가 "${newStatus}"로 변경되었습니다.`);
  }

  return (
    <div>
      <h1>감지 이벤트 알림 및 응답</h1>
      <p className="page-desc">
        AI가 감지한 위험 이벤트에 대해 관리자가 조치 상태를 기록합니다.
      </p>

      <section className="panel">
        <h2>🚨 최신 감지 이벤트</h2>

        <div className="event-info">
          <p>
            <strong>발생 시간:</strong> {latestEvent.date} {latestEvent.time}
          </p>
          <p>
            <strong>위험 유형:</strong> {latestEvent.type}
          </p>
          <p>
            <strong>위치:</strong> {latestEvent.location}
          </p>
          <p>
            <strong>위험도:</strong> {latestEvent.level}
          </p>
          <p>
            <strong>현재 조치 상태:</strong>{" "}
            <span className="response-status">{latestEvent.status}</span>
          </p>
          <p>
            <strong>감지 내용:</strong> {latestEvent.message}
          </p>
          <p>
            <strong>AI 권장 조치:</strong> 컨베이어 정지 후 관리자 확인이
            필요합니다.
          </p>
        </div>

        <div className="button-wrap">
          <button
            className="danger-btn"
            onClick={() => handleStatusChange("작업중지 처리")}
          >
            작업중지 처리
          </button>

          <button onClick={() => handleStatusChange("현장 확인 중")}>
            현장 확인 중
          </button>

          <button onClick={() => handleStatusChange("조치 완료")}>
            조치 완료
          </button>

          <button onClick={() => handleStatusChange("오탐 처리")}>
            오탐 처리
          </button>
        </div>

        <textarea
          className="memo"
          value={memo}
          onChange={(event) => setMemo(event.target.value)}
          placeholder="관리자 조치 메모를 입력하세요."
        />

        {memo && (
          <div className="alert-box normal" style={{ marginTop: "1rem" }}>
            <strong>관리자 메모</strong>
            <p>{memo}</p>
          </div>
        )}
      </section>
    </div>
  );
}

export default EventResponse;