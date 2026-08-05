import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import Modal from "../components/Modal";
import FilterBar from "../components/FilterBar";
import ContractorAutocomplete from "../components/ContractorAutocomplete";
import { fmtDate, fmtMoney, statusBadgeClass } from "../format";

const STATUSES = ["На согласовании", "Согласовано", "Отклонено"];

export default function Contracts() {
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [list, setList] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");

  function load() {
    api.contracts({ q, status }).then(setList).catch(() => setList([]));
  }
  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [q, status]);

  async function exportXlsx() {
    try { await api.exportContracts(); } catch (e) { toast(e.message, true); }
  }

  return (
    <div>
      <FilterBar q={q} onQ={setQ} status={status} onStatus={setStatus} statuses={STATUSES} onExport={exportXlsx} />

      <div className="top-actions" style={{ marginBottom: 16, justifyContent: "flex-end" }}>
        {(user.role === "Закупщик" || user.role === "Админ") && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ Новый договор</button>
        )}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>№</th><th>Контрагент</th><th>Предмет</th><th>Лимит</th><th>Статус</th><th>Создан</th>
            </tr>
          </thead>
          <tbody>
            {!list && <tr><td colSpan={6} className="et">Загрузка...</td></tr>}
            {list && list.length === 0 && <tr><td colSpan={6} className="et">Ничего не найдено</td></tr>}
            {list && list.map((c) => (
              <tr key={c.id} onClick={() => navigate(`/contracts/${c.id}`)}>
                <td>{c.id}</td>
                <td>{c.contractor_name}</td>
                <td>{c.subject}</td>
                <td>{fmtMoney(c.limit_amount)} ₽</td>
                <td><span className={`badge ${statusBadgeClass(c.status)}`}>{c.status}</span></td>
                <td>{fmtDate(c.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateContractModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load(); toast("✓ Договор отправлен на согласование"); }}
        />
      )}
    </div>
  );
}

function CreateContractModal({ onClose, onCreated }) {
  const toast = useToast();
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState({
    contractor_name: "", contractor_inn: "", legal_entity_id: "", subject: "",
    contract_number: "", limit_amount: "", valid_until: "", comment: "", needs_marketing: false,
    file_url: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.formOptions().then(setOptions); }, []);

  async function submit() {
    if (!form.contractor_name || !form.subject) { toast("Заполните контрагента и предмет договора", true); return; }
    setBusy(true);
    try {
      await api.createContract({
        ...form,
        limit_amount: Number(form.limit_amount) || 0,
        valid_until: form.valid_until || null,
      });
      onCreated();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новый договор" onClose={onClose} footer={
      <>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Отправка..." : "Отправить на согласование"}</button>
      </>
    }>
      <div className="grid-2">
        <div className="field">
          <label>Контрагент *</label>
          <ContractorAutocomplete
            value={form.contractor_name}
            inn={form.contractor_inn}
            onChange={({ name, inn }) => setForm({ ...form, contractor_name: name, contractor_inn: inn })}
          />
        </div>
        <div className="field">
          <label>ИНН контрагента</label>
          <input value={form.contractor_inn} onChange={(e) => setForm({ ...form, contractor_inn: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label>Юрлицо</label>
        <select value={form.legal_entity_id} onChange={(e) => setForm({ ...form, legal_entity_id: e.target.value })}>
          <option value="">— не выбрано —</option>
          {options?.legalEntities.map((le) => <option key={le.id} value={le.id}>{le.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Предмет договора *</label>
        <textarea rows={2} value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Номер договора</label>
          <input value={form.contract_number} onChange={(e) => setForm({ ...form, contract_number: e.target.value })} />
        </div>
        <div className="field">
          <label>Лимит, ₽</label>
          <input type="number" value={form.limit_amount} onChange={(e) => setForm({ ...form, limit_amount: e.target.value })} />
        </div>
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Действует до</label>
          <input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} />
        </div>
        <div className="field">
          <label>Ссылка на файл договора</label>
          <input value={form.file_url} onChange={(e) => setForm({ ...form, file_url: e.target.value })} placeholder="https://..." />
        </div>
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
    </Modal>
  );
}
