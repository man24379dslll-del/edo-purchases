import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

const TITLES = {
  "/": ["Дашборд", "Обзор по договорам"],
  "/approvals": ["Мои согласования", "Договоры, ожидающие вашего решения"],
  "/contracts": ["Договоры", "Реестр договоров"],
  "/documents": ["Хранилище документов", "Все загруженные файлы в одном месте"],
  "/payments": ["Платёжный календарь", "Плановые и фактические платежи по договорам"],
  "/admin": ["Администрирование", "Пользователи и юрлица"],
};

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);
  const [search, setSearch] = useState("");

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

  function submitSearch(e) {
    e.preventDefault();
    if (search.trim()) navigate(`/contracts?q=${encodeURIComponent(search.trim())}`);
  }

  return (
    <div className="app-shell">
      <Sidebar pendingCount={pendingCount} />
      <div className="main">
        <div className="topbar topbar-tall">
          <div>
            <div className="topbar-title">{title}</div>
            <div className="topbar-sub">{sub}</div>
          </div>
          <form className="topbar-search" onSubmit={submitSearch}>
            <span className="topbar-search-icon">🔍</span>
            <input
              placeholder="Поиск по договорам: номер, контрагент, предмет..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </form>
          {user.role !== "Контрагент" && (
            <button className="btn btn-primary" onClick={() => navigate("/contracts?create=1")}>
              + Новый договор
            </button>
          )}
        </div>
        <div className="content">
          <Outlet context={{ refreshPending }} />
        </div>
      </div>
    </div>
  );
}
