import { useState } from "react";

export default function Tabs({ tabs }) {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)", marginBottom: 18 }}>
        {tabs.map((t, i) => (
          <button
            key={t.label}
            onClick={() => setActive(i)}
            style={{
              background: "none", border: "none", cursor: "pointer",
              padding: "10px 16px", fontSize: 13, fontWeight: 600,
              color: active === i ? "var(--accent)" : "var(--text-3)",
              borderBottom: active === i ? "2px solid var(--accent)" : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div>{tabs[active].content}</div>
    </div>
  );
}
