import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../format";

function fmtSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export default function Documents() {
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");

  function load() {
    api.documents({ q }).then(setRows).catch(() => setRows([]));
  }

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div>
      <div className="top-actions" style={{ marginBottom: 16 }}>
        <input
          placeholder="Поиск по имени файла, договору, кто загрузил..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 300, padding: "9px 12px", border: "1px solid var(--border-s)", borderRadius: 8 }}
        />
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Файл</th><th>Относится к договору</th><th>Размер</th><th>Загрузил</th><th>Когда</th><th></th>
            </tr>
          </thead>
          <tbody>
            {!rows && <tr><td colSpan={6} className="et">Загрузка...</td></tr>}
            {rows && rows.length === 0 && <tr><td colSpan={6} className="et">Документов не найдено</td></tr>}
            {rows && rows.map((d) => (
              <tr key={d.id} style={{ cursor: "default" }}>
                <td>📎 {d.original_name}</td>
                <td>
                  {d.entity_id ? (
                    <Link to={`/contracts/${d.entity_id}`}>{d.entity_subject || d.entity_id}</Link>
                  ) : (
                    <span style={{ color: "var(--text-3)" }}>не привязан</span>
                  )}
                </td>
                <td>{fmtSize(d.size_bytes)}</td>
                <td>{d.uploaded_by || "—"}</td>
                <td>{fmtDate(d.uploaded_at)}</td>
                <td><a href={d.url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-xs">Открыть</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
