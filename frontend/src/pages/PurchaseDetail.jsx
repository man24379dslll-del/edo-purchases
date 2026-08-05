import { useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../components/Toast";
import ApprovalTrail from "../components/ApprovalTrail";
import FilePreview from "../components/FilePreview";
import HistoryPanel from "../components/HistoryPanel";
import Tabs from "../components/Tabs";
import { fmtDate, fmtMoney, statusBadgeClass } from "../format";

export default function PurchaseDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const toast = useToast();
  const { refreshPending } = useOutletContext();
  const [data, setData] = useState(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [receiptQty, setReceiptQty] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentType, setPaymentType] = useState("Безналичный");
  const [showRework, setShowRework] = useState(false);
  const [reworkForm, setReworkForm] = useState({ subject: "", quantity: "", price_per_unit: "", comment: "" });

  function load() {
    api.purchase(id).then((d) => {
      setData(d);
      setReworkForm({
        subject: d.purchase.subject, quantity: d.purchase.quantity,
        price_per_unit: d.purchase.price_per_unit, comment: "",
      });
    }).catch((e) => toast(e.message, true));
  }
  useEffect(load, [id]);

  if (!data) return <div className="loading">Загрузка...</div>;

  const { purchase, receipts, payments, approvals } = data;
  const myTurn = approvals.some((a) => a.state === "active" && a.role === user.role);
  const canReceive = ["Склад", "Закупщик", "Админ"].includes(user.role);
  const canPay = ["Бухгалтер", "Фин. директор", "Админ"].includes(user.role);
  const canRework = purchase.status === "Отклонено" && user.email === purchase.initiator_email;

  async function decide(decision) {
    setBusy(true);
    try {
      await api.decide({ entity_type: "purchase", entity_id: id, decision, comment });
      toast(decision === "Согласовано" ? "✓ Согласовано" : "✓ Отклонено");
      setComment("");
      load();
      refreshPending();
    } catch (e) { toast(e.message, true); }
    finally { setBusy(false); }
  }

  async function submitRework() {
    if (!reworkForm.comment.trim()) { toast("Опишите, что было исправлено", true); return; }
    setBusy(true);
    try {
      await api.resubmitPurchase(id, {
        ...reworkForm,
        quantity: reworkForm.quantity !== "" ? Number(reworkForm.quantity) : undefined,
        price_per_unit: reworkForm.price_per_unit !== "" ? Number(reworkForm.price_per_unit) : undefined,
      });
      toast("✓ Закупка доработана и отправлена на новый круг согласования");
      setShowRework(false);
      load();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function submitReceipt() {
    if (!Number(receiptQty)) { toast("Укажите количество", true); return; }
    try {
      await api.addReceipt({ purchase_id: id, quantity: Number(receiptQty) });
      toast("✓ Поступление зафиксировано");
      setReceiptQty(""); load();
    } catch (e) { toast(e.message, true); }
  }

  async function submitPayment() {
    if (!Number(paymentAmount)) { toast("Укажите сумму", true); return; }
    try {
      await api.addPayment({ purchase_id: id, amount: Number(paymentAmount), payment_type: paymentType });
      toast("✓ Платёж добавлен");
      setPaymentAmount(""); load();
    } catch (e) { toast(e.message, true); }
  }

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Link to="/purchases" style={{ fontSize: 12, color: "var(--text-3)", textDecoration: "none" }}>← К реестру закупок</Link>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Закупка {purchase.id}</div>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 2 }}>
              Инициатор {purchase.initiator_fio} · создана {fmtDate(purchase.created_at)}
            </div>
          </div>
          <span className={`badge ${statusBadgeClass(purchase.status)}`}>{purchase.status}</span>
        </div>
        {purchase.revision > 1 && (
          <div style={{ padding: "0 20px", fontSize: 12, color: "var(--text-3)" }}>Раунд согласования: {purchase.revision}</div>
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
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Закупка отклонена</div>
                <div style={{ fontSize: 13, color: "var(--text-2)", marginBottom: 10 }}>
                  Вы можете исправить закупку и отправить её на новый круг согласования.
                </div>
                <button className="btn btn-primary btn-xs" onClick={() => setShowRework(true)}>✎ Доработать и отправить заново</button>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Доработка закупки (раунд {(purchase.revision || 1) + 1})</div>
                <div className="field">
                  <label>Предмет закупки</label>
                  <textarea rows={2} value={reworkForm.subject} onChange={(e) => setReworkForm({ ...reworkForm, subject: e.target.value })} />
                </div>
                <div className="grid-2">
                  <div className="field">
                    <label>Количество</label>
                    <input type="number" value={reworkForm.quantity} onChange={(e) => setReworkForm({ ...reworkForm, quantity: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Цена за ед.</label>
                    <input type="number" value={reworkForm.price_per_unit} onChange={(e) => setReworkForm({ ...reworkForm, price_per_unit: e.target.value })} />
                  </div>
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
                    <div><b>Контрагент:</b> {purchase.contractor_name || "—"}</div>
                    <div><b>Договор:</b> {purchase.contract_id || "—"}</div>
                    <div><b>Тип:</b> {purchase.purchase_type || "—"}</div>
                    <div><b>Подкатегория:</b> {purchase.subcategory || "—"}</div>
                    <div><b>Количество:</b> {purchase.quantity}</div>
                    <div><b>Сумма:</b> {fmtMoney(purchase.amount)} ₽</div>
                    <div><b>Исполнение:</b> {purchase.execution_status}</div>
                  </div>
                  <p style={{ marginBottom: 16 }}><b>Предмет:</b> {purchase.subject}</p>
                  {purchase.comment && <p style={{ marginBottom: 16 }}><b>Комментарий:</b> {purchase.comment}</p>}

                  {purchase.status === "Согласовано" && (
                    <div className="grid-2" style={{ marginBottom: 18 }}>
                      {canReceive && (
                        <div className="field">
                          <label>Зафиксировать поступление, остаток {data.remainingQty}</label>
                          <div style={{ display: "flex", gap: 8 }}>
                            <input type="number" value={receiptQty} onChange={(e) => setReceiptQty(e.target.value)} />
                            <button className="btn btn-primary btn-xs" onClick={submitReceipt}>Сохранить</button>
                          </div>
                        </div>
                      )}
                      {canPay && (
                        <div className="field">
                          <label>Добавить платёж, остаток {fmtMoney(data.remainingAmount)} ₽</label>
                          <div style={{ display: "flex", gap: 8 }}>
                            <input type="number" value={paymentAmount} onChange={(e) => setPaymentAmount(e.target.value)} />
                            <select value={paymentType} onChange={(e) => setPaymentType(e.target.value)} style={{ width: 130 }}>
                              <option>Безналичный</option>
                              <option>Наличный</option>
                            </select>
                            <button className="btn btn-primary btn-xs" onClick={submitPayment}>Сохранить</button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {receipts?.length > 0 && (
                    <>
                      <h4 style={{ margin: "14px 0 6px" }}>Поступления</h4>
                      <table>
                        <thead><tr><th>Дата</th><th>Кол-во</th><th>Кто</th></tr></thead>
                        <tbody>{receipts.map((r) => <tr key={r.id} style={{ cursor: "default" }}><td>{fmtDate(r.date)}</td><td>{r.quantity} ед.</td><td>{r.user_fio}</td></tr>)}</tbody>
                      </table>
                    </>
                  )}
                  {payments?.length > 0 && (
                    <>
                      <h4 style={{ margin: "14px 0 6px" }}>Платежи</h4>
                      <table>
                        <thead><tr><th>Дата</th><th>Сумма</th><th>Тип</th></tr></thead>
                        <tbody>{payments.map((p) => <tr key={p.id} style={{ cursor: "default" }}><td>{fmtDate(p.date)}</td><td>{fmtMoney(p.amount)} ₽</td><td>{p.payment_type}</td></tr>)}</tbody>
                      </table>
                    </>
                  )}

                  <h4 style={{ margin: "20px 0 8px" }}>Маршрут согласования</h4>
                  <ApprovalTrail approvals={approvals} />
                </div>
              ),
            },
            { label: "Файл", content: <FilePreview url={purchase.file_url} /> },
            { label: "История", content: <HistoryPanel entityId={id} /> },
          ]} />
        </div>
      </div>
    </div>
  );
}
