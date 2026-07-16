type SidebarProps = {
  setPage: (page: string) => void;
  currentPage: string;
};

function Sidebar({ setPage, currentPage }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h2>LineShield</h2>
        <p>Conveyor Safety AI</p>
      </div>

      <div className="sidebar-menu">
        <button
          className={currentPage === "dashboard" ? "active" : ""}
          onClick={() => setPage("dashboard")}
        >
          📊 대시보드
        </button>

        <button
          className={currentPage === "monitoring" ? "active" : ""}
          onClick={() => setPage("monitoring")}
        >
          📹 CCTV 모니터링
        </button>

        <button
          className={currentPage === "event" ? "active" : ""}
          onClick={() => setPage("event")}
        >
          🚨 이벤트 응답
        </button>

        <button
          className={currentPage === "history" ? "active" : ""}
          onClick={() => setPage("history")}
        >
          📋 감지 이력
        </button>

        <button
          className={currentPage === "report" ? "active" : ""}
          onClick={() => setPage("report")}
        >
          📄 사후 리포트
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;