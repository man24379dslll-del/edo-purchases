import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { type: "single", to: "/", icon: "📊", label: "Дашборд", roles: null },
  { type: "single", to: "/approvals", icon: "✅", label: "Мои согласования", roles: null, badge: true, excludeRoles: ["Контрагент"] },
  {
    type: "group", key: "docs", icon: "📁", label: "Документы", roles: null,
    children: [
      { to: "/contracts", icon: "📄", label: "Договоры" },
      { to: "/documents", icon: "🗂️", label: "Хранилище документов" },
    ],
  },
  {
    type: "group", key: "finance", icon: "💰", label: "Финансы", roles: ["Директор", "Бухгалтер", "Админ"],
    children: [
      { to: "/payments", icon: "💳", label: "Платёжный календарь" },
    ],
  },
  {
    type: "group", key: "admin", icon: "⚙️", label: "Администрирование", roles: ["Директор", "Админ"],
    children: [
      { to: "/admin", icon: "👥", label: "Пользователи и юрлица" },
    ],
  },
];

export default function Sidebar({ pendingCount }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  const visible = NAV.filter((n) =>
    (!n.roles || n.roles.includes(user?.role)) && !(n.excludeRoles || []).includes(user?.role));

  const activeGroupKey = visible.find((n) => n.type === "group" &&
    n.children.some((c) => location.pathname.startsWith(c.to)))?.key;
  const [openGroup, setOpenGroup] = useState(activeGroupKey || null);

  return (
    <aside className="sidebar">
      <div className="sb-logo">
        <div className="sb-logo-icon">📋</div>
        <div>
          <div className="sb-logo-name">ЭДО Договоров</div>
          <div className="sb-logo-sub">cloud</div>
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
        {visible.map((n) => {
          if (n.type === "single") {
            return (
              <NavLink key={n.to} to={n.to} end={n.to === "/"} className={({ isActive }) => `sb-item ${isActive ? "active" : ""}`}>
                <span className="sb-icon">{n.icon}</span>
                <span>{n.label}</span>
                {n.badge && pendingCount > 0 && <span className="sb-badge">{pendingCount}</span>}
              </NavLink>
            );
          }
          const isOpen = openGroup === n.key;
          const groupActive = n.children.some((c) => location.pathname.startsWith(c.to));
          return (
            <div key={n.key}>
              <div
                className={`sb-item sb-group-header ${groupActive ? "active" : ""}`}
                onClick={() => setOpenGroup(isOpen ? null : n.key)}
              >
                <span className="sb-icon">{n.icon}</span>
                <span>{n.label}</span>
                <span className={`sb-chevron ${isOpen ? "open" : ""}`}>›</span>
              </div>
              {isOpen && (
                <div className="sb-subnav">
                  {n.children.map((c) => (
                    <NavLink key={c.to} to={c.to} className={({ isActive }) => `sb-subitem ${isActive ? "active" : ""}`}>
                      <span className="sb-icon">{c.icon}</span>
                      <span>{c.label}</span>
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="sb-bottom">
        <button className="sb-logout" onClick={logout}>Выйти</button>
      </div>
    </aside>
  );
}
