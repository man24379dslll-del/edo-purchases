import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useToast } from "../components/Toast";
import Modal from "../components/Modal";
import FilterBar from "../components/FilterBar";
import { fmtDate, fmtMoney, statusBadgeClass } from "../format";

const STATUSES = ["На согласовании", "Согласовано", "Отклонено"];

export default function Purchases() {
  const toast = useToast();
  const navigate = useNavigate();
  const [list, setList] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");

  function load() {
    api.purchases({ q, status }).then(setList).catch(() => setList([]));
  }
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [q, status]);

  async function exportXlsx() {
    try { await api.exportPurchases(); } catch (e) { toast(e.message, true); }
  }

  return (
    <div>
      <FilterBar q={q} onQ={setQ} status={status} onStatus={setStatus} statuses={STATUSES} onExport={exportXlsx} />

      <div className="top-actions" style={{ marginBottom: 16, justifyContent: "flex-end" }}>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ Новая закупка</button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>№</th><th>Предмет</th><th>Кол-во</th><th>Сумма</th><th>Статус</th><th>Исполнение</th><th>Создана</th>
            </tr>
          </thead>
          <tbody>
            {!list && <tr><td colSpan={7} className="et">Загрузка...</td></tr>}
            {list && list.length === 0 && <tr><td colSpan={7} className="et">Ничего не найдено</td></tr>}
            {list && list.map((p) => (
              <tr key={p.id} onClick={() => navigate(`/purchases/${p.id}`)}>
                <td>{p.id}</td>
                <td>{p.subject}</td>
                <td>{p.quantity}</td>
                <td>{fmtMoney(p.amount)} ₽</td>
                <td><span className={`badge ${statusBadgeClass(p.status)}`}>{p.status}</span></td>
                <td>{p.execution_status}</td>
                <td>{fmtDate(p.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreatePurchaseModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); toast("✓ Закупка отправлена на согласование"); }}
        />
      )}
    </div>
  );
}

function CreatePurchaseModal({ onClose, onCreated }) {
  const toast = useToast();
  const [contracts, setContracts] = useState([]);
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState({
    contract_id: "", purchase_type: "Товар", subcategory: "", subject: "",
    quantity: "", price_per_unit: "", comment: "", file_url: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.contracts({ status: "Согласовано" }).then(setContracts);
    api.formOptions().then(setOptions);
  }, []);

  const amount = (Number(form.quantity) || 0) * (Number(form.price_per_unit) || 0);

  async function submit() {
    if (!form.subject || !form.quantity || !form.price_per_unit) {
      toast("Заполните предмет, количество и цену", true); return;
    }
    setBusy(true);
    try {
      await api.createPurchase({
        ...form,
        contract_id: form.contract_id || null,
        quantity: Number(form.quantity),
        price_per_unit: Number(form.price_per_unit),
      });
      onCreated();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новая закупка" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Отправка..." : "Отправить на согласование"}</button>
      </>
    }>
      <div className="field">
        <label>Договор (необязательно)</label>
        <select value={form.contract_id} onChange={(e) => setForm({ ...form, contract_id: e.target.value })}>
          <option value="">— без договора —</option>
          {contracts.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.contractor_name}</option>)}
        </select>
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Тип закупки</label>
          <select value={form.purchase_type} onChange={(e) => setForm({ ...form, purchase_type: e.target.value })}>
            {(options?.purchaseTypes || ["Товар"]).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Подкатегория</label>
          <select value={form.subcategory} onChange={(e) => setForm({ ...form, subcategory: e.target.value })}>
            <option value="">—</option>
            {(options?.productSubcategories || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Предмет закупки *</label>
        <textarea rows={2} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Количество *</label>
          <input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        </div>
        <div className="field">
          <label>Цена за ед. *</label>
          <input type="number" value={form.price_per_unit} onChange={(e) => setForm({ ...form, price_per_unit: e.target.value })} />
        </div>
      </div>
      <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 14 }}>Итого: <b>{fmtMoney(amount)} ₽</b></div>
      <div className="field">
        <label>Ссылка на файл</label>
        <input value={form.file_url} onChange={(e) => setForm({ ...form, file_url: e.target.value })} placeholder="https://..." />
      </div>
      <div className="field">
        <label>Комментарий</label>
        <textarea rows={2} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
      </div>
    </Modal>
  );
}
