import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { fmtDate, fmtMoney } from "../format";

export default function Approvals() {
  const [rows, setRows] = useState(null);
  const [comment, setComment] = useState({});
  const [busy, setBusy] = useState({});
  const toast = useToast();
  const { refreshPending } = useOutletContext();

  function load() {
    api.myApprovals().then(setRows).catch(() => setRows([]));
  }
  useEffect(load, []);

  async function decide(row, decision, standard) {
    setBusy({ ...busy, [row.contractId]: true });
    try {
      await api.decide({
        contract_id: row.contractId,
        decision,
        standard,
        comment: comment[row.contractId] || "",
      });
      toast(decision === "Согласовано" ? "✓ Согласовано" : "✓ Отклонено");
      load();
      refreshPending();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy({ ...busy, [row.contractId]: false });
    }
  }

  if (!rows) return <div className="loading">Загрузка...</div>;

  return (
    <div>
      {rows.length === 0 && <div className="empty-state">Нет договоров, ожидающих вашего решения 🎉</div>}

      {rows.map((r) => (
        <div className="card" key={r.contractId}>
          <div className="card-header">
            <div>
              <div className="card-title">
                <Link to={`/contracts/${r.contractId}`} style={{ color: "inherit", textDecoration: "none" }}>
                  Договор {r.contractId}
                </Link>
                {r.isDirectorFinal && <span className="badge b-p" style={{ marginLeft: 8 }}>Финальная подпись</span>}
              </div>
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
                {r.subject} · {r.contractorName} · {fmtMoney(r.pricePerUnit)} ₽ за ед. ·
                инициатор {r.initiatorFio} · {fmtDate(r.createdAt)}
              </div>
            </div>
          </div>
          <div className="card-body">
            <div className="field">
              <label>Комментарий (необязательно)</label>
              <textarea
                rows={2}
                value={comment[r.contractId] || ""}
                onChange={(e) => setComment({ ...comment, [r.contractId]: e.target.value })}
              />
            </div>

            {r.isDirectorReview ? (
              <div className="top-actions">
                <button className="btn btn-approve" disabled={busy[r.contractId]}
                  onClick={() => decide(r, "Согласовано", true)}>
                  ✓ Стандартный — согласовать
                </button>
                <button className="btn btn-primary" disabled={busy[r.contractId]}
                  onClick={() => decide(r, "Согласовано", false)}>
                  → Отправить Юристу и Бухгалтеру
                </button>
                <button className="btn btn-danger" disabled={busy[r.contractId]}
                  onClick={() => decide(r, "Отклонено")}>
                  ✕ Отклонить
                </button>
              </div>
            ) : (
              <div className="top-actions">
                <button className="btn btn-approve" disabled={busy[r.contractId]}
                  onClick={() => decide(r, "Согласовано")}>
                  ✓ Согласовать
                </button>
                <button className="btn btn-danger" disabled={busy[r.contractId]}
                  onClick={() => decide(r, "Отклонено")}>
                  ✕ Отклонить
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
