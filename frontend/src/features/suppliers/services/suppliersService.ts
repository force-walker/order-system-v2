import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type {
  Supplier,
  SupplierCreateRequest,
  SupplierListParams,
  SupplierListResult,
  SupplierProductMapping,
  SupplierProductMappingCreateRequest,
  SupplierProductMappingUpdateRequest,
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

type ApiSupplierProductMapping = {
  id: number;
  supplier_id: number;
  product_id: number;
  priority: number;
  is_preferred: boolean;
  default_unit_cost: number | null;
  lead_time_days: number | null;
  note: string | null;
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
  if (params.includeInactive) query.set('include_inactive', 'true');
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

export const archiveSupplier = async (supplierId: number): Promise<Supplier> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/archive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiSupplier;
  return toSupplier(data);
};

export const unarchiveSupplier = async (supplierId: number): Promise<Supplier> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/unarchive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiSupplier;
  return toSupplier(data);
};

const toSupplierProductMapping = (row: ApiSupplierProductMapping): SupplierProductMapping => ({
  id: row.id,
  supplierId: row.supplier_id,
  productId: row.product_id,
  priority: row.priority,
  isPreferred: row.is_preferred,
  defaultUnitCost: row.default_unit_cost,
  leadTimeDays: row.lead_time_days,
  note: row.note,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export const listSupplierProductMappings = async (supplierId: number): Promise<SupplierProductMapping[]> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/products`);
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiSupplierProductMapping[];
  return data.map(toSupplierProductMapping);
};

export const createSupplierProductMapping = async (
  supplierId: number,
  payload: SupplierProductMappingCreateRequest,
): Promise<SupplierProductMapping> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/products`, {
    method: 'POST',
    body: {
      product_id: payload.productId,
      priority: payload.priority,
      is_preferred: payload.isPreferred,
      default_unit_cost: payload.defaultUnitCost,
      lead_time_days: payload.leadTimeDays,
      note: payload.note,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiSupplierProductMapping;
  return toSupplierProductMapping(data);
};

export const updateSupplierProductMapping = async (
  supplierId: number,
  productId: number,
  payload: SupplierProductMappingUpdateRequest,
): Promise<SupplierProductMapping> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/products/${productId}`, {
    method: 'PATCH',
    body: {
      priority: payload.priority,
      is_preferred: payload.isPreferred,
      default_unit_cost: payload.defaultUnitCost,
      lead_time_days: payload.leadTimeDays,
      note: payload.note,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiSupplierProductMapping;
  return toSupplierProductMapping(data);
};

export const deleteSupplierProductMapping = async (supplierId: number, productId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}/products/${productId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
};

export const deleteSupplier = async (supplierId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/suppliers/${supplierId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
};

export const deactivateSupplier = deleteSupplier;
