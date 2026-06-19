import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type { InvoiceDetailView, InvoiceDraftItem, InvoiceDraftListRow, InvoiceDraftSummary, InvoiceStatus, InvoiceSummaryRow } from 'features/orders/types/order';
import { markOrdersStatusDirty } from './ordersService';

const TOKEN_STORAGE_KEY = 'osv2_access_token';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

type ApiInvoiceSummary = {
  id: number;
  invoice_no: string;
  customer_id: number;
  invoice_date: string;
  delivery_date: string;
  subtotal: number;
  tax_total: number;
  grand_total: number;
  status: InvoiceStatus;
};

type ApiInvoiceItem = {
  id: number;
  invoice_id: number;
  order_item_id: number;
  billable_qty: number;
  billable_uom: string;
  invoice_line_status: 'uninvoiced' | 'partially_invoiced' | 'invoiced' | 'cancelled';
  sales_unit_price: number;
  unit_cost_basis?: number | null;
  auto_price_error?: string | null;
  line_amount: number;
  tax_amount: number;
  gross_margin_pct?: number | null;
  gross_margin_unavailable?: boolean;
};

type ApiInvoiceDraftListRow = {
  invoice_id: number;
  invoice_item_id: number;
  invoice_no: string;
  invoice_date: string;
  delivery_date: string;
  status: InvoiceStatus;
  order_no: string;
  customer_name: string;
  product_name: string;
  billable_qty: number;
  billable_uom: string;
  sales_unit_price: number;
  unit_cost_basis: number | null;
  auto_price_error?: string | null;
  line_amount: number;
  gross_margin_pct: number | null;
  gross_margin_unavailable: boolean;
};

type ApiInvoiceReportLine = {
  invoice_item_id: number;
  order_item_id: number;
  product_name: string;
  billable_qty: number;
  billable_uom: string;
  sales_unit_price: number;
  unit_cost_basis?: number | null;
  line_amount: number;
  tax_amount: number;
  gross_margin_pct?: number | null;
  gross_margin_unavailable?: boolean;
};

type ApiInvoiceReport = {
  invoice_id: number;
  invoice_no: string;
  status: InvoiceStatus;
  customer_id: number;
  customer_name: string;
  invoice_date: string;
  delivery_date: string;
  due_date: string | null;
  subtotal: number;
  tax_total: number;
  grand_total: number;
  items: ApiInvoiceReportLine[];
};

type ApiInvoiceBatchFinalizeResult = {
  invoice_id: number;
  ok: boolean;
  status?: InvoiceStatus | null;
  is_locked?: boolean | null;
  reason_code?: string | null;
  message?: string | null;
};

type ApiInvoiceBatchFinalizeResponse = {
  success_count: number;
  failure_count: number;
  results: ApiInvoiceBatchFinalizeResult[];
};

const INVOICE_STATUSES: InvoiceStatus[] = ['draft', 'finalized', 'sent', 'cancelled'];

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

