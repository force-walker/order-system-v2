// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { PurchasePage } from './PurchasePage';
import {
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
} from 'features/orders/services/orderItemAllocationsService';
import {
  bulkUpsertPurchaseResults,
  generateDraftInvoiceFromPurchase,
  listPurchaseResults,
  listPurchaseWorkQueue,
} from 'features/orders/services/purchaseService';
import { getProductDetail } from 'features/products/services/productsService';

vi.mock('features/orders/services/orderItemAllocationsService', () => ({
  listOrderItemAllocationWorkItems: vi.fn(),
  listSupplierFilterOptions: vi.fn(),
}));
vi.mock('features/orders/services/purchaseService', () => ({
  bulkUpsertPurchaseResults: vi.fn(),
  generateDraftInvoiceFromPurchase: vi.fn(),
  listPurchaseResults: vi.fn(),
  listPurchaseWorkQueue: vi.fn(),
}));
vi.mock('features/products/services/productsService', () => ({ getProductDetail: vi.fn() }));

const rows = [
  {
    orderItemId: 'item-a', allocationId: 11, orderId: 'order-a', orderNo: 'ORD-A',
    orderStatus: 'confirmed' as const, customerName: 'Customer A', productId: 1, productName: 'Product A', orderedQty: 2,
    deliveryDate: '2026-09-22', shippedDate: null, allocationStatus: 'allocated',
    proposedSupplierId: 1, proposedQty: 2, manualSupplierId: 1, manualQty: 2,
  },
  {
    orderItemId: 'item-b', allocationId: 22, orderId: 'order-b', orderNo: 'ORD-B',
    orderStatus: 'confirmed' as const, customerName: 'Customer B', productId: 2, productName: 'Product B', orderedQty: 3,
    deliveryDate: '2026-09-22', shippedDate: null, allocationStatus: 'allocated',
    proposedSupplierId: 2, proposedQty: 3, manualSupplierId: 2, manualQty: 3,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue(rows);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([
    { id: 1, label: '1: Supplier A' },
    { id: 2, label: '2: Supplier B' },
  ]);
  vi.mocked(listPurchaseWorkQueue).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(listPurchaseResults).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(getProductDetail).mockImplementation(async (id) => ({
    id,
    orderUom: id === 1 ? 'CTN' : 'PC',
    purchaseUom: id === 1 ? 'CTN' : 'PC',
    invoiceUom: id === 1 ? 'KG' : 'PC',
    isCatchWeight: id === 1,
    weightCaptureRequired: id === 1,
  } as Awaited<ReturnType<typeof getProductDetail>>));
  vi.mocked(bulkUpsertPurchaseResults).mockResolvedValue({ count: 2, resultIds: [101, 202] });
  vi.mocked(generateDraftInvoiceFromPurchase)
    .mockResolvedValueOnce('invoice-a')
    .mockResolvedValueOnce('invoice-b');
});

afterEach(() => cleanup());

it('passes only each order\'s returned purchase-result IDs to draft generation', async () => {
  const actor = userEvent.setup();
  render(<MemoryRouter><PurchasePage /></MemoryRouter>);

  const rowA = (await screen.findByText('ORD-A')).closest('tr');
  const rowB = screen.getByText('ORD-B').closest('tr');
  await actor.type(screen.getByRole('spinbutton', { name: 'Product A 実測重量' }), '21.73');
  await actor.click(rowA!.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(rowB!.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (2)' }));

  await waitFor(() => expect(generateDraftInvoiceFromPurchase).toHaveBeenCalledTimes(2));
  expect(bulkUpsertPurchaseResults).toHaveBeenCalledTimes(1);
  expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ allocationId: 11, purchasedUom: 'CTN', actualWeightKg: 21.73 }),
    expect.objectContaining({ allocationId: 22, purchasedUom: 'PC', actualWeightKg: undefined }),
  ]);
  expect(generateDraftInvoiceFromPurchase).toHaveBeenNthCalledWith(1, {
    orderId: 'order-a',
    invoiceDate: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    purchaseResultIds: [101],
  });
  expect(generateDraftInvoiceFromPurchase).toHaveBeenNthCalledWith(2, {
    orderId: 'order-b',
    invoiceDate: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    purchaseResultIds: [202],
  });
  expect(JSON.stringify(vi.mocked(generateDraftInvoiceFromPurchase).mock.calls)).not.toContain('DRAFT-');
});
