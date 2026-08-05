import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import ApprovalTrail from "../components/ApprovalTrail";
import FilePreview from "../components/FilePreview";
import HistoryPanel from "../components/HistoryPanel";
import Tabs from "../components/Tabs";
import { fmtDate, fmtMoney, statusBadgeClass } from "../format";

export default function ContractDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { refreshPending } = useOutletContext();
  const [data, setData] = useState(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [showRework, setShowRework] = useState(false);
  const [reworkForm, setReworkForm] = useState({ subject: "", comment: "" });

  function load() {
    api.contract(id).then((d) => {
      setData(d);
      setReworkForm({ subject: d.contract.subject, comment: "" });
    }).catch((e) => toast(e.message, true));
  }
  useEffect(load, [id]);

  if (!data) return <div className="loading">Загрузка...</div>;

  const { contract, items, approvals } = data;
  const myTurn = approvals.some((a) => a.state === "active" && a.role === user.role);
  const canRework = contract.status === "Отклонено" && user.email === contract.initiator_email;

  async function decide(decision) {
    setBusy(true);
    try {
      await api.decide({ entity_type: "contract", entity_id: id, decision, comment });
      toast(decision === "Согласовано" ? "✓ Согласовано" : "✓ Отклонено");
      setComment("");
      load();
      refreshPending();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function submitRework() {
    if (!reworkForm.comment.trim()) { toast("Опишите, что было исправлено", true); return; }
    setBusy(true);
    try {
      await api.resubmitContract(id, reworkForm);
      toast("✓ Договор доработан и отправлен на новый круг согласования");
      setShowRework(false);
      load();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Link to="/contracts" style={{ fontSize: 12, color: "var(--text-3)", textDecoration: "none" }}>← К реестру договоров</Link>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Договор {contract.id}</div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
              Инициатор {contract.initiator_fio} · создан {fmtDate(contract.created_at)}
            </div>
          </div>
          <span className={`badge ${statusBadgeClass(contract.status)}`}>{contract.status}</span>
        </div>
        {contract.revision > 1 && (
          <div style={{ padding: "0 20px", fontSize: 12, color: "var(--text-3)" }}>Раунд согласования: {contract.revision}</div>
        )}

        {myTurn && (
          <div className="card-body" style={{ background: "var(--blue-bg, #EEF2FF)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Документ ожидает вашего решения</div>
            <div className="field">
              <label>Комментарий (необязательно)</label>
              <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
            </div>
            <div className="top-actions">
              <button className="btn btn-approve" disabled={busy} onClick={() => decide("Согласовано")}>✓ Согласовать</button>
              <button className="btn btn-danger" disabled={busy} onClick={() => decide("Отклонено")}>✕ Отклонить</button>
            </div>
          </div>
        )}

        {canRework && (
          <div className="card-body" style={{ background: "var(--red-bg)", borderBottom: "1px solid var(--border)" }}>
            {!showRework ? (
              <>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Договор отклонён</div>
                <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 10 }}>
                  Вы можете исправить договор и отправить его на новый круг согласования.
                </div>
                <button className="btn btn-primary btn-xs" onClick={() => setShowRework(true)}>✎ Доработать и отправить заново</button>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Доработка договора (раунд {(contract.revision || 1) + 1})</div>
                <div className="field">
                  <label>Предмет договора</label>
                  <textarea rows={2} value={reworkForm.subject} onChange={(e) => setReworkForm({ ...reworkForm, subject: e.target.value })} />
                </div>
                <div className="field">
                  <label>Что исправлено (обязательно)</label>
                  <textarea rows={2} value={reworkForm.comment} onChange={(e) => setReworkForm({ ...reworkForm, comment: e.target.value })} />
                </div>
                <div className="top-actions">
                  <button className="btn btn-primary btn-xs" disabled={busy} onClick={submitRework}>Отправить на согласование</button>
                  <button className="btn btn-ghost btn-xs" onClick={() => setShowRework(false)}>Отмена</button>
                </div>
              </>
            )}
          </div>
        )}

        <div className="card-body">
          <Tabs tabs={[
            {
              label: "Обзор",
              content: (
                <div>
                  <div className="grid-2" style={{ marginBottom: 16 }}>
                    <div><b>Контрагент:</b> {contract.contractor_name}{contract.contractor_inn ? ` (ИНН ${contract.contractor_inn})` : ""}</div>
                    <div><b>Юрлицо:</b> {contract.legal_entity_name || "—"}</div>
                    <div><b>Номер договора:</b> {contract.contract_number || "—"}</div>
                    <div><b>Лимит:</b> {fmtMoney(contract.limit_amount)} ₽</div>
                    <div><b>Действует до:</b> {contract.valid_until || "—"}</div>
                  </div>
                  <p style={{ marginBottom: 16 }}><b>Предмет:</b> {contract.subject}</p>
                  {contract.comment && <p style={{ marginBottom: 16 }}><b>Комментарий:</b> {contract.comment}</p>}

                  {items?.length > 0 && (
                    <>
                      <h4 style={{ margin: "16px 0 8px" }}>Позиции</h4>
                      <table>
                        <thead><tr><th>Наименование</th><th>Цена</th><th>Ед.</th></tr></thead>
                        <tbody>
                          {items.map((it) => <tr key={it.id} style={{ cursor: "default" }}><td>{it.name}</td><td>{fmtMoney(it.price)} ₽</td><td>{it.unit}</td></tr>)}
                        </tbody>
                      </table>
                    </>
                  )}

                  <h4 style={{ margin: "20px 0 8px" }}>Маршрут согласования</h4>
                  <ApprovalTrail approvals={approvals} />

                  {(user.role === "Закупщик" || user.role === "Админ") && contract.status === "Согласовано" && (
                    <div style={{ marginTop: 18 }}>
                      <button className="btn btn-ghost" onClick={() => navigate(`/contracts/${id}/amendment`)}>+ Доп. соглашение</button>
                    </div>
                  )}
                </div>
              ),
            },
            { label: "Файл", content: <FilePreview url={contract.file_url} /> },
            { label: "История", content: <HistoryPanel entityId={id} /> },
          ]} />
        </div>
      </div>
    </div>
  );
}
