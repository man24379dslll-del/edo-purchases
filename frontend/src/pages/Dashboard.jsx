import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtMoney } from "../format";

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.dashboard().then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <div className="loading">Загрузка...</div>;

  const kpis = [
    { label: "Договоры всего", value: data.contractsTotal },
    { label: "Договоры на согласовании", value: data.contractsPending },
    { label: "Договоры согласовано", value: data.contractsApproved },
    { label: "Закупки всего", value: data.purchasesTotal },
    { label: "Закупки на согласовании", value: data.purchasesPending },
    { label: "Сумма закупок, ₽", value: fmtMoney(data.purchasesAmount) },
    { label: "Ждут вашего решения", value: data.myPendingApprovals },
  ];

  return (
    <div>
      <div className="kpi-grid">
        {kpis.map((k) => (
          <div className="kpi" key={k.label}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Добро пожаловать</div></div>
        <div className="card-body" style={{ color: "var(--text-2)" }}>
          Используйте меню слева, чтобы создавать договоры и закупки, а также согласовывать
          документы, ожидающие вашего решения.
        </div>
      </div>
    </div>
  );
}
