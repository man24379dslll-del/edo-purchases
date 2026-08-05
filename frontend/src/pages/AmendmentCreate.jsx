import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useToast } from "../components/Toast";

export default function AmendmentCreate() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState({ subject: "", comment: "", needs_marketing: false, file_url: "" });
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!form.subject) { toast("Укажите предмет доп. соглашения", true); return; }
    setBusy(true);
    try {
      await api.createAmendment({ ...form, contract_id: id });
      toast("✓ Доп. соглашение отправлено на согласование");
      navigate(`/contracts/${id}`);
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Link to={`/contracts/${id}`} style={{ fontSize: 12, color: "var(--text-3)", textDecoration: "none" }}>← К договору {id}</Link>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Новое доп. соглашение к договору {id}</div></div>
        <div className="card-body">
          <div className="field">
            <label>Предмет доп. соглашения *</label>
            <textarea rows={3} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
          </div>
          <div className="field">
            <label>Ссылка на файл</label>
            <input value={form.file_url} onChange={(e) => setForm({ ...form, file_url: e.target.value })} placeholder="https://..." />
          </div>
          <div className="field">
            <label><input type="checkbox" checked={form.needs_marketing} style={{ width: "auto", marginRight: 8 }}
              onChange={(e) => setForm({ ...form, needs_marketing: e.target.checked })} />
              Требуется согласование Маркетинга
            </label>
          </div>
          <div className="field">
            <label>Комментарий</label>
            <textarea rows={2} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
          </div>
          <button className="btn btn-primary" disabled={busy} onClick={submit}>
            {busy ? "Отправка..." : "Отправить на согласование"}
          </button>
        </div>
      </div>
    </div>
  );
}
