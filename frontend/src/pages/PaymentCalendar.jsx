import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import Modal from "../components/Modal";
import ContractAutocomplete from "../components/ContractAutocomplete";
import { fmtMoney } from "../format";

const MONTH_NAMES = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];
const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function toISODate(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function buildMonthGrid(year, month) {
  const first = new Date(year, month, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

const FINANCE_ROLES = ["Директор", "Бухгалтер", "Админ"];

export default function PaymentCalendar() {
  const { user } = useAuth();
  const toast = useToast();
  const canEdit = FINANCE_ROLES.includes(user.role);
  const [cursor, setCursor] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [items, setItems] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [showDay, setShowDay] = useState(null);

  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const grid = useMemo(() => buildMonthGrid(year, month), [year, month]);

  function load() {
    const from = toISODate(new Date(year, month, 1));
    const to = toISODate(new Date(year, month + 1, 0));
    api.payments({ date_from: from, date_to: to }).then(setItems).catch(() => setItems([]));
  }
  useEffect(load, [year, month]);

  const byDay = useMemo(() => {
    const map = {};
    (items || []).forEach((p) => {
      (map[p.due_date] ||= []).push(p);
    });
    return map;
  }, [items]);

  const monthTotal = (items || []).reduce((s, p) => s + p.amount, 0);
  const plannedTotal = (items || []).filter((p) => p.status === "Запланирован").reduce((s, p) => s + p.amount, 0);

  return (
    <div>
      <div className="top-actions" style={{ marginBottom: 16, justifyContent: "space-between" }}>
        <div className="top-actions">
          <button className="btn btn-ghost btn-xs" onClick={() => setCursor(new Date(year, month - 1, 1))}>← Пред.</button>
          <div style={{ fontWeight: 600, minWidth: 160, textAlign: "center" }}>{MONTH_NAMES[month]} {year}</div>
          <button className="btn btn-ghost btn-xs" onClick={() => setCursor(new Date(year, month + 1, 1))}>След. →</button>
        </div>
        <div className="top-actions">
          <div style={{ fontSize: 12, color: "var(--text-3)" }}>
            Всего за месяц: <b style={{ color: "var(--text-1)" }}>{fmtMoney(monthTotal)} ₽</b>
            {" · "}Запланировано: <b style={{ color: "var(--amber)" }}>{fmtMoney(plannedTotal)} ₽</b>
          </div>
          {canEdit && <button className="btn btn-primary btn-xs" onClick={() => setShowAdd(true)}>+ Платёж</button>}
        </div>
      </div>

      {!items ? (
        <div className="loading">Загрузка...</div>
      ) : (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6, marginBottom: 6 }}>
            {WEEKDAYS.map((w) => (
              <div key={w} style={{ textAlign: "center", fontSize: 11, color: "var(--text-3)", fontWeight: 600 }}>{w}</div>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6 }}>
            {grid.map((d, i) => {
              const iso = d ? toISODate(d) : null;
              const dayItems = iso ? (byDay[iso] || []) : [];
              const isToday = d && toISODate(d) === toISODate(new Date());
              return (
                <div key={i} onClick={() => d && dayItems.length > 0 && setShowDay(d)} style={{
                  minHeight: 84, borderRadius: 8, padding: 6,
                  background: d ? "var(--bg)" : "transparent",
                  border: isToday ? "1.5px solid var(--accent)" : "1px solid var(--border)",
                  cursor: dayItems.length > 0 ? "pointer" : "default",
                }}>
                  {d && <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4 }}>{d.getDate()}</div>}
                  {dayItems.slice(0, 3).map((p) => (
                    <div key={p.id} style={{
                      fontSize: 10, padding: "2px 5px", borderRadius: 5, marginBottom: 2,
                      background: p.status === "Оплачен" ? "var(--green-bg)" : "var(--amber-bg)",
                      color: p.status === "Оплачен" ? "var(--green)" : "var(--amber)",
                      overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis",
                    }}>
                      {fmtMoney(p.amount)} ₽
                    </div>
                  ))}
                  {dayItems.length > 3 && <div style={{ fontSize: 10, color: "var(--text-3)" }}>+{dayItems.length - 3} ещё</div>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {showAdd && (
        <AddPaymentModal onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); load(); toast("✓ Платёж добавлен в календарь"); }} />
      )}
      {showDay && (
        <DayModal date={showDay} items={byDay[toISODate(showDay)] || []} canEdit={canEdit}
          onClose={() => setShowDay(null)} onChange={() => { load(); setShowDay(null); }} />
      )}
    </div>
  );
}

function AddPaymentModal({ onClose, onSaved }) {
  const toast = useToast();
  const [contract, setContract] = useState(null);
  const [form, setForm] = useState({ due_date: toISODate(new Date()), amount: "", comment: "" });
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!contract) { toast("Выберите договор", true); return; }
    if (!form.amount) { toast("Укажите сумму", true); return; }
    setBusy(true);
    try {
      await api.createPayment({ contract_id: contract.id, due_date: form.due_date, amount: Number(form.amount), comment: form.comment || null });
      onSaved();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новый плановый платёж" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Сохранение..." : "Добавить"}</button>
      </>
    }>
      <div className="field">
        <label>Договор *</label>
        <ContractAutocomplete value={contract} onSelect={setContract} />
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Дата платежа *</label>
          <input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
        </div>
        <div className="field">
          <label>Сумма, ₽ *</label>
          <input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label>Комментарий</label>
        <textarea rows={2} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
      </div>
    </Modal>
  );
}

function DayModal({ date, items, canEdit, onClose, onChange }) {
  const toast = useToast();

  async function markPaid(id) {
    try { await api.markPaymentPaid(id); toast("✓ Отмечен оплаченным"); onChange(); }
    catch (e) { toast(e.message, true); }
  }
  async function remove(id) {
    if (!confirm("Удалить этот платёж из календаря?")) return;
    try { await api.removePayment(id); toast("✓ Удалено"); onChange(); }
    catch (e) { toast(e.message, true); }
  }

  return (
    <Modal title={date.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" })} onClose={onClose}>
      {items.map((p) => (
        <div key={p.id} className="card" style={{ padding: 12, marginBottom: 10, boxShadow: "none", border: "1px solid var(--border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
            <b>{fmtMoney(p.amount)} ₽</b>
            <span className={`badge ${p.status === "Оплачен" ? "b-approved" : "b-pending"}`}>{p.status}</span>
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <Link to={`/contracts/${p.contract_id}`}>{p.contract_subject || p.contract_id}</Link>
            {p.contractor_name && <span style={{ color: "var(--text-3)" }}> · {p.contractor_name}</span>}
          </div>
          {p.comment && <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 8 }}>{p.comment}</div>}
          {canEdit && (
            <div className="top-actions">
              {p.status !== "Оплачен" && (
                <button className="btn btn-approve btn-xs" onClick={() => markPaid(p.id)}>✓ Отметить оплаченным</button>
              )}
              <button className="btn btn-danger btn-xs" onClick={() => remove(p.id)}>Удалить</button>
            </div>
          )}
        </div>
      ))}
    </Modal>
  );
}
