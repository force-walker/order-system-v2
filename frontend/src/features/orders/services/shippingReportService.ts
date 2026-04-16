import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

const TOKEN_STORAGE_KEY = 'osv2_access_token';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

const ensureDevToken = async (): Promise<string> => {
  const cached = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (cached) return cached;

  const loginBody: ApiLoginRequest = { user_id: DEV_LOGIN_USER, role: DEV_LOGIN_ROLE };
  const res = await apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: loginBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiTokenResponse;
  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
  return data.access_token;
};

const fetchWithAuth = async (path: string, init?: { method?: string; body?: unknown }) => {
  const token = await ensureDevToken();
  const res = await apiRequest(path, {
    method: init?.method ?? 'GET',
    body: init?.body,
    authToken: token,
  });
  if (res.status === 401) localStorage.removeItem(TOKEN_STORAGE_KEY);
  return res;
};

export type ShippingReportMode = 'supplier_product' | 'customer';

export type ShippingReportRow = {
  shippedDate: string;
  supplierName: string;
  customerName: string;
  productName: string;
  quantity: number;
  unit: string;
};

type ApiShippingReportRow = {
  shipped_date: string;
  supplier_name: string;
  customer_name: string;
  product_name: string;
  quantity: number;
  unit: string;
};

export const getShippingReport = async (shippedDate: string, mode: ShippingReportMode): Promise<ShippingReportRow[]> => {
  const query = new URLSearchParams({ shipped_date: shippedDate, mode });
  const res = await fetchWithAuth(`/api/v1/reports/shipping?${query.toString()}`);
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiShippingReportRow[];
  return data.map((r) => ({
    shippedDate: r.shipped_date,
    supplierName: r.supplier_name,
    customerName: r.customer_name,
    productName: r.product_name,
    quantity: r.quantity,
    unit: r.unit,
  }));
};
