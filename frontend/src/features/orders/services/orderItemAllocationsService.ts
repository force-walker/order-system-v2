import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import { listOrders } from 'features/orders/services/ordersService';
import { listSuppliers } from 'features/suppliers/services/suppliersService';

export type OrderItemAllocationWorkItem = {
  orderItemId: number;
  allocationId: number | null;
  orderId: number | null;
  orderNo: string;
  customerName: string;
  productId: number;
  productName: string;
  orderedQty: number;
  deliveryDate: string;
  shippedDate: string | null;
  allocationStatus: 'allocated' | 'unallocated' | string;
  proposedSupplierId: number | null;
  proposedQty: number | null;
  manualSupplierId: number | null;
  manualQty: number | null;
};

export type AllocationSuggestion = {
  orderItemId: number;
  suggestedSupplierId: number | null;
  suggestedQty: number | null;
  reason: string;
};

export type BulkSaveAllocationItem = {
  orderItemId: number;
  supplierId: number | null;
  allocatedQty: number | null;
};

export type BulkSaveAllocationError = {
  orderItemId: number;
  code: string;
  message: string;
};

export type BulkSaveAllocationResponse = {
  total: number;
  succeeded: number;
  failed: number;
  errors: BulkSaveAllocationError[];
};

export type SupplierFilterOption = {
  id: number;
  label: string;
};

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

type ApiWorkItem = {
  order_item_id: number;
  allocation_id: number | null;
  order_no: string;
  product_id: number;
  product_name: string;
  ordered_qty: number;
  delivery_date: string;
  shipped_date: string | null;
  allocation_status: string;
  allocated_supplier_id: number | null;
  allocated_qty: number | null;
};

type ApiSuggestion = {
  order_item_id: number;
  suggested_supplier_id: number | null;
  suggested_qty: number | null;
  reason: string;
};

type ApiBulkSaveError = {
  order_item_id: number;
  code: string;
  message: string;
};

type ApiBulkSaveResponse = {
  total: number;
  succeeded: number;
  failed: number;
  errors: ApiBulkSaveError[];
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

export const listSupplierFilterOptions = async (): Promise<SupplierFilterOption[]> => {
  const result = await listSuppliers({ active: 'all', includeInactive: true, limit: 200, offset: 0 });
  return result.items.map((s) => ({ id: s.id, label: `${s.id}: ${s.name}` }));
};

export const listOrderItemAllocationWorkItems = async (params: {
  unallocatedOnly: boolean;
  deliveryDate?: string;
  supplierId?: number;
}): Promise<OrderItemAllocationWorkItem[]> => {
  const query = new URLSearchParams();
  if (params.unallocatedOnly) query.set('unallocated_only', 'true');
  if (params.deliveryDate) query.set('delivery_date', params.deliveryDate);
  if (params.supplierId) query.set('supplier_id', String(params.supplierId));

  const [res, orders] = await Promise.all([
    fetchWithAuth(`/api/v1/order-item-allocations?${query.toString()}`),
    listOrders().catch(() => []),
  ]);
  if (!res.ok) throw await parseApiErrorPayload(res);

  const customerByOrderNo = new Map(orders.map((o) => [o.orderNo, o.customerName]));
  const orderIdByOrderNo = new Map(orders.map((o) => [o.orderNo, o.id]));
  const rows = (await res.json()) as ApiWorkItem[];

  return rows.map((row) => ({
    orderItemId: row.order_item_id,
    allocationId: row.allocation_id,
    orderId: orderIdByOrderNo.get(row.order_no) ?? null,
    orderNo: row.order_no,
    customerName: customerByOrderNo.get(row.order_no) ?? '-',
    productId: row.product_id,
    productName: row.product_name,
    orderedQty: row.ordered_qty,
    deliveryDate: row.delivery_date,
    shippedDate: row.shipped_date,
    allocationStatus: row.allocation_status,
    proposedSupplierId: row.allocated_supplier_id,
    proposedQty: row.allocated_qty,
    manualSupplierId: row.allocated_supplier_id,
    manualQty: row.allocated_qty,
  }));
};

export const suggestOrderItemAllocations = async (orderItemIds: number[]): Promise<AllocationSuggestion[]> => {
  const res = await fetchWithAuth('/api/v1/order-item-allocations/suggestions', {
    method: 'POST',
    body: { order_item_ids: orderItemIds },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const rows = (await res.json()) as ApiSuggestion[];
  return rows.map((row) => ({
    orderItemId: row.order_item_id,
    suggestedSupplierId: row.suggested_supplier_id,
    suggestedQty: row.suggested_qty,
    reason: row.reason,
  }));
};

export const bulkSaveOrderItemAllocations = async (items: BulkSaveAllocationItem[]): Promise<BulkSaveAllocationResponse> => {
  const res = await fetchWithAuth('/api/v1/order-item-allocations/bulk-save', {
    method: 'POST',
    body: {
      items: items.map((row) => ({
        order_item_id: row.orderItemId,
        supplier_id: row.supplierId,
        allocated_qty: row.allocatedQty,
      })),
      override_reason_code: 'bulk_manual',
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiBulkSaveResponse;
  return {
    total: data.total,
    succeeded: data.succeeded,
    failed: data.failed,
    errors: data.errors.map((e) => ({ orderItemId: e.order_item_id, code: e.code, message: e.message })),
  };
};
