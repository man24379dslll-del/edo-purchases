import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import { api } from "../api";

const TITLES = {
  "/": ["Дашборд", "Обзор по договорам"],
  "/approvals": ["Мои согласования", "Договоры, ожидающие вашего решения"],
  "/contracts": ["Договоры", "Реестр договоров"],
  "/documents": ["Хранилище документов", "Все загруженные файлы в одном месте"],
  "/admin": ["Администрирование", "Пользователи и юрлица"],
};

export default function Layout() {
  const location = useLocation();
  const [pendingCount, setPendingCount] = useState(0);

  async function refreshPending() {
    try {
      const rows = await api.myApprovals();
      setPendingCount(rows.length);
    } catch (_) {}
  }

  useEffect(() => {
    refreshPending();
    const id = setInterval(refreshPending, 30000);
    return () => clearInterval(id);
  }, []);

  const base = "/" + (location.pathname.split("/")[1] || "");
  const [title, sub] = TITLES[base] || TITLES["/"];

  return (
    <div className="app-shell">
      <Sidebar pendingCount={pendingCount} />
      <div className="main">
        <div className="topbar">
          <div>
            <div className="topbar-title">{title}</div>
            <div className="topbar-sub">{sub}</div>
          </div>
        </div>
        <div className="content">
          <Outlet context={{ refreshPending }} />
        </div>
      </div>
    </div>
  );
}
