import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type {
  Supplier,
  SupplierCreateRequest,
  SupplierListParams,
  SupplierListResult,
  SupplierUpdateRequest,
} from 'features/suppliers/types/supplier';

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

type ApiSupplier = {
  id: number;
  supplier_code: string;
  name: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

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

const toSupplier = (row: ApiSupplier): Supplier => ({
  id: row.id,
  supplierCode: row.supplier_code,
  name: row.name,
  active: row.active,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export const listSuppliers = async (params: SupplierListParams): Promise<SupplierListResult> => {
  const query = new URLSearchParams();
  if (params.q && params.q.trim()) query.set('q', params.q.trim());
  if (params.active === 'true') query.set('active', 'true');
  if (params.active === 'false') query.set('active', 'false');
  query.set('limit', String(params.limit));
  query.set('offset', String(params.offset));

  const res = await fetchWithAuth(`/api/v1/suppliers?${query.toString()}`);
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiSupplier[];
  const items = data.map(toSupplier);
  return {
    items,
    hasNext: items.length === params.limit,
  };
};

export const getSupplier = async (supplierId: number): Promise<Supplier | null> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}`);
  if (res.status === 404) return null;
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiSupplier;
  return toSupplier(data);
};

export const createSupplier = async (payload: SupplierCreateRequest): Promise<Supplier> => {
  const res = await fetchWithAuth('/api/v1/suppliers', {
    method: 'POST',
    body: {
      supplier_code: payload.supplierCode,
      name: payload.name,
      active: payload.active,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiSupplier;
  return toSupplier(data);
};

export const updateSupplier = async (supplierId: number, payload: SupplierUpdateRequest): Promise<Supplier> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}`, {
    method: 'PATCH',
    body: {
      name: payload.name,
      active: payload.active,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiSupplier;
  return toSupplier(data);
};

export const deactivateSupplier = async (supplierId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
};
