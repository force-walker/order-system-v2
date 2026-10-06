// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { PurchasePage } from './PurchasePage';
import {
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
} from 'features/orders/services/orderItemAllocationsService';
import {
  bulkUpsertPurchaseResults,
  listPurchaseResults,
} from 'features/orders/services/purchaseService';
import { getProductDetail } from 'features/products/services/productsService';
import { getDefaultDeliveryDate } from 'features/orders/utils/deliveryDate';

vi.mock('features/orders/services/orderItemAllocationsService', () => ({
  listOrderItemAllocationWorkItems: vi.fn(),
  listSupplierFilterOptions: vi.fn(),
}));
vi.mock('features/orders/services/purchaseService', () => ({
  bulkUpsertPurchaseResults: vi.fn(),
  listPurchaseResults: vi.fn(),
}));
vi.mock('features/products/services/productsService', () => ({ getProductDetail: vi.fn() }));

const rows = [
  {
    orderItemId: 'item-a', allocationId: 11, orderId: 'order-a', orderNo: 'ORD-A',
    orderStatus: 'allocated' as const, customerName: 'Customer A', productId: 1, productName: 'Product A', orderedQty: 2,
    pricingBasis: 'uom_kg' as const,
    orderUom: 'case', purchaseUom: 'kg',
    deliveryDate: '2026-09-22', shippedDate: null, allocationStatus: 'allocated',
    proposedSupplierId: 1, proposedQty: 18.2, manualSupplierId: 1, manualQty: 18.2,
  },
  {
    orderItemId: 'item-b', allocationId: 22, orderId: 'order-b', orderNo: 'ORD-B',
    orderStatus: 'purchased' as const, customerName: 'Customer B', productId: 2, productName: 'Product B', orderedQty: 3,
    pricingBasis: 'uom_count' as const,
    orderUom: 'PC', purchaseUom: 'PC',
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
  vi.mocked(listPurchaseResults).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(getProductDetail).mockImplementation(async (id) => ({
    id,
    orderUom: id === 1 ? 'case' : 'piece',
    purchaseUom: id === 1 ? 'kg' : 'piece',
    invoiceUom: id === 1 ? 'kg' : 'piece',
    isCatchWeight: id === 1,
    weightCaptureRequired: id === 1,
  } as Awaited<ReturnType<typeof getProductDetail>>));
  vi.mocked(bulkUpsertPurchaseResults).mockResolvedValue({ count: 2, resultIds: [101, 202] });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const renderPurchasePage = () => render(<MemoryRouter><PurchasePage /></MemoryRouter>);

it('shows both orders on the same delivery date when there is no handoff filter', async () => {
  renderPurchasePage();

  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.getByText('ORD-B')).toBeTruthy();
  expect(screen.queryByRole('status')).toBeNull();
});

it('does not render the duplicate purchase work queue section', async () => {
  renderPurchasePage();
  await screen.findByText('ORD-A');
  expect(screen.queryByText('作業キュー（納品確認）')).toBeNull();
});

it('keeps an allocated uom_count CTN line visible without requiring actual weight', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...rows[0], pricingBasis: 'uom_count', orderUom: 'case', purchaseUom: 'case', manualQty: 2 }]);
  vi.mocked(getProductDetail).mockResolvedValue({
    id: 1,
    sku: 'SKU-COUNT-CTN',
    name: 'Product A',
    orderUom: 'case',
    purchaseUom: 'case',
    invoiceUom: 'case',
    pricingBasisDefault: 'uom_count',
    isCatchWeight: false,
    weightCaptureRequired: false,
    active: true,
  });
  renderPurchasePage();

  const tableRow = (await screen.findByText('ORD-A')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' }) as HTMLInputElement;
  expect(actualQty.value).toBe('2');
  await actor.click(tableRow.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));
  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ allocationId: 11, purchasedQty: 2, purchasedUom: 'case', actualWeightKg: undefined }),
  ]));
});

it('allows editing actual quantity for uom_count and saves it only as purchased quantity', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...rows[0], pricingBasis: 'uom_count', orderUom: 'case', purchaseUom: 'case', manualQty: 2 }]);
  vi.mocked(getProductDetail).mockResolvedValue({
    id: 1, sku: 'SKU-COUNT-CASE', name: 'Product A', orderUom: 'case', purchaseUom: 'case', invoiceUom: 'case',
    pricingBasisDefault: 'uom_count', isCatchWeight: false, weightCaptureRequired: false, active: true,
  });
  renderPurchasePage();

  const tableRow = (await screen.findByText('ORD-A')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' });
  await actor.clear(actualQty);
  await actor.type(actualQty, '1.5');
  await actor.click(tableRow.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ allocationId: 11, purchasedQty: 1.5, purchasedUom: 'case', actualWeightKg: undefined }),
  ]));
});

