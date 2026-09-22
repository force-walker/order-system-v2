import type { EntityId } from 'shared/entityId';
import { apiRequestWithAuth as fetchWithAuth } from 'shared/authenticatedApiClient';
import { parseApiErrorPayload } from 'shared/error';
import { listSuppliers } from 'features/suppliers/services/suppliersService';
import type { OrderStatus } from 'features/orders/types/order';

export type OrderItemAllocationWorkItem = {
  orderItemId: EntityId;
  allocationId: number | null;
  orderId: EntityId;
  orderNo: string;
  orderStatus: OrderStatus;
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
  orderItemId: EntityId;
  suggestedSupplierId: number | null;
  suggestedQty: number | null;
  reason: string;
};

export type BulkSaveAllocationItem = {
  orderItemId: EntityId;
  supplierId: number | null;
  allocatedQty: number | null;
};

export type BulkSaveAllocationError = {
  orderItemId: EntityId;
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

type ApiWorkItem = {
  order_item_id: EntityId;
  allocation_id: number | null;
  order_id: EntityId;
  order_no: string;
  order_status: OrderStatus;
  customer_name: string;
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
  order_item_id: EntityId;
  suggested_supplier_id: number | null;
  suggested_qty: number | null;
  reason: string;
};

type ApiBulkSaveError = {
  order_item_id: EntityId;
  code: string;
  message: string;
};

type ApiBulkSaveResponse = {
  total: number;
  succeeded: number;
  failed: number;
  errors: ApiBulkSaveError[];
};

export const listSupplierFilterOptions = async (): Promise<SupplierFilterOption[]> => {
  const result = await listSuppliers({ active: 'all', includeInactive: true, limit: 200, offset: 0 });
  return result.items.map((s) => ({ id: s.id, label: `${s.id}: ${s.name}` }));
};

export const listOrderItemAllocationWorkItems = async (params: {
  unallocatedOnly: boolean;
  deliveryDate?: string;
  orderStatuses?: OrderStatus[];
  supplierId?: number;
}): Promise<OrderItemAllocationWorkItem[]> => {
  const query = new URLSearchParams();
  if (params.unallocatedOnly) query.set('unallocated_only', 'true');
  if (params.deliveryDate) query.set('delivery_date', params.deliveryDate);
  params.orderStatuses?.forEach((status) => query.append('order_status', status));
  if (params.supplierId) query.set('supplier_id', String(params.supplierId));

  const res = await fetchWithAuth(`/api/v1/order-item-allocations?${query.toString()}`);
  if (!res.ok) throw await parseApiErrorPayload(res);

  const rows = (await res.json()) as ApiWorkItem[];

  return rows.map((row) => ({
    orderItemId: row.order_item_id,
    allocationId: row.allocation_id,
    orderId: row.order_id,
    orderNo: row.order_no,
    orderStatus: row.order_status,
    customerName: row.customer_name,
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

export const suggestOrderItemAllocations = async (orderItemIds: EntityId[]): Promise<AllocationSuggestion[]> => {
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

export const generateOrderItemLabelsPdf = async (orderItemIds: EntityId[]): Promise<Blob> => {
  const res = await fetchWithAuth('/api/v1/orders/item-labels/pdf', {
    method: 'POST',
    body: { order_item_ids: orderItemIds },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return await res.blob();
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
