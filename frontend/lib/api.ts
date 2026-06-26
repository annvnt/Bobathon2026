import type {
  Alert,
  Analytics,
  ClassifyResult,
  DashboardMetrics,
  LabelDef,
  Product,
  ProductAnalytics,
  ScanResult,
  Taxonomy,
  User,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // dashboard
  metrics: (userId?: string) =>
    req<DashboardMetrics>(`/api/dashboard/metrics${userId ? `?user_id=${userId}` : ""}`),
  scan: () => req<ScanResult>(`/api/scan`, { method: "POST" }),
  analytics: (userId?: string) =>
    req<Analytics>(`/api/analytics${userId ? `?user_id=${userId}` : ""}`),
  productAnalytics: (productId: string) =>
    req<ProductAnalytics>(`/api/analytics/product/${productId}`),
  taxonomy: () => req<Taxonomy>(`/api/taxonomy`),
  labels: () => req<LabelDef[]>(`/api/labels`),
  users: () => req<User[]>(`/api/users`),
  login: (partner_id: string) =>
    req<User>(`/api/login`, {
      method: "POST",
      body: JSON.stringify({ partner_id }),
    }),

  // products
  listProducts: (userId?: string) =>
    req<Product[]>(`/api/products${userId ? `?user_id=${userId}` : ""}`),
  getProduct: (id: string) => req<Product>(`/api/products/${id}`),
  classify: (description: string, name?: string) =>
    req<ClassifyResult>(`/api/products/classify`, {
      method: "POST",
      body: JSON.stringify({ description, name }),
    }),
  createProduct: (body: Partial<Product>) =>
    req<Product>(`/api/products`, { method: "POST", body: JSON.stringify(body) }),
  deleteProduct: (id: string) =>
    req<void>(`/api/products/${id}`, { method: "DELETE" }),

  // alerts
  listAlerts: (
    params: { is_read?: boolean; user_id?: string; product_id?: string } = {},
  ) => {
    const q = new URLSearchParams();
    if (params.is_read !== undefined) q.set("is_read", String(params.is_read));
    if (params.user_id) q.set("user_id", params.user_id);
    if (params.product_id) q.set("product_id", params.product_id);
    const qs = q.toString();
    return req<Alert[]>(`/api/alerts${qs ? `?${qs}` : ""}`);
  },
  markAlertRead: (id: string) =>
    req<Alert>(`/api/alerts/${id}/read`, { method: "POST" }),
};
