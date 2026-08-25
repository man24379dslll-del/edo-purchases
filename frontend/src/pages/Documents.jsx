import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import { fmtDate } from "../format";

function fmtSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export default function Documents() {
  const { user } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");

  function load() {
    api.documents({ q }).then(setRows).catch(() => setRows([]));
  }

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [q]);

  async function remove(doc) {
    if (!confirm(`Удалить файл «${doc.original_name}»? Это действие необратимо.`)) return;
    try {
      await api.removeDocument(doc.id);
      toast("✓ Файл удалён");
      load();
    } catch (e) {
      toast(e.message, true);
    }
  }

  // Группируем документы по договору, к которому они привязаны;
  // непривязанные ("ничейные") файлы собираем в отдельную группу внизу.
  const groups = useMemo(() => {
    if (!rows) return [];
    const map = new Map();
    for (const d of rows) {
      const key = d.entity_id || "__unlinked__";
      if (!map.has(key)) {
        map.set(key, {
          entityId: d.entity_id,
          subject: d.entity_subject || (d.entity_id ? d.entity_id : "Не привязано к договору"),
          docs: [],
        });
      }
      map.get(key).docs.push(d);
    }
    const list = Array.from(map.values());
    list.sort((a, b) => {
      if (!a.entityId) return 1;
      if (!b.entityId) return -1;
      return new Date(b.docs[0].uploaded_at) - new Date(a.docs[0].uploaded_at);
    });
    return list;
  }, [rows]);

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

      {!rows && <div className="loading">Загрузка...</div>}
      {rows && groups.length === 0 && <div className="empty-state">Документов не найдено</div>}

      {groups.map((g) => (
        <div className="card" key={g.entityId || "unlinked"}>
          <div className="card-header">
            <div className="card-title">
              {g.entityId ? (
                <Link to={`/contracts/${g.entityId}`}>📄 {g.subject}</Link>
              ) : (
                <span style={{ color: "var(--text-3)" }}>🗂️ Не привязано к договору</span>
              )}
            </div>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>{g.docs.length} файл(ов)</span>
          </div>
          <table>
            <thead><tr><th>Файл</th><th>Тип</th><th>Размер</th><th>Загрузил</th><th>Когда</th><th></th></tr></thead>
            <tbody>
              {g.docs.map((d) => (
                <tr key={d.id} style={{ cursor: "default" }}>
                  <td>📎 {d.original_name}</td>
                  <td>{d.doc_type ? <span className="badge b-p">{d.doc_type}</span> : "—"}</td>
                  <td>{fmtSize(d.size_bytes)}</td>
                  <td>{d.uploaded_by || "—"}</td>
                  <td>{fmtDate(d.uploaded_at)}</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <a href={d.url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-xs">Открыть</a>
                    {(user.email === d.uploaded_by || user.role === "Директор" || user.role === "Админ") && (
                      <button className="btn btn-danger btn-xs" onClick={() => remove(d)}>Удалить</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
