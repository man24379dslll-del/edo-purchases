import { fmtDate } from "../format";

export default function ApprovalTrail({ approvals }) {
  if (!approvals || !approvals.length) return <div className="empty-state">Маршрут согласования не запущен</div>;
  return (
    <div className="trail">
      {approvals.map((a, i) => {
        let dotClass = "dot-pending";
        if (a.decision === "Согласовано") dotClass = "dot-approved";
        else if (a.decision === "Отклонено") dotClass = "dot-rejected";
        else if (a.state === "active") dotClass = "dot-active";
        return (
          <div className="trail-item" key={i}>
            <span className={`trail-dot ${dotClass}`}></span>
            <b>{a.role}</b>
            <span style={{ color: "var(--text-3)" }}>
              {a.decision === "Ожидает"
                ? (a.state === "active" ? "— ожидает решения" : "— в очереди")
                : `— ${a.decision.toLowerCase()} ${a.date ? fmtDate(a.date) : ""}`}
            </span>
            {a.comment && <span style={{ marginLeft: "auto", color: "var(--text-3)" }}>«{a.comment}»</span>}
          </div>
        );
      })}
    </div>
  );
}
