import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import { fmtDate } from "../format";

const ENTITY_LABEL = { contract: "Договор", purchase: "Закупка", amendment: "Доп. соглашение" };
const ENTITY_ROUTE = { contract: "contracts", purchase: "purchases", amendment: "contracts" };

export default function Approvals() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const [comment, setComment] = useState({});
  const [selected, setSelected] = useState({});
  const [bulkComment, setBulkComment] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const { refreshPending } = useOutletContext();

  function load() {
    api.myApprovals().then((r) => { setRows(r); setSelected({}); }).catch(() => setRows([]));
  }

  useEffect(load, []);

  async function runOverdueCheck() {
    try {
      const res = await api.checkOverdue();
      toast(res.escalatedCount > 0 ? `⚠ Эскалировано просроченных этапов: ${res.escalatedCount}` : "Просроченных этапов нет");
      load();
    } catch (e) {
      toast(e.message, true);
    }
  }

  const key = (r) => `${r.entityType}:${r.entityId}`;
  const selectedRows = rows ? rows.filter((r) => selected[key(r)]) : [];

  function toggle(r) {
    setSelected({ ...selected, [key(r)]: !selected[key(r)] });
  }
  function toggleAll() {
    if (selectedRows.length === rows.length) setSelected({});
    else setSelected(Object.fromEntries(rows.map((r) => [key(r), true])));
  }

  async function decide(row, decision) {
    try {
      await api.decide({
        entity_type: row.entityType,
        entity_id: row.entityId,
        decision,
        comment: comment[row.entityId] || "",
      });
      toast(decision === "Согласовано" ? "✓ Согласовано" : "✓ Отклонено");
      load();
      refreshPending();
    } catch (e) {
      toast(e.message, true);
    }
  }

  async function decideBulk(decision) {
    if (!selectedRows.length) return;
    if (decision === "Отклонено" && !confirm(`Отклонить ${selectedRows.length} документ(ов)?`)) return;
    setBusy(true);
    try {
      const res = await api.decideBulk({
        items: selectedRows.map((r) => ({ entity_type: r.entityType, entity_id: r.entityId })),
        decision,
        comment: bulkComment,
      });
      const failed = res.results.filter((r) => !r.ok);
      if (failed.length) toast(`Готово с ошибками: ${failed.length} из ${res.results.length} не удалось`, true);
      else toast(`✓ Обработано документов: ${res.results.length}`);
      setBulkComment("");
      load();
      refreshPending();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  if (!rows) return <div className="loading">Загрузка...</div>;

  return (
    <div>
      {user.role === "Директор" && (
        <div className="top-actions" style={{ marginBottom: 12, justifyContent: "flex-end" }}>
          <button className="btn btn-ghost btn-xs" onClick={runOverdueCheck}>⏱ Проверить просроченные по SLA</button>
        </div>
      )}

      {rows.length === 0 && <div className="empty-state">Нет документов, ожидающих вашего решения 🎉</div>}

      {rows.length > 0 && (
        <div className="card" style={{ padding: "12px 20px", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <input type="checkbox" checked={selectedRows.length === rows.length} onChange={toggleAll} style={{ width: "auto" }} />
            Выбрать все ({rows.length})
          </label>
          {selectedRows.length > 0 && (
            <>
              <input
                placeholder="Общий комментарий (необязательно)"
                value={bulkComment}
                onChange={(e) => setBulkComment(e.target.value)}
                style={{ flex: 1, minWidth: 200, padding: "7px 10px", border: "1px solid var(--border-s)", borderRadius: 8 }}
              />
              <button className="btn btn-approve btn-xs" disabled={busy} onClick={() => decideBulk("Согласовано")}>
                ✓ Согласовать выбранные ({selectedRows.length})
              </button>
              <button className="btn btn-danger btn-xs" disabled={busy} onClick={() => decideBulk("Отклонено")}>
                ✕ Отклонить выбранные
              </button>
            </>
          )}
        </div>
      )}

      {rows.map((r) => (
        <div className="card" key={key(r)}>
          <div className="card-header">
            <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input type="checkbox" checked={!!selected[key(r)]} onChange={() => toggle(r)} style={{ width: "auto" }} />
              <div>
                <div className="card-title">
                  <Link to={`/${ENTITY_ROUTE[r.entityType]}/${r.entityId}`} style={{ color: "inherit", textDecoration: "none" }}>
                    {ENTITY_LABEL[r.entityType]} · {r.entityId}
                  </Link>
                  {r.overdue && <span className="badge b-rejected" style={{ marginLeft: 8 }}>Просрочено</span>}
                  {r.isDelegated && <span className="badge b-p" style={{ marginLeft: 8 }}>За {r.actingAsRole}</span>}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
                  {r.subject} · инициатор {r.initiatorFio} · {fmtDate(r.createdAt)}
                  {r.deadline && <> · дедлайн {fmtDate(r.deadline)}</>}
                </div>
              </div>
            </label>
            <Link to={`/${ENTITY_ROUTE[r.entityType]}/${r.entityId}`} className="btn btn-ghost btn-xs">Открыть документ</Link>
          </div>
          <div className="card-body">
            <div className="field">
              <label>Комментарий (необязательно)</label>
              <textarea
                rows={2}
                value={comment[r.entityId] || ""}
                onChange={(e) => setComment({ ...comment, [r.entityId]: e.target.value })}
              />
            </div>
            <div className="top-actions">
              <button className="btn btn-approve" onClick={() => decide(r, "Согласовано")}>✓ Согласовать</button>
              <button className="btn btn-danger" onClick={() => decide(r, "Отклонено")}>✕ Отклонить</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