it('uses one actual quantity input for uom_kg and synchronizes purchased quantity and actual weight', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...rows[1], pricingBasis: 'uom_kg', orderUom: 'case', purchaseUom: 'kg', manualQty: 18.2,
  }]);
  vi.mocked(getProductDetail).mockResolvedValue({
    id: 2,
    sku: 'SKU-2',
    name: 'Product B',
    orderUom: 'case',
    purchaseUom: 'kg',
    invoiceUom: 'kg',
    pricingBasisDefault: 'uom_kg',
    isCatchWeight: true,
    weightCaptureRequired: true,
    active: true,
  });
  renderPurchasePage();

  const row = (await screen.findByText('ORD-B')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product B 実数量' });
  await actor.clear(actualQty);
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));
  expect(await screen.findByText('実数量の数値入力を確認してください。')).toBeTruthy();
  expect(bulkUpsertPurchaseResults).not.toHaveBeenCalled();

  await actor.type(actualQty, '18.2');
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));
  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ allocationId: 22, purchasedQty: 18.2, purchasedUom: 'kg', actualWeightKg: 18.2 }),
  ]));
});

it('calculates cross-unit shortage from allocation quantity instead of ordered quantity', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...rows[0], orderedQty: 3, orderUom: 'piece', purchaseUom: 'kg', manualQty: 3,
  }]);
  renderPurchasePage();

  const row = (await screen.findByText('ORD-A')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' });
  await actor.clear(actualQty);
  await actor.type(actualQty, '2.5');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ purchasedQty: 2.5, shortageQty: 0.5, resultStatus: 'partially_filled' }),
  ]));
});

it('moves between actual quantity and purchase unit cost with the row keyboard flow', async () => {
  renderPurchasePage();
  await screen.findByText('ORD-A');

  const actualQtyInputs = Array.from(
    document.querySelectorAll<HTMLInputElement>('input[data-actual-qty-row]'),
  );
  const unitCostInputs = Array.from(
    document.querySelectorAll<HTMLInputElement>('input[data-unitcost-row]'),
  );

  expect(actualQtyInputs).toHaveLength(2);
  expect(unitCostInputs).toHaveLength(2);

  actualQtyInputs[0].focus();
  fireEvent.keyDown(actualQtyInputs[0], { key: 'Enter' });
  expect(document.activeElement).toBe(unitCostInputs[0]);

  fireEvent.keyDown(unitCostInputs[0], { key: 'Enter' });
  expect(document.activeElement).toBe(actualQtyInputs[1]);

  unitCostInputs[1].focus();
  fireEvent.keyDown(unitCostInputs[1], { key: 'ArrowUp' });
  expect(document.activeElement).toBe(actualQtyInputs[1]);
});

it('marks a cross-unit result filled when actual equals allocation even if ordered quantity differs', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...rows[0], orderedQty: 3, orderUom: 'piece', purchaseUom: 'kg', manualQty: 18.5,
  }]);
  renderPurchasePage();

  const row = (await screen.findByText('ORD-A')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ purchasedQty: 18.5, shortageQty: undefined, resultStatus: 'filled' }),
  ]));
});

it('marks a same-unit result filled against allocation quantity rather than order quantity', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...rows[1], orderedQty: 10, orderUom: 'case', purchaseUom: 'case', manualQty: 8,
  }]);
  vi.mocked(getProductDetail).mockResolvedValue({
    id: 2, sku: 'SKU-CASE', name: 'Product B', orderUom: 'case', purchaseUom: 'case', invoiceUom: 'case',
    pricingBasisDefault: 'uom_count', isCatchWeight: false, weightCaptureRequired: false, active: true,
  });
  renderPurchasePage();

  const row = (await screen.findByText('ORD-B')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ purchasedQty: 8, purchasedUom: 'case', shortageQty: undefined, resultStatus: 'filled' }),
  ]));
});

it('uses the shared delivery date and allocated plus purchased as its default API filters', async () => {
  renderPurchasePage();
  await screen.findByText('ORD-A');

  expect((screen.getByLabelText('納品日') as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
  expect((screen.getByRole('checkbox', { name: 'Allocated' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: 'Purchased' }) as HTMLInputElement).checked).toBe(true);
  expect(listOrderItemAllocationWorkItems).toHaveBeenCalledWith({
    unallocatedOnly: false,
    deliveryDate: getDefaultDeliveryDate(),
    orderStatuses: ['allocated', 'purchased'],
  });
});

it('combines delivery date and selected status in the backend query', async () => {
  const actor = userEvent.setup();
  renderPurchasePage();
  await screen.findByText('ORD-A');

  await actor.click(screen.getByRole('checkbox', { name: 'Purchased' }));
  await actor.clear(screen.getByLabelText('納品日'));
  await actor.type(screen.getByLabelText('納品日'), '2026-09-29');

  await waitFor(() => expect(listOrderItemAllocationWorkItems).toHaveBeenLastCalledWith({
    unallocatedOnly: false,
    deliveryDate: '2026-09-29',
    orderStatuses: ['allocated'],
  }));
});

it('uses the allocation handoff once and removes it from session storage immediately', async () => {
  sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify([11]));

  renderPurchasePage();

  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.queryByText('ORD-B')).toBeNull();
  expect(screen.getByRole('status').textContent).toContain('一括割当から選択した 1 件を表示中');
  expect(sessionStorage.getItem('osv2_purchase_target_allocations')).toBeNull();
});

