// Business IDs are UUID strings. Numeric IDs remain supported for legacy/mock data.
export type EntityId = string | number;

export const compareIds = (a: EntityId, b: EntityId) =>
  String(a).localeCompare(String(b), 'en', { numeric: true });

export const newestOrderFirst = (
  a: { id: EntityId; orderDatetime?: string; orderNo: string },
  b: { id: EntityId; orderDatetime?: string; orderNo: string },
) => (b.orderDatetime ?? '').localeCompare(a.orderDatetime ?? '')
  || compareIds(b.orderNo, a.orderNo) || compareIds(b.id, a.id);

export const newestInvoiceFirst = (
  a: { invoiceId: EntityId; invoiceDate: string; invoiceNo: string },
  b: { invoiceId: EntityId; invoiceDate: string; invoiceNo: string },
) => b.invoiceDate.localeCompare(a.invoiceDate)
  || compareIds(b.invoiceNo, a.invoiceNo) || compareIds(b.invoiceId, a.invoiceId);
