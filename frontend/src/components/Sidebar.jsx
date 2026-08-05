import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/", icon: "📊", label: "Дашборд", roles: null },
  { to: "/approvals", icon: "✅", label: "Мои согласования", roles: null, badge: true },
  { to: "/delegations", icon: "🔁", label: "Делегирование", roles: null },
  { to: "/contracts", icon: "📄", label: "Договоры", roles: null },
  { to: "/purchases", icon: "🛒", label: "Закупки", roles: null },
  { to: "/osv", icon: "📈", label: "ОСВ", roles: ["Фин. директор", "Админ"] },
  { to: "/admin", icon: "⚙️", label: "Администрирование", roles: ["Директор", "Админ"] },
];

export default function Sidebar({ pendingCount }) {
  const { user, logout } = useAuth();

  return (
    <aside className="sidebar">
      <div className="sb-logo">
        <div className="sb-logo-icon">📋</div>
        <div>
          <div className="sb-logo-name">ЭДО Закупок</div>
          <div className="sb-logo-sub">v5 · cloud</div>
        </div>
      </div>

      <div className="sb-user">
        <div className="sb-avatar">{(user?.fio || "?").slice(0, 1).toUpperCase()}</div>
        <div>
          <div className="sb-user-name">{user?.fio}</div>
          <div className="sb-user-role">{user?.role}</div>
        </div>
      </div>

      <nav className="sb-nav">
        {NAV.filter((n) => !n.roles || n.roles.includes(user?.role)).map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => `sb-item ${isActive ? "active" : ""}`}>
            <span className="sb-icon">{n.icon}</span>
            <span>{n.label}</span>
            {n.badge && pendingCount > 0 && <span className="sb-badge">{pendingCount}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sb-bottom">
        <button className="sb-logout" onClick={logout}>Выйти</button>
      </div>
    </aside>
  );
}