const listInvoicesByStatus = async (status: InvoiceStatus): Promise<InvoiceDraftSummary[]> => {
  const res = await fetchWithAuth(`/api/v1/invoices?status=${status}`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiInvoiceSummary[];

  const itemCounts = await Promise.all(
    data.map(async (r) => {
      try {
        const items = await getInvoiceDraftItems(r.id);
        return [r.id, items.length] as const;
      } catch {
        return [r.id, 0] as const;
      }
    }),
  );
  const countMap = new Map<number, number>(itemCounts);

  return data.map((r) => ({
    id: r.id,
    invoiceNo: r.invoice_no,
    customerId: r.customer_id,
    invoiceDate: r.invoice_date,
    deliveryDate: r.delivery_date,
    itemCount: countMap.get(r.id) ?? 0,
    subtotal: r.subtotal,
    taxTotal: r.tax_total,
    grandTotal: r.grand_total,
    status: r.status,
  }));
};

const getInvoiceReport = async (invoiceId: number): Promise<ApiInvoiceReport> => {
  const reportRes = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/report`, { method: 'GET' });
  if (!reportRes.ok) throw await parseApiErrorPayload(reportRes);
  return (await reportRes.json()) as ApiInvoiceReport;
};

export const listInvoiceDrafts = async (): Promise<InvoiceDraftSummary[]> => {
  const res = await fetchWithAuth('/api/v1/invoices?status=draft', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiInvoiceSummary[];

  const itemCounts = await Promise.all(
    data.map(async (r) => {
      try {
        const items = await getInvoiceDraftItems(r.id);
        return [r.id, items.length] as const;
      } catch {
        return [r.id, 0] as const;
      }
    }),
  );
  const countMap = new Map<number, number>(itemCounts);

  return data.map((r) => ({
    id: r.id,
    invoiceNo: r.invoice_no,
    customerId: r.customer_id,
    invoiceDate: r.invoice_date,
    deliveryDate: r.delivery_date,
    itemCount: countMap.get(r.id) ?? 0,
    subtotal: r.subtotal,
    taxTotal: r.tax_total,
    grandTotal: r.grand_total,
    status: r.status,
  }));
};

export const getInvoiceDraftItems = async (invoiceId: number): Promise<InvoiceDraftItem[]> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/items`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiInvoiceItem[];
  return data.map((r) => ({
    id: r.id,
    orderItemId: r.order_item_id,
    billableQty: r.billable_qty,
    billableUom: r.billable_uom,
    invoiceLineStatus: r.invoice_line_status,
    salesUnitPrice: r.sales_unit_price,
    unitCostBasis: r.unit_cost_basis ?? undefined,
    autoPriceError: r.auto_price_error ?? undefined,
    lineAmount: r.line_amount,
    taxAmount: r.tax_amount,
    grossMarginPct: r.gross_margin_pct ?? undefined,
    grossMarginUnavailable: r.gross_margin_unavailable ?? false,
  }));
};

export const finalizeInvoiceItemLine = async (invoiceId: number, invoiceItemId: number): Promise<InvoiceDraftItem> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/items/${invoiceItemId}/finalize`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const r = (await res.json()) as ApiInvoiceItem;
  return {
    id: r.id,
    orderItemId: r.order_item_id,
    billableQty: r.billable_qty,
    billableUom: r.billable_uom,
    invoiceLineStatus: r.invoice_line_status,
    salesUnitPrice: r.sales_unit_price,
    autoPriceError: r.auto_price_error ?? undefined,
    lineAmount: r.line_amount,
    taxAmount: r.tax_amount,
  };
};



export const listInvoiceDraftListRows = async (): Promise<InvoiceDraftListRow[]> => {
  const rowsRes = await fetchWithAuth('/api/v1/invoices/draft-list', { method: 'GET' });
  if (!rowsRes.ok) throw await parseApiErrorPayload(rowsRes);
  const rows = (await rowsRes.json()) as ApiInvoiceDraftListRow[];

  return rows.map((r) => ({
    invoiceId: r.invoice_id,
    invoiceItemId: r.invoice_item_id,
    invoiceNo: r.invoice_no,
    invoiceDate: r.invoice_date,
    deliveryDate: r.delivery_date,
    status: r.status,
    orderNo: r.order_no,
    customerName: r.customer_name,
    productName: r.product_name,
    billableQty: r.billable_qty,
    billableUom: r.billable_uom,
    salesUnitPrice: r.sales_unit_price,
    unitCostBasis: r.unit_cost_basis ?? undefined,
    autoPriceError: r.auto_price_error ?? undefined,
    lineAmount: r.line_amount,
    grossMarginPct: r.gross_margin_pct ?? undefined,
    grossMarginUnavailable: r.gross_margin_unavailable,
  }));
};
export const updateInvoiceDraftItem = async (
  invoiceId: number,
  invoiceItemId: number,
  payload: { billableQty: number; salesUnitPrice: number },
): Promise<InvoiceDraftItem> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/items/${invoiceItemId}`, {
    method: 'PATCH',
    body: {
      billable_qty: payload.billableQty,
      sales_unit_price: payload.salesUnitPrice,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const r = (await res.json()) as ApiInvoiceItem;
  return {
    id: r.id,
    orderItemId: r.order_item_id,
    billableQty: r.billable_qty,
    billableUom: r.billable_uom,
    invoiceLineStatus: r.invoice_line_status,
    salesUnitPrice: r.sales_unit_price,
    unitCostBasis: r.unit_cost_basis ?? undefined,
    autoPriceError: r.auto_price_error ?? undefined,
    lineAmount: r.line_amount,
    taxAmount: r.tax_amount,
    grossMarginPct: r.gross_margin_pct ?? undefined,
    grossMarginUnavailable: r.gross_margin_unavailable ?? false,
  };
};

export const finalizeInvoiceDraft = async (invoiceId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/finalize`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  markOrdersStatusDirty();
};

export const finalizeInvoiceDraftsBatch = async (invoiceIds: number[]) => {
  const deduped = [...new Set(invoiceIds)];
  const res = await fetchWithAuth('/api/v1/invoices/finalize-batch', {
    method: 'POST',
    body: { invoice_ids: deduped },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiInvoiceBatchFinalizeResponse;
  if ((data.success_count ?? 0) > 0) {
    markOrdersStatusDirty();
  }
  return data;
};

export const listInvoiceSummaries = async (): Promise<InvoiceSummaryRow[]> => {
  const grouped = await Promise.all(INVOICE_STATUSES.map((status) => listInvoicesByStatus(status)));
  const all = grouped.flat();
  const reports = await Promise.all(
    all.map(async (row) => {
      try {
        return [row.id, await getInvoiceReport(row.id)] as const;
      } catch {
        return [row.id, null] as const;
      }
    }),
  );
  const reportById = new Map<number, ApiInvoiceReport | null>(reports);

  return all.map((r) => ({
    invoiceId: r.id,
    invoiceNo: r.invoiceNo,
    customerName: reportById.get(r.id)?.customer_name ?? `customer#${r.customerId}`,
    invoiceDate: r.invoiceDate,
    deliveryDate: r.deliveryDate,
    status: r.status,
    subtotal: r.subtotal,
    taxTotal: r.taxTotal,
    grandTotal: r.grandTotal,
    itemCount: reportById.get(r.id)?.items.length ?? r.itemCount,
  }));
};

export const getInvoiceDetailView = async (invoiceId: number): Promise<InvoiceDetailView> => {
  const report = await getInvoiceReport(invoiceId);

  return {
    invoiceId: report.invoice_id,
    invoiceNo: report.invoice_no,
    customerName: report.customer_name,
    invoiceDate: report.invoice_date,
    deliveryDate: report.delivery_date,
    status: report.status,
    subtotal: report.subtotal,
    taxTotal: report.tax_total,
    grandTotal: report.grand_total,
    items: report.items.map((i) => ({
      invoiceItemId: i.invoice_item_id,
      productName: i.product_name,
      billableQty: i.billable_qty,
      billableUom: i.billable_uom,
      salesUnitPrice: i.sales_unit_price,
      unitCostBasis: i.unit_cost_basis ?? undefined,
      lineAmount: i.line_amount,
      grossMarginPct: i.gross_margin_pct ?? undefined,
      grossMarginUnavailable: i.gross_margin_unavailable ?? false,
    })),
  };
};

export const generateInvoicePdf = async (invoiceId: number): Promise<Blob> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/pdf`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return await res.blob();
};
