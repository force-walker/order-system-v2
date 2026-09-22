import type { EntityId } from 'shared/entityId';
import { apiRequestWithAuth as fetchWithAuth } from 'shared/authenticatedApiClient';
import { parseApiErrorPayload } from 'shared/error';
import { currentUser } from 'shared/authSession';
import type {
  PurchaseResultCreateRequest,
  PurchaseResultFilter,
  PurchaseResultItem,
  PurchaseResultResponse,
  PurchaseResultStatus,
} from 'features/orders/types/order';

type ApiPurchaseResultResponse = {
  id: number;
  allocation_id: number;
  order_id?: EntityId | null;
  supplier_id: number | null;
  supplier_name?: string | null;
  customer_id?: number | null;
  customer_name?: string | null;
  product_id?: number | null;
  product_name?: string | null;
  purchased_qty: number;
  purchased_uom: string;
  received_qty?: number | null;
  order_uom?: string | null;
  invoice_qty?: number | null;
  invoice_uom?: string | null;
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
  is_deferred?: boolean;
  defer_until?: string | null;
  defer_reason?: string | null;
  deferred_by?: string | null;
  deferred_at?: string | null;
};

const toItem = (row: ApiPurchaseResultResponse): PurchaseResultItem => ({
  id: row.id,
  allocationId: row.allocation_id,
  orderId: row.order_id ?? undefined,
  supplierId: row.supplier_id ?? undefined,
  supplierName: row.supplier_name ?? undefined,
  customerId: row.customer_id ?? undefined,
  customerName: row.customer_name ?? undefined,
  productId: row.product_id ?? undefined,
  productName: row.product_name ?? undefined,
  purchasedQty: row.purchased_qty,
  purchasedUom: row.purchased_uom,
  receivedQty: row.received_qty ?? undefined,
  orderUom: row.order_uom ?? undefined,
  invoiceQty: row.invoice_qty ?? undefined,
  invoiceUom: row.invoice_uom ?? undefined,
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
  isDeferred: row.is_deferred,
  deferUntil: row.defer_until ?? undefined,
  deferReason: row.defer_reason ?? undefined,
  deferredBy: row.deferred_by ?? undefined,
  deferredAt: row.deferred_at ?? undefined,
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
  const res = await fetchWithAuth(`/api/v1/purchase-results/queue/history?${query}`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiPurchaseResultResponse[];
  const items = data.map(toItem);

  return {
    items,
    total: items.length,
  };
};

export const listPurchaseWorkQueue = async (): Promise<PurchaseResultResponse> => {
  const res = await fetchWithAuth('/api/v1/purchase-results/queue/work-queue', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiPurchaseResultResponse[];
  const items = data.map(toItem);
  return { items, total: items.length };
};

export const deferPurchaseResult = async (resultId: number, deferReason: string): Promise<PurchaseResultItem> => {
  const user = await currentUser();
  const res = await fetchWithAuth(`/api/v1/purchase-results/${resultId}/defer`, {
    method: 'POST',
    body: { defer_reason: deferReason, deferred_by: user.user_id },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return toItem((await res.json()) as ApiPurchaseResultResponse);
};

export const undeferPurchaseResult = async (resultId: number): Promise<PurchaseResultItem> => {
  const res = await fetchWithAuth(`/api/v1/purchase-results/${resultId}/undefer`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return toItem((await res.json()) as ApiPurchaseResultResponse);
};

export const generateDraftInvoiceFromPurchase = async (payload: { orderId: EntityId; invoiceDate: string; purchaseResultIds: number[] }): Promise<EntityId> => {
  const res = await fetchWithAuth('/api/v1/invoices/generate-draft-from-purchase-results', {
    method: 'POST',
    body: {
      order_id: payload.orderId,
      invoice_date: payload.invoiceDate,
      purchase_result_ids: payload.purchaseResultIds,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as { invoice_id: EntityId };
  return data.invoice_id;
};

const toRequestBody = (payload: PurchaseResultCreateRequest) => ({
  allocation_id: payload.allocationId,
  supplier_id: payload.supplierId ?? null,
  purchased_qty: payload.purchasedQty,
  purchased_uom: payload.purchasedUom,
  actual_weight_kg: payload.actualWeightKg ?? null,
  invoice_qty: payload.invoiceQty ?? null,
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

export const bulkUpsertPurchaseResults = async (items: PurchaseResultCreateRequest[]): Promise<{ count: number; resultIds: number[] }> => {
  const res = await fetchWithAuth('/api/v1/purchase-results/bulk-upsert', {
    method: 'POST',
    body: { items: items.map(toRequestBody) },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as { upserted_count: number; purchase_result_ids: number[] };
  return { count: data.upserted_count, resultIds: data.purchase_result_ids };
};
