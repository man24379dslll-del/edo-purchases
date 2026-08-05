import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDate } from "../format";

export default function HistoryPanel({ entityId }) {
  const [rows, setRows] = useState(null);

  useEffect(() => {
    api.log(entityId).then(setRows).catch(() => setRows([]));
  }, [entityId]);

  if (!rows) return <div className="loading">Загрузка истории...</div>;
  if (!rows.length) return <div className="empty-state">Записей пока нет</div>;

  return (
    <div className="trail">
      {rows.map((r, i) => (
        <div className="trail-item" key={i}>
          <span className="trail-dot dot-approved"></span>
          <span style={{ color: "var(--text-3)", minWidth: 130 }}>{fmtDate(r.date)}</span>
          <b>{r.user}</b>
          {r.role && <span style={{ color: "var(--text-3)" }}>({r.role})</span>}
          <span>{r.action}</span>
          {r.comment && <span style={{ marginLeft: "auto", color: "var(--text-3)" }}>«{r.comment}»</span>}
        </div>
      ))}
    </div>
  );
}
