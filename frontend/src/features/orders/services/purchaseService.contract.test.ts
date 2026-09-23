import { beforeEach, expect, it, vi } from 'vitest';
import { apiRequestWithAuth } from 'shared/authenticatedApiClient';
import { bulkUpsertPurchaseResults, generateDraftInvoiceFromPurchase } from './purchaseService';

vi.mock('shared/authenticatedApiClient', () => ({ apiRequestWithAuth: vi.fn() }));

const request = vi.mocked(apiRequestWithAuth);

beforeEach(() => {
  request.mockReset();
});

it('maps bulk-upsert response IDs to the frontend contract', async () => {
  request.mockResolvedValueOnce(Response.json({
    upserted_count: 2,
    purchase_result_ids: [101, 202],
  }));

  const result = await bulkUpsertPurchaseResults([
    {
      allocationId: 11,
      purchasedQty: 2,
      purchasedUom: 'count',
      actualWeightKg: 21.73,
      resultStatus: 'filled',
      invoiceableFlag: true,
    },
    {
      allocationId: 22,
      purchasedQty: 3,
      purchasedUom: 'count',
      resultStatus: 'filled',
      invoiceableFlag: true,
    },
  ]);

  expect(result).toEqual({ count: 2, resultIds: [101, 202] });
  expect(request).toHaveBeenCalledWith('/api/v1/purchase-results/bulk-upsert', {
    method: 'POST',
    body: {
      items: [
        expect.objectContaining({ allocation_id: 11, purchased_qty: 2, actual_weight_kg: 21.73 }),
        expect.objectContaining({ allocation_id: 22, purchased_qty: 3 }),
      ],
    },
  });
  const body = request.mock.calls[0][1]?.body as { items: Array<Record<string, unknown>> };
  expect(body.items[0]).not.toHaveProperty('invoice_qty');
});

it('sends purchase-result IDs and consumes invoice_id without a frontend draft number', async () => {
  request.mockResolvedValueOnce(Response.json({ invoice_id: 'invoice-uuid' }));

  const invoiceId = await generateDraftInvoiceFromPurchase({
    orderId: 'order-uuid',
    invoiceDate: '2026-09-22',
    purchaseResultIds: [101, 202],
  });

  expect(invoiceId).toBe('invoice-uuid');
  expect(request).toHaveBeenCalledWith('/api/v1/invoices/generate-draft-from-purchase-results', {
    method: 'POST',
    body: {
      order_id: 'order-uuid',
      invoice_date: '2026-09-22',
      purchase_result_ids: [101, 202],
    },
  });
  const body = request.mock.calls[0][1]?.body as Record<string, unknown>;
  expect(body).not.toHaveProperty('invoice_no');
  expect(JSON.stringify(body)).not.toContain('DRAFT-');
});
