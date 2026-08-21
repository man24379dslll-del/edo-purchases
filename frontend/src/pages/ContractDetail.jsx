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

  function load() {
    api.contract(id).then(setData).catch((e) => toast(e.message, true));
  }
  useEffect(load, [id]);

  if (!data) return <div className="loading">Загрузка...</div>;

  const { contract, approvals } = data;
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
            { label: "История", content: <HistoryPanel entityId={id} /> },
          ]} />
        </div>
      </div>
    </div>
  );
}
