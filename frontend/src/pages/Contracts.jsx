import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import Modal from "../components/Modal";
import FilterBar from "../components/FilterBar";
import ContractorAutocomplete from "../components/ContractorAutocomplete";
import ContractAutocomplete from "../components/ContractAutocomplete";
import FileUpload from "../components/FileUpload";
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

  function canDelete(c) {
    return c.status === "На согласовании" && (c.initiator_email === user.email || user.role === "Админ");
  }

  async function remove(e, c) {
    e.stopPropagation();
    if (!confirm(`Удалить договор ${c.id}?`)) return;
    try {
      await api.deleteContract(c.id);
      toast("✓ Договор удалён");
      load();
    } catch (err) {
      toast(err.message, true);
    }
  }

  return (
    <div>
      <FilterBar q={q} onQ={setQ} status={status} onStatus={setStatus} statuses={STATUSES} onExport={exportXlsx} />

      <div className="top-actions" style={{ marginBottom: 16, justifyContent: "flex-end" }}>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ Новый / Доп. соглашение</button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>№</th><th>Контрагент</th><th>Предмет</th><th>Цена за ед.</th><th>Статус</th><th>Создан</th><th></th>
            </tr>
          </thead>
          <tbody>
            {!list && <tr><td colSpan={7} className="et">Загрузка...</td></tr>}
            {list && list.length === 0 && <tr><td colSpan={7} className="et">Ничего не найдено</td></tr>}
            {list && list.map((c) => (
              <tr key={c.id} onClick={() => navigate(`/contracts/${c.id}`)}>
                <td>{c.id}</td>
                <td>{c.contractor_name}</td>
                <td>{c.subject}</td>
                <td>{fmtMoney(c.price_per_unit)} ₽</td>
                <td><span className={`badge ${statusBadgeClass(c.status)}`}>{c.status}</span></td>
                <td>{fmtDate(c.created_at)}</td>
                <td>
                  {canDelete(c) && (
                    <button className="btn btn-danger btn-xs" onClick={(e) => remove(e, c)}>Удалить</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreatedContract={() => { setShowCreate(false); load(); toast("✓ Договор отправлен на согласование"); }}
          onAttached={(contractId) => { setShowCreate(false); toast("✓ Документ прикреплён к договору"); navigate(`/contracts/${contractId}`); }}
        />
      )}
    </div>
  );
}

function CreateModal({ onClose, onCreatedContract, onAttached }) {
  const [mode, setMode] = useState("contract"); // "contract" | "amendment"

  return (
    <Modal title="Новый договор / доп. соглашение" onClose={onClose} footer={null}>
      <div style={{ display: "flex", gap: 4, marginBottom: 18, background: "var(--bg)", borderRadius: 8, padding: 4 }}>
        <button
          type="button"
          onClick={() => setMode("contract")}
          className="btn btn-xs"
          style={{
            flex: 1, background: mode === "contract" ? "var(--surface)" : "transparent",
            boxShadow: mode === "contract" ? "var(--shadow-sm)" : "none", color: "var(--text-1)",
          }}
        >
          Новый договор
        </button>
        <button
          type="button"
          onClick={() => setMode("amendment")}
          className="btn btn-xs"
          style={{
            flex: 1, background: mode === "amendment" ? "var(--surface)" : "transparent",
            boxShadow: mode === "amendment" ? "var(--shadow-sm)" : "none", color: "var(--text-1)",
          }}
        >
          Доп. соглашение / приложение
        </button>
      </div>

      {mode === "contract"
        ? <NewContractForm onClose={onClose} onCreated={onCreatedContract} />
        : <AttachDocumentForm onClose={onClose} onAttached={onAttached} />}
    </Modal>
  );
}

function NewContractForm({ onClose, onCreated }) {
  const toast = useToast();
  const [options, setOptions] = useState(null);
  const [form, setForm] = useState({
    contractor_name: "", contractor_inn: "", legal_entity_id: "", subject: "",
    contract_number: "", price_per_unit: "", valid_until: "", comment: "", file_url: "",
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.formOptions().then(setOptions); }, []);

  async function submit() {
    if (!form.contractor_name || !form.subject) { toast("Заполните контрагента и предмет договора", true); return; }
    setBusy(true);
    try {
      await api.createContract({
        ...form,
        price_per_unit: Number(form.price_per_unit) || 0,
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
    <>
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
          <label>Цена за единицу, ₽</label>
          <input type="number" value={form.price_per_unit} onChange={(e) => setForm({ ...form, price_per_unit: e.target.value })} />
        </div>
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Действует до</label>
          <input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} />
        </div>
        <div className="field">
          <label>Файл договора</label>
          <FileUpload value={form.file_url} onChange={(url) => setForm({ ...form, file_url: url })} />
        </div>
      </div>
      <div className="field">
        <label>Комментарий</label>
        <textarea rows={2} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
      </div>
      <div className="modal-footer" style={{ margin: "18px -22px -22px", padding: "16px 22px" }}>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Отправка..." : "Отправить на согласование"}</button>
      </div>
    </>
  );
}

function AttachDocumentForm({ onClose, onAttached }) {
  const toast = useToast();
  const [docTypes, setDocTypes] = useState([]);
  const [contract, setContract] = useState(null);
  const [form, setForm] = useState({ doc_type: "Доп. соглашение", description: "", file_url: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.docTypes().then((t) => setDocTypes(t.filter((x) => x !== "Договор"))); }, []);

  async function submit() {
    if (!contract) { toast("Выберите договор, к которому прикрепляете документ", true); return; }
    if (!form.file_url) { toast("Прикрепите файл", true); return; }
    setBusy(true);
    try {
      await api.attachDocument(contract.id, {
        url: form.file_url, doc_type: form.doc_type, description: form.description || null,
      });
      onAttached(contract.id);
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="field">
        <label>Договор *</label>
        <ContractAutocomplete value={contract} onSelect={setContract} />
      </div>
      <div className="field">
        <label>Тип документа *</label>
        <select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
          {docTypes.map((t) => <option key={t} value={t}>{t}</option>)}
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
      <div className="modal-footer" style={{ margin: "18px -22px -22px", padding: "16px 22px" }}>
        <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={submit} disabled={busy}>{busy ? "Сохранение..." : "Прикрепить к договору"}</button>
      </div>
    </>
  );
}
