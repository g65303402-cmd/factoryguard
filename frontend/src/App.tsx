import { useState } from "react";
import "./App.css";

import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Monitoring from "./pages/Monitoring";
import EventResponse from "./pages/EventResponse";
import History from "./pages/History";
import Report from "./pages/Report";

export type DetectionEvent = {
  id: number;
  date: string;
  time: string;
  type: string;
  location: string;
  level: string;
  status: string;
  message: string;
};

function App() {
  const [page, setPage] = useState("dashboard");
  const [events, setEvents] = useState<DetectionEvent[]>([]);

  function getTodayDate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const date = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${date}`;
  }

  function getCurrentTime() {
    const now = new Date();
    const hour = String(now.getHours()).padStart(2, "0");
    const minute = String(now.getMinutes()).padStart(2, "0");
    return `${hour}:${minute}`;
  }

  function addEvent(
    type: string,
    location: string,
    level: string,
    status: string,
    message: string
  ) {
    const newEvent: DetectionEvent = {
      id: Date.now(),
      date: getTodayDate(),
      time: getCurrentTime(),
      type,
      location,
      level,
      status,
      message,
    };

    setEvents((prevEvents) => [newEvent, ...prevEvents]);
  }

  function updateEventStatus(id: number, newStatus: string) {
    setEvents((prevEvents) =>
      prevEvents.map((event) =>
        event.id === id ? { ...event, status: newStatus } : event
      )
    );
  }

  return (
    <div className="app">
      <Sidebar setPage={setPage} currentPage={page} />

      <main className="main-content">
        {page === "dashboard" && <Dashboard events={events} />}
        {page === "monitoring" && <Monitoring addEvent={addEvent} />}
        {page === "event" && (
          <EventResponse
            events={events}
            updateEventStatus={updateEventStatus}
          />
        )}
        {page === "history" && <History events={events} />}
        {page === "report" && <Report events={events} />}
      </main>
    </div>
  );
}

export default App;