const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("edo_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("edo_token", token);
  else localStorage.removeItem("edo_token");
}

async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

function qs(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  if (!entries.length) return "";
  return "?" + new URLSearchParams(entries).toString();
}

// Скачивает бинарный ответ (например, .xlsx) с авторизацией и запускает сохранение файла.
async function downloadFile(path, filename) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Не удалось скачать файл.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Загружает файл (договор, скан и т.п.) на backend и возвращает абсолютный URL,
// по которому файл потом можно открыть в <iframe>/<img> или скачать напрямую.
async function uploadFile(file) {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/files/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_) {}
    throw new Error(detail);
  }
  const data = await res.json();
  return { ...data, url: `${API_BASE}${data.url}` };
}

export const api = {
  login: (email, password) => request("/api/auth/login", { method: "POST", body: { email, password }, auth: false }),
  me: () => request("/api/auth/me"),

  dashboard: () => request("/api/dashboard"),
  myApprovals: () => request("/api/approvals/mine"),
  decide: (payload) => request("/api/approvals/decide", { method: "POST", body: payload }),

  contracts: (filters) => request(`/api/contracts${qs(filters)}`),
  contract: (id) => request(`/api/contracts/${id}`),
  createContract: (payload) => request("/api/contracts", { method: "POST", body: payload }),
  deleteContract: (id) => request(`/api/contracts/${id}`, { method: "DELETE" }),
  exportContracts: () => downloadFile("/api/export/contracts.xlsx", "contracts.xlsx"),

  contractors: (q) => request(`/api/contractors${qs({ q })}`),
  createContractor: (payload) => request("/api/contractors", { method: "POST", body: payload }),
  formOptions: () => request("/api/contractors/form-options"),

  uploadFile: (file) => uploadFile(file),
  documents: (filters) => request(`/api/documents${qs(filters)}`),
  log: (entityId) => request(`/api/log/${entityId}`),

  adminUsers: () => request("/api/admin/users"),
  addUser: (payload) => request("/api/admin/users", { method: "POST", body: payload }),
  updateUserRole: (email, newRole, oldRole) =>
    request(`/api/admin/users/${encodeURIComponent(email)}/role?new_role=${encodeURIComponent(newRole)}&old_role=${encodeURIComponent(oldRole)}`, { method: "PUT" }),
  removeUser: (email, role) =>
    request(`/api/admin/users/${encodeURIComponent(email)}?target_role=${encodeURIComponent(role)}`, { method: "DELETE" }),
  adminLegalEntities: () => request("/api/admin/legal-entities"),
  addLegalEntity: (payload) => request("/api/admin/legal-entities", { method: "POST", body: payload }),
  removeLegalEntity: (id) => request(`/api/admin/legal-entities/${id}`, { method: "DELETE" }),
  allRoles: () => request("/api/admin/roles"),
};
