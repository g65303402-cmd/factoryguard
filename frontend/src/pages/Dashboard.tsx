import type { DetectionEvent } from "../App";

type DashboardProps = {
  events: DetectionEvent[];
};

function Dashboard({ events }: DashboardProps) {
  const intrusionCount = events.filter((event) =>
    event.type.includes("위험구역 침입")
  ).length;

  const gestureXCount = events.filter((event) =>
    event.type.includes("양팔 X자 교차")
  ).length;

  const gestureWaveCount = events.filter((event) =>
    event.type.includes("비상정지")
  ).length;

  const fallDownCount = events.filter(
    (event) => event.type.includes("쓰러짐") || event.type.includes("낙상")
  ).length;

  return (
    <div>
      <h1>관리자 대시보드</h1>
      <p className="page-desc">
        컨베이어 주변 위험구역 침입, 비상 제스처, 낙상 감지 현황을
        확인합니다.
      </p>

      <div className="cards">
        <div className="card">
          <h2>{events.length}</h2>
          <p>전체 감지 이벤트</p>
          <span>📊</span>
        </div>

        <div className="card">
          <h2>{intrusionCount}</h2>
          <p>위험구역 침입</p>
          <span>🚨</span>
        </div>

        <div className="card">
          <h2>{gestureXCount}</h2>
          <p>양팔 X자 교차</p>
          <span>⚠️</span>
        </div>

        <div className="card">
          <h2>{gestureWaveCount}</h2>
          <p>비상정지 / 손 흔들기</p>
          <span>🛑</span>
        </div>

        <div className="card">
          <h2>{fallDownCount}</h2>
          <p>작업자 쓰러짐 / 낙상</p>
          <span>🚑</span>
        </div>
      </div>

      <section className="panel">
        <h2>최근 감지 이력</h2>

        {events.length === 0 ? (
          <p className="page-desc">아직 감지된 이벤트가 없습니다.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>시간</th>
                <th>위험 유형</th>
                <th>위치</th>
                <th>위험도</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 5).map((event) => (
                <tr key={event.id}>
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

      <section className="panel">
        <h2>위험 유형별 통계</h2>

        <div className="stat-row">
          <p>위험구역 침입</p>
          <div className="bar">
            <span>{intrusionCount}건</span>
          </div>
        </div>

        <div className="stat-row">
          <p>양팔 X자 교차</p>
          <div className="bar">
            <span>{gestureXCount}건</span>
          </div>
        </div>

        <div className="stat-row">
          <p>비상정지 / 손 흔들기</p>
          <div className="bar danger">
            <span>{gestureWaveCount}건</span>
          </div>
        </div>

        <div className="stat-row">
          <p>작업자 쓰러짐 / 낙상</p>
          <div className="bar danger">
            <span>{fallDownCount}건</span>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Dashboard;