import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type { InvoiceDraftItem, InvoiceDraftListRow, InvoiceDraftSummary, InvoiceStatus } from 'features/orders/types/order';

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
  order_item_id: number;
  billable_qty: number;
  billable_uom: string;
  sales_unit_price: number;
  line_amount: number;
  tax_amount: number;
};

type ApiInvoiceDraftListRow = {
  invoice_id: number;
  invoice_item_id: number;
  order_no: string;
  customer_name: string;
  product_name: string;
  billable_qty: number;
  billable_uom: string;
  sales_unit_price: number;
  unit_cost_basis: number | null;
  line_amount: number;
  gross_margin_pct: number | null;
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
    salesUnitPrice: r.sales_unit_price,
    lineAmount: r.line_amount,
    taxAmount: r.tax_amount,
  }));
};



export const listInvoiceDraftListRows = async (): Promise<InvoiceDraftListRow[]> => {
  const [rowsRes, summaries] = await Promise.all([
    fetchWithAuth('/api/v1/invoices/draft-list', { method: 'GET' }),
    listInvoiceDrafts(),
  ]);
  if (!rowsRes.ok) throw await parseApiErrorPayload(rowsRes);
  const rows = (await rowsRes.json()) as ApiInvoiceDraftListRow[];

  const summaryById = new Map<number, InvoiceDraftSummary>();
  summaries.forEach((s) => summaryById.set(s.id, s));

  return rows.map((r) => {
    const s = summaryById.get(r.invoice_id);
    return {
      invoiceId: r.invoice_id,
      invoiceItemId: r.invoice_item_id,
      orderNo: r.order_no,
      customerName: r.customer_name,
      productName: r.product_name,
      billableQty: r.billable_qty,
      billableUom: r.billable_uom,
      salesUnitPrice: r.sales_unit_price,
      unitCostBasis: r.unit_cost_basis ?? undefined,
      lineAmount: r.line_amount,
      grossMarginPct: r.gross_margin_pct ?? undefined,
      deliveryDate: s?.deliveryDate,
      status: s?.status,
    };
  });
};
export const finalizeInvoiceDraft = async (invoiceId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/invoices/${invoiceId}/finalize`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
};
