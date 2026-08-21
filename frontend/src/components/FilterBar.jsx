export default function FilterBar({ q, onQ, status, onStatus, statuses, onExport }) {
  return (
    <div className="top-actions" style={{ marginBottom: 16, justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
      <div className="top-actions" style={{ flex: 1, minWidth: 260 }}>
        <input
          placeholder="Поиск по номеру, контрагенту, предмету..."
          value={q}
          onChange={(e) => onQ(e.target.value)}
          style={{ minWidth: 260, padding: "9px 12px", border: "1px solid var(--border-s)", borderRadius: 8 }}
        />
        <select value={status} onChange={(e) => onStatus(e.target.value)} style={{ padding: "9px 12px", border: "1px solid var(--border-s)", borderRadius: 8 }}>
          <option value="">Все статусы</option>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      {onExport && (
        <button className="btn btn-ghost" onClick={onExport}>⬇ Экспорт в Excel</button>
      )}
    </div>
  );
}
