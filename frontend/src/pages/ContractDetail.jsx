import { useEffect, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import ApprovalTrail from "../components/ApprovalTrail";
import FilePreview from "../components/FilePreview";
import FileUpload from "../components/FileUpload";
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

  function load() {
    api.contract(id).then(setData).catch((e) => toast(e.message, true));
  }
  useEffect(load, [id]);

  if (!data) return <div className="loading">Загрузка...</div>;

  const { contract, approvals, documents } = data;
  const myStage = approvals.find((a) => a.state === "active" && a.role === user.role);
  const isDirectorReview = myStage && myStage.stage === 0;
  const canDelete = contract.status === "На согласовании" &&
    (user.email === contract.initiator_email || user.role === "Админ") &&
    !approvals.some((a) => a.decision !== "Ожидает");

  async function decide(decision, standard) {
    setBusy(true);
    try {
      await api.decide({ contract_id: id, decision, standard, comment });
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

  async function remove() {
    if (!confirm(`Удалить договор ${id}? Это действие необратимо.`)) return;
    try {
      await api.deleteContract(id);
      toast("✓ Договор удалён");
      navigate("/contracts");
    } catch (e) {
      toast(e.message, true);
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
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className={`badge ${statusBadgeClass(contract.status)}`}>{contract.status}</span>
            {canDelete && <button className="btn btn-danger btn-xs" onClick={remove}>Удалить</button>}
          </div>
        </div>

        {myStage && (
          <div className="card-body" style={{ background: "var(--blue-bg, #EEF2FF)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>
              {isDirectorReview ? "Договор ожидает вашего рассмотрения" : "Документ ожидает вашего решения"}
            </div>
            <div className="field">
              <label>Комментарий (необязательно)</label>
              <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
            </div>
            {isDirectorReview ? (
              <div className="top-actions">
                <button className="btn btn-approve" disabled={busy} onClick={() => decide("Согласовано", true)}>
                  ✓ Стандартный — согласовать
                </button>
                <button className="btn btn-primary" disabled={busy} onClick={() => decide("Согласовано", false)}>
                  → Отправить Юристу и Бухгалтеру
                </button>
                <button className="btn btn-danger" disabled={busy} onClick={() => decide("Отклонено")}>
                  ✕ Отклонить
                </button>
              </div>
            ) : (
              <div className="top-actions">
                <button className="btn btn-approve" disabled={busy} onClick={() => decide("Согласовано")}>✓ Согласовать</button>
                <button className="btn btn-danger" disabled={busy} onClick={() => decide("Отклонено")}>✕ Отклонить</button>
              </div>
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
                    <div><b>Цена за единицу:</b> {fmtMoney(contract.price_per_unit)} ₽</div>
                    <div><b>Действует до:</b> {contract.valid_until || "—"}</div>
                    <div><b>Стандартный:</b> {contract.is_standard === null ? "— (ещё не решено)" : contract.is_standard ? "Да" : "Нет"}</div>
                  </div>
                  <p style={{ marginBottom: 16 }}><b>Предмет:</b> {contract.subject}</p>
                  {contract.comment && <p style={{ marginBottom: 16 }}><b>Комментарий:</b> {contract.comment}</p>}

                  <h4 style={{ margin: "20px 0 8px" }}>Маршрут согласования</h4>
                  <ApprovalTrail approvals={approvals} />
                </div>
              ),
            },
            { label: "Файл", content: <FilePreview url={contract.file_url} /> },
            { label: `Документы (${documents?.length || 0})`, content: <DocumentsPanel contractId={id} documents={documents} onChange={load} /> },
            { label: "История", content: <HistoryPanel entityId={id} /> },
          ]} />
        </div>
      </div>
    </div>
  );
}

function DocumentsPanel({ contractId, documents, onChange }) {
  const { user } = useAuth();
  const toast = useToast();
  const [docTypes, setDocTypes] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ doc_type: "Доп. соглашение", description: "", file_url: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.docTypes().then(setDocTypes); }, []);

  async function submit() {
    if (!form.file_url) { toast("Прикрепите файл", true); return; }
    setBusy(true);
    try {
      await api.attachDocument(contractId, { url: form.file_url, doc_type: form.doc_type, description: form.description || null });
      toast("✓ Документ прикреплён");
      setForm({ doc_type: "Доп. соглашение", description: "", file_url: "" });
      setShowAdd(false);
      onChange();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function remove(docId) {
    if (!confirm("Удалить этот документ?")) return;
    try {
      await api.removeContractDocument(contractId, docId);
      toast("✓ Документ удалён");
      onChange();
    } catch (e) {
      toast(e.message, true);
    }
  }

  return (
    <div>
      {(!documents || documents.length === 0) && <div className="empty-state">Документов пока нет</div>}
      {documents && documents.length > 0 && (
        <table style={{ marginBottom: 16 }}>
          <thead><tr><th>Тип</th><th>Файл</th><th>Описание</th><th>Загрузил</th><th>Когда</th><th></th></tr></thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.id} style={{ cursor: "default" }}>
                <td><span className="badge b-p">{d.doc_type || "—"}</span></td>
                <td><a href={d.url} target="_blank" rel="noreferrer">📎 {d.original_name}</a></td>
                <td>{d.entity_subject || "—"}</td>
                <td>{d.uploaded_by || "—"}</td>
                <td>{fmtDate(d.uploaded_at)}</td>
                <td>
                  {(user.email === d.uploaded_by || user.role === "Директор" || user.role === "Админ") && (
                    <button className="btn btn-danger btn-xs" onClick={() => remove(d.id)}>Удалить</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!showAdd ? (
        <button className="btn btn-ghost btn-xs" onClick={() => setShowAdd(true)}>+ Добавить документ</button>
      ) : (
        <div className="card" style={{ padding: 16, boxShadow: "none", border: "1px dashed var(--border-s)" }}>
          <div className="field">
            <label>Тип документа</label>
            <select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
              {docTypes.filter((t) => t !== "Договор").map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Описание</label>
            <textarea rows={2} placeholder="Например: ДС №2 об изменении сроков поставки"
              value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="field">
            <label>Файл *</label>
            <FileUpload value={form.file_url} onChange={(url) => setForm({ ...form, file_url: url })} />
          </div>
          <div className="top-actions">
            <button className="btn btn-primary btn-xs" disabled={busy} onClick={submit}>Прикрепить</button>
            <button className="btn btn-ghost btn-xs" onClick={() => setShowAdd(false)}>Отмена</button>
          </div>
        </div>
      )}
    </div>
  );
}