it('shows all orders after a reload-equivalent remount', async () => {
  sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify([11]));
  const firstView = renderPurchasePage();
  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.queryByText('ORD-B')).toBeNull();

  firstView.unmount();
  renderPurchasePage();

  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.getByText('ORD-B')).toBeTruthy();
});

it('shows all orders when the page is opened again by normal navigation', async () => {
  sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify([11]));
  const handoffView = renderPurchasePage();
  expect(await screen.findByText('ORD-A')).toBeTruthy();
  handoffView.unmount();

  renderPurchasePage();

  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.getByText('ORD-B')).toBeTruthy();
  expect(screen.queryByRole('status')).toBeNull();
});

it('clears the handoff filter from the visible control', async () => {
  const actor = userEvent.setup();
  sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify([11]));
  renderPurchasePage();
  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.queryByText('ORD-B')).toBeNull();

  await actor.click(screen.getByRole('button', { name: '全件表示' }));

  expect(screen.getByText('ORD-B')).toBeTruthy();
  expect(screen.queryByRole('status')).toBeNull();
});

it('falls back to all orders when the handed-off allocation ID is stale', async () => {
  sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify([999]));
  renderPurchasePage();

  expect(await screen.findByText('ORD-A')).toBeTruthy();
  expect(screen.getByText('ORD-B')).toBeTruthy();
  expect(screen.queryByRole('status')).toBeNull();
  expect(sessionStorage.getItem('osv2_purchase_target_allocations')).toBeNull();
});

it('saves purchase results without generating invoice drafts automatically', async () => {
  const actor = userEvent.setup();
  renderPurchasePage();

  const rowA = (await screen.findByText('ORD-A')).closest('tr');
  const rowB = screen.getByText('ORD-B').closest('tr');
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' });
  await actor.clear(actualQty);
  await actor.type(actualQty, '21.73');
  await actor.click(rowA!.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(rowB!.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (2)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledTimes(1));
  expect(bulkUpsertPurchaseResults).toHaveBeenCalledTimes(1);
  expect(bulkUpsertPurchaseResults).toHaveBeenCalledWith([
    expect.objectContaining({ allocationId: 11, purchasedQty: 21.73, purchasedUom: 'kg', actualWeightKg: 21.73 }),
    expect.objectContaining({ allocationId: 22, purchasedQty: 3, purchasedUom: 'piece', actualWeightKg: undefined }),
  ]);
  expect(await screen.findByText(/完了した注文は請求ドラフト候補に移動します/)).toBeTruthy();
});

const persistedResult = (invoiceQty: number | undefined = undefined) => ({
  id: 101,
  allocationId: 11,
  orderId: 'order-a',
  supplierId: 1,
  purchasedQty: 18.2,
  purchasedUom: 'kg',
  receivedQty: 2,
  orderUom: 'case',
  purchaseUom: 'kg',
  invoiceQty,
  invoiceUom: 'kg',
  actualWeightKg: 18.2,
  unitCost: 10,
  resultStatus: 'filled' as const,
  invoiceableFlag: true,
  recordedAt: '2026-09-27T00:00:00Z',
});

it('does not ask for overwrite confirmation when a saved purchase result is unchanged', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm');
  vi.mocked(listPurchaseResults).mockResolvedValue({ items: [persistedResult()], total: 1 });
  vi.mocked(bulkUpsertPurchaseResults).mockResolvedValue({ count: 1, resultIds: [101] });
  renderPurchasePage();

  const row = (await screen.findByText('ORD-A')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledTimes(1));
  expect(confirmSpy).not.toHaveBeenCalled();
});

it('asks before overwriting a changed unclaimed purchase result', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(listPurchaseResults).mockResolvedValue({ items: [persistedResult()], total: 1 });
  vi.mocked(bulkUpsertPurchaseResults).mockResolvedValue({ count: 1, resultIds: [101] });
  renderPurchasePage();

  const row = (await screen.findByText('ORD-A')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' });
  await actor.clear(actualQty);
  await actor.type(actualQty, '22.14');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  await waitFor(() => expect(bulkUpsertPurchaseResults).toHaveBeenCalledTimes(1));
  expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('実数量: 18.2 kg → 22.14 kg'));
});

it('shows the invoice-claim lock reason instead of attempting an overwrite', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm');
  vi.mocked(listPurchaseResults).mockResolvedValue({ items: [persistedResult(21.73)], total: 1 });
  renderPurchasePage();

  const row = (await screen.findByText('ORD-A')).closest('tr')!;
  const actualQty = screen.getByRole('spinbutton', { name: 'Product A 実数量' });
  await actor.clear(actualQty);
  await actor.type(actualQty, '22.14');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を保存 (1)' }));

  expect(await screen.findByText('請求ドラフトで使用済みのため変更できません。')).toBeTruthy();
  expect(confirmSpy).not.toHaveBeenCalled();
  expect(bulkUpsertPurchaseResults).not.toHaveBeenCalled();
});
