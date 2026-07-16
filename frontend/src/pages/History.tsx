import type { DetectionEvent } from "../App";

type HistoryProps = {
  events: DetectionEvent[];
};

function History({ events }: HistoryProps) {

  return (
    <div>
      <h1>감지 이력</h1>
      <p className="page-desc">
        CCTV 모니터링에서 감지된 위험 이벤트 이력을 확인합니다.
      </p>



      <section className="panel">
  <h2>전체 감지 이력</h2>

        {events.length === 0 ? (
          <p className="page-desc">아직 감지된 이벤트가 없습니다.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>날짜</th>
                <th>시간</th>
                <th>위험 유형</th>
                <th>위치</th>
                <th>위험도</th>
                <th>조치 상태</th>
              </tr>
            </thead>

            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.date}</td>
                  <td>{event.time}</td>
                  <td>{event.type}</td>
                  <td>{event.location}</td>
                  <td>{event.level}</td>
                  <td>{event.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default History;