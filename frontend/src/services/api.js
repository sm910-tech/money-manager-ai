import { getIdToken } from "./firebase";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body = null, isFormData = false, requireAuth = true } = {}) {
  const headers = {};
  if (requireAuth) {
    const token = await getIdToken();
    if (!token) {
      throw new ApiError("Please sign in with Google to access authenticated financial records.", 401);
    }
    headers.Authorization = `Bearer ${token}`;
  }

  if (body && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    const detail = data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : detail?.message || `Request failed with status ${res.status}`;
    throw new ApiError(msg, res.status, detail);
  }

  return data;
}

export function checkBackendHealth() {
  return request("/health", { requireAuth: false });
}

export function uploadCsvStatement(file, columnMapping = null) {
  const formData = new FormData();
  formData.append("file", file);
  if (columnMapping) {
    formData.append("column_mapping", JSON.stringify(columnMapping));
  }
  return request("/upload", { method: "POST", body: formData, isFormData: true });
}

export function fetchTransactions(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== "") {
      params.set(k, String(v));
    }
  });
  const qs = params.toString();
  return request(`/transactions${qs ? `?${qs}` : ""}`);
}

export function patchTransaction(transactionId, patch) {
  return request(`/transactions/${encodeURIComponent(transactionId)}`, {
    method: "PATCH",
    body: patch,
  });
}

export function fetchBudgets(month) {
  const qs = month ? `?month=${encodeURIComponent(month)}` : "";
  return request(`/budgets${qs}`);
}

export function updateBudgets(month, limits) {
  return request("/budgets", {
    method: "PUT",
    body: { month, limits },
  });
}

export function fetchAnalyticsSummary(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) sp.set(k, String(v));
  });
  const qs = sp.toString();
  return request(`/analytics/summary${qs ? `?${qs}` : ""}`);
}

export function fetchMonthlyAnalytics() {
  return request("/analytics/monthly");
}

export function sendChatMessage(message, month = null) {
  return request("/chat", {
    method: "POST",
    body: { message, ...(month ? { month } : {}) },
  });
}
