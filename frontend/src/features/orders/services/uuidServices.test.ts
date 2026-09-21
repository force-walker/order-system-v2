import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { apiRequestWithAuth } from 'shared/authenticatedApiClient';
import { getInvoiceDraftItems, finalizeInvoiceItemLine } from './invoiceService';
import { suggestOrderItemAllocations, bulkSaveOrderItemAllocations } from './orderItemAllocationsService';
import { generatePurchaseConfirmationPdf } from './shippingReportService';
import { newestOrderFirst, newestInvoiceFirst } from 'shared/entityId';

vi.mock('shared/authenticatedApiClient', () => ({ apiRequestWithAuth: vi.fn() }));
const request = vi.mocked(apiRequestWithAuth);
const id = '30ae4186-04b9-4a13-985b-79edf1d061bc';
const itemId = '57048d30-023a-4886-a623-3ef334c8d51c';
beforeEach(() => { request.mockReset(); });
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

it('creates the order header and items with one atomic request', async () => {
  vi.stubEnv('VITE_USE_MOCK', 'false');
  vi.stubEnv('VITE_DEBUG_ORDER_ITEM_FIELDS', 'false');
  vi.resetModules();
  const { createOrder } = await import('./ordersService');
  const order = {
    id,
    customer_id: 1,
    order_no: 'ORD-TEST',
    order_datetime: '2026-09-20T00:00:00Z',
    delivery_date: '2026-09-20',
    shipped_date: null,
    status: 'new',
    note: null,
    created_at: '2026-09-20T00:00:00Z',
  };
  const item = {
    id: itemId,
    order_id: id,
    product_id: 5,
    ordered_qty: 2,
    order_uom_type: 'uom_count',
    estimated_weight_kg: null,
    target_price: null,
    price_ceiling: null,
    stockout_policy: null,
    pricing_basis: 'uom_count',
    unit_price_uom_count: 100,
    unit_price_uom_kg: null,
    note: null,
    comment: null,
  };
  request.mockResolvedValueOnce(Response.json({ order, items: [item] }));

  const created = await createOrder({
    customerId: 1,
    customerName: 'Test Customer',
    deliveryDate: '2026-09-20',
    items: [{ productId: 5, productName: 'Test Product', quantity: 2, unit: 'count', unitPrice: 100, pricingBasis: 'uom_count' }],
  });

  expect(created.id).toBe(id);
  expect(created.items).toHaveLength(1);
  expect(request).toHaveBeenCalledTimes(1);
  expect(request).toHaveBeenCalledWith('/api/v1/orders/with-items', {
    method: 'POST',
    body: expect.objectContaining({
      customer_id: 1,
      items: [expect.objectContaining({ product_id: 5, ordered_qty: 2 })],
    }),
  });
});

it('updates an existing UUID line without deleting and recreating it', async () => {
  vi.stubEnv('VITE_USE_MOCK', 'false');
  vi.stubEnv('VITE_DEBUG_ORDER_ITEM_FIELDS', 'false');
  vi.resetModules();
  const { updateOrder } = await import('./ordersService');
  const order = { id, customer_id: 1, order_no: 'TEST', order_datetime: '', delivery_date: '2026-09-20', status: 'new', created_at: '' };
  const line = { id: itemId, order_id: id, product_id: 1, ordered_qty: 2, pricing_basis: 'uom_count', unit_price_uom_count: 5 };
  request.mockImplementation(async (url, options) => {
    if (options?.method === 'PATCH') return Response.json({});
    if (url.endsWith('/items')) return Response.json([line]);
    if (url === `/api/v1/orders/${id}`) return Response.json(order);
    return Response.json([]);
  });
  const result = await updateOrder(id, { customerId: 1, customerName: 'Test', deliveryDate: '2026-09-20', items: [{ id: itemId, productId: 1, productName: 'Test', quantity: 2, unit: 'kg', unitPrice: 5, pricingBasis: 'uom_count' }] });
  expect(result.id).toBe(id);
  expect(request).toHaveBeenCalledWith(`/api/v1/orders/${id}/items/${itemId}`, expect.objectContaining({ method: 'PATCH' }));
  expect(request.mock.calls.some(([, options]) => ['POST', 'DELETE'].includes(options?.method ?? ''))).toBe(false);
});

it('retains invoice and line UUIDs in request URLs and responses', async () => {
  const line = { id: itemId, order_item_id: id };
  request.mockResolvedValueOnce(Response.json([line])).mockResolvedValueOnce(Response.json(line));
  expect((await getInvoiceDraftItems(id))[0]).toMatchObject({ id: itemId, orderItemId: id });
  await finalizeInvoiceItemLine(id, itemId);
  expect(request.mock.calls.map(([url]) => url)).toEqual([
    `/api/v1/invoices/${id}/items`, `/api/v1/invoices/${id}/items/${itemId}/finalize`,
  ]);
});
it('retains allocation UUIDs and partial failure IDs while supplier IDs stay numeric', async () => {
  request.mockResolvedValueOnce(Response.json([])).mockResolvedValueOnce(Response.json({ total: 1, succeeded: 0, failed: 1, errors: [{ order_item_id: itemId, code: 'CONFLICT', message: 'test' }] }));
  await suggestOrderItemAllocations([itemId]);
  const result = await bulkSaveOrderItemAllocations([{ orderItemId: itemId, supplierId: 7, allocatedQty: 2 }]);
  expect(request.mock.calls[0][1]?.body).toEqual({ order_item_ids: [itemId] });
  expect(request.mock.calls[1][1]?.body).toMatchObject({ items: [{ order_item_id: itemId, supplier_id: 7, allocated_qty: 2 }] });
  expect(result.errors[0].orderItemId).toBe(itemId);
});
it('sends selected UUIDs to the shipping PDF API', async () => {
  request.mockResolvedValue(new Response('PDF'));
  await generatePurchaseConfirmationPdf([itemId]);
  expect(request.mock.calls[0][1]?.body).toEqual({ selected_ids: [itemId], sort: 'product_desc' });
});
it('sorts by dates rather than subtracting UUIDs', () => {
  const old = { id, orderNo: 'ORD-1', orderDatetime: '2026-09-01' };
  const recent = { id: itemId, orderNo: 'ORD-2', orderDatetime: '2026-09-20' };
  expect([old, recent].sort(newestOrderFirst)).toEqual([recent, old]);
  expect(newestInvoiceFirst({ invoiceId: id, invoiceNo: 'INV-2', invoiceDate: '2026-09-20' }, { invoiceId: itemId, invoiceNo: 'INV-1', invoiceDate: '2026-09-01' })).toBeLessThan(0);
});
