import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type {
  PurchaseResultCreateRequest,
  PurchaseResultFilter,
  PurchaseResultItem,
  PurchaseResultResponse,
  PurchaseResultStatus,
} from 'features/orders/types/order';

const TOKEN_STORAGE_KEY = 'osv2_access_token';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

type ApiPurchaseResultResponse = {
  id: number;
  allocation_id: number;
  supplier_id: number | null;
  purchased_qty: number;
  purchased_uom: string;
  actual_weight_kg: number | null;
  unit_cost: number | null;
  final_unit_cost: number | null;
  shortage_qty: number | null;
  shortage_policy: string | null;
  result_status: PurchaseResultStatus;
  invoiceable_flag: boolean;
  recorded_by: string | null;
  recorded_at: string;
  note: string | null;
};

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
    method: init?.method,
    body: init?.body,
    authToken: token,
  });

  if (res.status === 401) localStorage.removeItem(TOKEN_STORAGE_KEY);
  return res;
};

const toItem = (row: ApiPurchaseResultResponse): PurchaseResultItem => ({
  id: row.id,
  allocationId: row.allocation_id,
  supplierId: row.supplier_id ?? undefined,
  purchasedQty: row.purchased_qty,
  purchasedUom: row.purchased_uom,
  actualWeightKg: row.actual_weight_kg ?? undefined,
  unitCost: row.unit_cost ?? undefined,
  finalUnitCost: row.final_unit_cost ?? undefined,
  shortageQty: row.shortage_qty ?? undefined,
  shortagePolicy: row.shortage_policy ?? undefined,
  resultStatus: row.result_status,
  invoiceableFlag: row.invoiceable_flag,
  recordedBy: row.recorded_by ?? undefined,
  recordedAt: row.recorded_at,
  note: row.note ?? undefined,
});

const toQuery = (filter: PurchaseResultFilter): string => {
  const params = new URLSearchParams();
  if (filter.allocationId) params.set('allocation_id', String(filter.allocationId));
  if (filter.supplierId) params.set('supplier_id', String(filter.supplierId));
  params.set('limit', String(filter.limit ?? 100));
  params.set('offset', String(filter.offset ?? 0));
  return params.toString();
};

export const listPurchaseResults = async (filter: PurchaseResultFilter = {}): Promise<PurchaseResultResponse> => {
  const query = toQuery(filter);
  const res = await fetchWithAuth(`/api/v1/purchase-results?${query}`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiPurchaseResultResponse[];
  const items = data.map(toItem);

  return {
    items,
    total: items.length,
  };
};

const toRequestBody = (payload: PurchaseResultCreateRequest) => ({
  allocation_id: payload.allocationId,
  supplier_id: payload.supplierId ?? null,
  purchased_qty: payload.purchasedQty,
  purchased_uom: payload.purchasedUom,
  actual_weight_kg: payload.actualWeightKg ?? null,
  unit_cost: payload.unitCost ?? null,
  final_unit_cost: payload.finalUnitCost ?? null,
  shortage_qty: payload.shortageQty ?? null,
  shortage_policy: payload.shortagePolicy ?? null,
  result_status: payload.resultStatus,
  invoiceable_flag: payload.invoiceableFlag,
  recorded_by: payload.recordedBy ?? null,
  note: payload.note ?? null,
});

export const createPurchaseResult = async (payload: PurchaseResultCreateRequest): Promise<PurchaseResultItem> => {
  const res = await fetchWithAuth('/api/v1/purchase-results', {
    method: 'POST',
    body: toRequestBody(payload),
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiPurchaseResultResponse;
  return toItem(data);
};

export const bulkUpsertPurchaseResults = async (items: PurchaseResultCreateRequest[]): Promise<number> => {
  const res = await fetchWithAuth('/api/v1/purchase-results/bulk-upsert', {
    method: 'POST',
    body: { items: items.map(toRequestBody) },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as { upserted_count: number };
  return data.upserted_count;
};
