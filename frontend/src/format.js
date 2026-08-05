export function fmtMoney(n) {
  const v = Number(n) || 0;
  return v.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function statusBadgeClass(status) {
  if (!status) return "b-pending";
  if (status.includes("Отклон")) return "b-rejected";
  if (status.includes("Согласовано")) return "b-approved";
  return "b-pending";
}
