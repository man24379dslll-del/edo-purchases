import { useEffect, useState } from "react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { fmtMoney } from "../format";

export default function Osv() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.osv().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty-state">{error}</div>;
  if (!data) return <div className="loading">Загрузка...</div>;

  const t = data.totals;

  async function exportXlsx() {
    try { await api.exportOsv(); } catch (e) { toast(e.message, true); }
  }

  return (
    <div>
      <div className="top-actions" style={{ justifyContent: "space-between", marginBottom: 4 }}>
        <div className="section-sub" style={{ marginBottom: 0 }}>По состоянию на: {data.generatedAt}</div>
        <button className="btn btn-ghost" onClick={exportXlsx}>⬇ Экспорт в Excel</button>
      </div>

      <div className="kpi-grid">
        <div className="kpi"><div className="kpi-label">Контрагентов</div><div className="kpi-value">{data.rows.length}</div></div>
        <div className="kpi"><div className="kpi-label">Дебет, ₽</div><div className="kpi-value" style={{ color: "var(--amber)" }}>{fmtMoney(t.debit)}</div></div>
        <div className="kpi"><div className="kpi-label">Кредит, ₽</div><div className="kpi-value" style={{ color: "var(--green)" }}>{fmtMoney(t.credit)}</div></div>
        <div className="kpi"><div className="kpi-label">Сальдо, ₽</div><div className="kpi-value" style={{ color: t.saldo > 0 ? "var(--red)" : "var(--green)" }}>{fmtMoney(t.saldo)}</div></div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Контрагент</th><th>ИНН</th><th>Договоров</th><th>Сумма договоров</th>
              <th>Дебет</th><th>Кредит</th><th>Сальдо</th><th>Заказано</th><th>Получено</th><th>Остаток</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.length === 0 && <tr><td colSpan={10} className="et">Нет данных по контрагентам</td></tr>}
            {data.rows.map((r) => {
              const saldoQty = r.saldoQty ?? (r.orderedQty - r.receivedQty);
              return (
                <tr key={r.contractorId} style={{ cursor: "default" }}>
                  <td><b>{r.contractorName}</b></td>
                  <td style={{ color: "var(--text-3)" }}>{r.contractorInn || "—"}</td>
                  <td style={{ textAlign: "center" }}>{r.contracts}</td>
                  <td style={{ textAlign: "right" }}>{fmtMoney(r.contractSum)} ₽</td>
                  <td style={{ textAlign: "right", color: "var(--amber)", fontWeight: 600 }}>{fmtMoney(r.debit)} ₽</td>
                  <td style={{ textAlign: "right", color: "var(--green)", fontWeight: 600 }}>{fmtMoney(r.credit)} ₽</td>
                  <td style={{ textAlign: "right", color: r.saldo > 0 ? "var(--red)" : r.saldo < 0 ? "var(--green)" : undefined, fontWeight: 700 }}>{fmtMoney(r.saldo)} ₽</td>
                  <td style={{ textAlign: "right" }}>{r.orderedQty}</td>
                  <td style={{ textAlign: "right" }}>{r.receivedQty}</td>
                  <td style={{ textAlign: "right", color: saldoQty > 0 ? "var(--amber)" : saldoQty < 0 ? "var(--green)" : undefined, fontWeight: 600 }}>{saldoQty}</td>
                </tr>
              );
            })}
          </tbody>
          {data.rows.length > 0 && (
            <tfoot>
              <tr style={{ background: "var(--bg)", fontWeight: 700 }}>
                <td colSpan={3} style={{ fontSize: 12, color: "var(--text-2)" }}>ИТОГО</td>
                <td style={{ textAlign: "right" }}>{fmtMoney(t.contractSum)} ₽</td>
                <td style={{ textAlign: "right", color: "var(--amber)" }}>{fmtMoney(t.debit)} ₽</td>
                <td style={{ textAlign: "right", color: "var(--green)" }}>{fmtMoney(t.credit)} ₽</td>
                <td style={{ textAlign: "right", color: t.saldo > 0 ? "var(--red)" : "var(--green)" }}>{fmtMoney(t.saldo)} ₽</td>
                <td style={{ textAlign: "right" }}>{t.orderedQty}</td>
                <td style={{ textAlign: "right" }}>{t.receivedQty}</td>
                <td style={{ textAlign: "right" }}>{t.saldoQty}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
