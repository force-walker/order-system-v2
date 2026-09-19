import type { EntityId } from 'shared/entityId';
import { apiRequestWithAuth as fetchWithAuth } from 'shared/authenticatedApiClient';
import { parseApiErrorPayload } from 'shared/error';

export type ShippingReportMode = 'supplier_product' | 'customer';

export type ShippingReportRow = {
  orderItemId: EntityId;
  shippedDate: string;
  supplierName: string;
  customerName: string;
  productName: string;
  quantity: number;
  unit: string;
};

type ApiShippingReportRow = {
  order_item_id: EntityId;
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
    orderItemId: r.order_item_id,
    shippedDate: r.shipped_date,
    supplierName: r.supplier_name,
    customerName: r.customer_name,
    productName: r.product_name,
    quantity: r.quantity,
    unit: r.unit,
  }));
};

export const generatePurchaseConfirmationPdf = async (selectedIds: EntityId[]): Promise<Blob> => {
  const res = await fetchWithAuth('/api/v1/reports/purchase-confirmation/pdf', {
    method: 'POST',
    body: { selected_ids: selectedIds, sort: 'product_desc' },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return await res.blob();
};
