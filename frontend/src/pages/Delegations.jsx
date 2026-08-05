import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import { fmtDate } from "../format";

function toLocalInputValue(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function Delegations() {
  const { user } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const now = new Date();
  const inAWeek = new Date(now.getTime() + 7 * 24 * 3600 * 1000);
  const [form, setForm] = useState({
    delegate_email: "", starts_at: toLocalInputValue(now), ends_at: toLocalInputValue(inAWeek), comment: "",
  });
  const [busy, setBusy] = useState(false);

  function load() {
    api.delegations().then(setRows).catch(() => setRows([]));
  }
  useEffect(load, []);

  async function submit() {
    if (!form.delegate_email) { toast("Укажите email замещающего", true); return; }
    setBusy(true);
    try {
      await api.createDelegation({
        delegator_email: user.email,
        delegate_email: form.delegate_email,
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: new Date(form.ends_at).toISOString(),
        comment: form.comment,
      });
      toast("✓ Делегирование создано");
      setForm({ ...form, delegate_email: "", comment: "" });
      load();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id) {
    if (!confirm("Отменить это делегирование?")) return;
    try { await api.removeDelegation(id); toast("✓ Отменено"); load(); }
    catch (e) { toast(e.message, true); }
  }

  function isActive(d) {
    const nowT = Date.now();
    return new Date(d.starts_at).getTime() <= nowT && nowT <= new Date(d.ends_at).getTime();
  }

  return (
    <div>
      <div className="section-sub">
        Передайте свои задачи на согласование другому сотруднику на время отпуска, командировки
        или болезни — он будет видеть и принимать решения по вашим документам, не получая вашу роль.
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">Делегировать свою роль ({user.role})</div></div>
        <div className="card-body">
          <div className="field">
            <label>Кому передать (email)</label>
            <input value={form.delegate_email} onChange={(e) => setForm({ ...form, delegate_email: e.target.value })} placeholder="colleague@company.com" />
          </div>
          <div className="grid-2">
            <div className="field">
              <label>С</label>
              <input type="datetime-local" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
            </div>
            <div className="field">
              <label>По</label>
              <input type="datetime-local" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>Комментарий</label>
            <input value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} placeholder="Например: отпуск" />
          </div>
          <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Сохранение..." : "Создать делегирование"}</button>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">
          {user.role === "Директор" || user.role === "Админ" ? "Все делегирования" : "Мои делегирования"}
        </div></div>
        <table>
          <thead><tr><th>Кто замещает</th><th>Вместо кого</th><th>Период</th><th>Статус</th><th>Комментарий</th><th></th></tr></thead>
          <tbody>
            {!rows && <tr><td colSpan={6} className="et">Загрузка...</td></tr>}
            {rows && rows.length === 0 && <tr><td colSpan={6} className="et">Делегирований пока нет</td></tr>}
            {rows && rows.map((d) => (
              <tr key={d.id} style={{ cursor: "default" }}>
                <td>{d.delegate_email}</td>
                <td>{d.delegator_email} ({d.delegator_role})</td>
                <td style={{ fontSize: 12 }}>{fmtDate(d.starts_at)} — {fmtDate(d.ends_at)}</td>
                <td><span className={`badge ${isActive(d) ? "b-approved" : "b-pending"}`}>{isActive(d) ? "Активно" : "Не активно"}</span></td>
                <td>{d.comment || "—"}</td>
                <td>
                  {(user.email === d.delegator_email || user.role === "Директор" || user.role === "Админ") && (
                    <button className="btn btn-danger btn-xs" onClick={() => remove(d.id)}>Отменить</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
