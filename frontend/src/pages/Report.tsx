import type { DetectionEvent } from "../App";

type ReportProps = {
  events: DetectionEvent[];
};

function Report({ events }: ReportProps) {
  const latestEvent = events[0];

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

  function printReport() {
    window.print();
  }

  return (
    <div>
      <div className="report-toolbar">
        <button className="pdf-print-btn" onClick={printReport}>
          <span>📄</span>
          PDF로 저장 / 인쇄
        </button>
      </div>

      <section className="report-page">
        <h1>AI 안전 감지 사후 리포트</h1>

        <p className="report-subtitle">
          CCTV 기반 위험구역 침입, 비상 제스처, 작업자 쓰러짐 감지 이벤트에
          대한 관리자 조치 리포트입니다.
        </p>

        <div className="report-info-grid">
          <div>
            <strong>리포트 생성일</strong>
            <p>{new Date().toLocaleDateString()}</p>
          </div>

          <div>
            <strong>감지 위치</strong>
            <p>{latestEvent ? latestEvent.location : "제조 1라인 컨베이어"}</p>
          </div>

          <div>
            <strong>총 감지 건수</strong>
            <p>{events.length}건</p>
          </div>

          <div>
            <strong>최신 조치 상태</strong>
            <p>{latestEvent ? latestEvent.status : "감지 이벤트 없음"}</p>
          </div>
        </div>

        <div className="report-section">
          <h2>1. 감지 이벤트 요약</h2>

          {latestEvent ? (
            <div className="report-highlight">
              <p>
                <strong>최신 감지 유형:</strong> {latestEvent.type}
              </p>
              <p>
                <strong>위험도:</strong> {latestEvent.level}
              </p>
              <p>
                <strong>감지 시간:</strong> {latestEvent.date} {latestEvent.time}
              </p>
              <p>
                <strong>감지 내용:</strong> {latestEvent.message}
              </p>
            </div>
          ) : (
            <p>아직 감지된 위험 이벤트가 없습니다.</p>
          )}
        </div>

        <div className="report-section">
          <h2>2. 위험 유형별 통계</h2>

          <table>
            <thead>
              <tr>
                <th>위험 유형</th>
                <th>감지 건수</th>
                <th>설명</th>
              </tr>
            </thead>

            <tbody>
              <tr>
                <td>위험구역 침입</td>
                <td>{intrusionCount}건</td>
                <td>
                  작업자의 발끝 점 또는 신체 관절 선이 지정된 위험구역에
                  진입하거나 경계선을 교차한 경우
                </td>
              </tr>

              <tr>
                <td>양팔 X자 교차 감지</td>
                <td>{gestureXCount}건</td>
                <td>
                  작업자가 양손목을 어깨 높이 부근에서 X자로 교차한 경우
                </td>
              </tr>

              <tr>
                <td>비상정지 / 손 흔들기</td>
                <td>{gestureWaveCount}건</td>
                <td>
                  작업자가 어깨 위로 손을 올리고 좌우로 격렬하게 흔든 경우
                </td>
              </tr>

              <tr>
                <td>작업자 쓰러짐 / 낙상</td>
                <td>{fallDownCount}건</td>
                <td>
                  작업자의 자세가 수평에 가깝게 유지되어 쓰러짐 또는 낙상
                  상황으로 판단된 경우
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="report-section">
          <h2>3. AI 분석 결과</h2>

          <p>
            본 시스템은 CCTV 영상에서 작업자의 자세, 관절 위치, 위험구역
            진입 여부, 비상 제스처, 쓰러짐 상태를 분석하여 위험 이벤트를
            감지합니다.
          </p>

          <p>
            감지 이벤트는 위험도에 따라 낮음, 중간, 높음, 매우 높음으로
            분류되며, 매우 높은 위험도에서는 즉각적인 현장 확인 및 작업중지
            권고가 필요합니다.
          </p>
        </div>

        <div className="report-section">
          <h2>4. 관리자 조치 내역</h2>

          {events.length === 0 ? (
            <p>기록된 관리자 조치 내역이 없습니다.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>시간</th>
                  <th>위험 유형</th>
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
                    <td>{event.level}</td>
                    <td>{event.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="report-section">
          <h2>5. 재발 방지 권고사항</h2>

          <ul className="report-list">
            <li>컨베이어 주변 위험구역을 명확히 표시하고 접근 제한선을 유지합니다.</li>
            <li>작업자에게 비상정지 제스처와 위험상황 신고 절차를 교육합니다.</li>
            <li>위험구역 침입 이벤트가 반복되는 구간은 CCTV 각도와 위험구역 설정을 재점검합니다.</li>
            <li>쓰러짐 또는 낙상 감지 발생 시 즉시 현장 확인 및 응급 대응 절차를 수행합니다.</li>
            <li>감지 이력과 조치 상태를 주기적으로 검토하여 반복 위험요인을 개선합니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

export default Report;