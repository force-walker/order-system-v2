// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { OrderItemBulkAllocationPage } from './OrderItemBulkAllocationPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import {
  bulkSaveOrderItemAllocations,
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
} from '../services/orderItemAllocationsService';
import {
  createSupplierProductMappingGlobal,
  listProductSupplierMappings,
} from 'features/suppliers/services/suppliersService';
import { ServiceError } from 'shared/error';

vi.mock('../services/orderItemAllocationsService', () => ({
  listOrderItemAllocationWorkItems: vi.fn(),
  listSupplierFilterOptions: vi.fn(),
  bulkSaveOrderItemAllocations: vi.fn(),
  generateOrderItemLabelsPdf: vi.fn(),
  suggestOrderItemAllocations: vi.fn(),
}));
vi.mock('features/suppliers/services/suppliersService', () => ({
  createSupplierProductMappingGlobal: vi.fn(),
  listProductSupplierMappings: vi.fn(),
}));

const mapping = (supplierId = 1, productId = 1) => ({
  id: 100,
  supplierId,
  productId,
  priority: 100,
  isPreferred: false,
  defaultUnitCost: null,
  leadTimeDays: null,
  note: null,
  createdAt: '2026-10-06T00:00:00Z',
  updatedAt: '2026-10-06T00:00:00Z',
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([]);
  vi.mocked(bulkSaveOrderItemAllocations).mockResolvedValue({ total: 1, succeeded: 1, failed: 0, errors: [] });
  vi.mocked(listProductSupplierMappings).mockImplementation(async (productId) => [mapping(1, productId)]);
  vi.mocked(createSupplierProductMappingGlobal).mockResolvedValue(mapping());
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('defaults to confirmed and allocated orders on the shared delivery date', async () => {
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  await screen.findByText('条件に合う受注アイテムがありません。');
  expect((screen.getByRole('checkbox', { name: '確定' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '引当済' }) as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByRole('checkbox', { name: '新規' })).toBeNull();
  expect(screen.getByRole('button', { name: '茶屋札PDF作成' })).toBeTruthy();
  expect((screen.getByLabelText('納品日') as HTMLInputElement).value).toBe(getDefaultDeliveryDate());

  await waitFor(() => expect(listOrderItemAllocationWorkItems).toHaveBeenCalledWith({
    unallocatedOnly: false,
    deliveryDate: getDefaultDeliveryDate(),
    orderStatuses: ['confirmed', 'allocated'],
    supplierId: undefined,
  }));
});

const savedRow = {
  orderItemId: 'item-1',
  allocationId: 11,
  orderId: 'order-1',
  orderNo: 'ORD-1',
  orderStatus: 'allocated' as const,
  customerName: 'Customer A',
  productId: 1,
  productName: 'Product A',
  pricingBasis: 'uom_count' as const,
  orderedQty: 2,
  orderUom: 'count',
  purchaseUom: 'count',
  deliveryDate: getDefaultDeliveryDate(),
  shippedDate: null,
  allocationStatus: 'allocated' as const,
  proposedSupplierId: 1,
  proposedQty: 2,
  manualSupplierId: 1,
  manualQty: 2,
};

it('does not show an overwrite warning for the first save of an unsaved allocation', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm');
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...savedRow,
    allocationId: 99,
    allocationStatus: 'unallocated',
    proposedSupplierId: null,
    proposedQty: null,
    manualSupplierId: null,
    manualQty: null,
  }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.type(row.querySelector<HTMLInputElement>('input[type="number"]')!, '2');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1));
  expect(confirmSpy).not.toHaveBeenCalled();
});

it('blocks selected rows without a final supplier before calling the API', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...savedRow,
    allocationId: null,
    allocationStatus: 'unallocated',
    manualSupplierId: null,
    manualQty: 2,
  }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const tableRow = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.click(tableRow.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  expect(await screen.findByText('仕入先を選択してください')).toBeTruthy();
  expect(bulkSaveOrderItemAllocations).not.toHaveBeenCalled();
});

it('copies the ordered quantity as the cross-unit allocation initial value without conversion', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{
    ...savedRow,
    allocationId: null,
    allocationStatus: 'unallocated',
    manualSupplierId: null,
    manualQty: null,
    orderedQty: 3,
    orderUom: 'piece',
    purchaseUom: 'kg',
  }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  const qty = row.querySelector<HTMLInputElement>('input[type="number"]')!;
  expect(qty.value).toBe('3');
  expect(qty.step).toBe('0.001');
  expect(row.textContent).toContain('異単位（換算なし）');

  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.clear(qty);
  await actor.type(qty, '3.75');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledWith([{
    orderItemId: 'item-1',
    supplierId: 1,
    allocatedQty: 3.75,
  }]));
});

it('resaves an unchanged allocation without overwrite confirmation', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm');
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([savedRow]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1));
  expect(confirmSpy).not.toHaveBeenCalled();
});

it('asks before overwriting changed allocation fields', async () => {
  const actor = userEvent.setup();
  const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([savedRow]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([
    { id: 1, label: '1: Supplier A' },
    { id: 2, label: '2: Supplier B' },
  ]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '2');
  const qty = row.querySelector<HTMLInputElement>('input[type="number"]')!;
  await actor.clear(qty);
  await actor.type(qty, '3');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1));
  expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('Supplier A → 2: Supplier B'));
  expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('数量: 2 → 3'));
});

it('offers a missing product mapping and creates it after allocation save when accepted', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings).mockResolvedValue([]);
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  const dialog = await screen.findByRole('dialog');
  expect(dialog.textContent).toContain('Product A → 1: Supplier A');
  expect(bulkSaveOrderItemAllocations).not.toHaveBeenCalled();
  await actor.click(screen.getByRole('button', { name: '追加して保存' }));

  await waitFor(() => expect(createSupplierProductMappingGlobal).toHaveBeenCalledWith({
    productId: 1,
    supplierId: 1,
    priority: 100,
    isPreferred: false,
    defaultUnitCost: null,
    leadTimeDays: null,
    note: null,
  }));
  expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1);
  expect(vi.mocked(bulkSaveOrderItemAllocations).mock.invocationCallOrder[0])
    .toBeLessThan(vi.mocked(createSupplierProductMappingGlobal).mock.invocationCallOrder[0]);
});

it('does not repeat the offer on the next save after mapping creation succeeds', async () => {
  const actor = userEvent.setup();
  let currentMappings: ReturnType<typeof mapping>[] = [];
  vi.mocked(listProductSupplierMappings).mockImplementation(async () => currentMappings);
  vi.mocked(createSupplierProductMappingGlobal).mockImplementation(async (payload) => {
    const created = mapping(payload.supplierId, payload.productId);
    currentMappings = [created];
    return created;
  });
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  let row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  await actor.click(await screen.findByRole('button', { name: '追加して保存' }));
  await waitFor(() => expect(createSupplierProductMappingGlobal).toHaveBeenCalledTimes(1));

  row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(createSupplierProductMappingGlobal).toHaveBeenCalledTimes(1);
});

it('saves the allocation without creating a mapping when declined', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings).mockResolvedValue([]);
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  await actor.click(await screen.findByRole('button', { name: '追加せず保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1));
  expect(createSupplierProductMappingGlobal).not.toHaveBeenCalled();
});

it('does not offer a mapping when the product already has any supplier mapping', async () => {
  const actor = userEvent.setup();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([
    { id: 1, label: '1: Supplier A' },
    { id: 2, label: '2: Supplier B' },
  ]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '2');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  await waitFor(() => expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(createSupplierProductMappingGlobal).not.toHaveBeenCalled();
});

it('deduplicates mapping creation for repeated rows with the same product and supplier', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings).mockResolvedValue([]);
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([
    { ...savedRow, orderItemId: 'item-1', orderNo: 'ORD-1', allocationStatus: 'unallocated', manualSupplierId: null },
    { ...savedRow, orderItemId: 'item-2', orderNo: 'ORD-2', allocationId: 12, allocationStatus: 'unallocated', manualSupplierId: null },
  ]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  vi.mocked(bulkSaveOrderItemAllocations).mockResolvedValue({ total: 2, succeeded: 2, failed: 0, errors: [] });
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const tableRows = (await screen.findAllByText(/ORD-[12]/)).map((cell) => cell.closest('tr')!);
  for (const row of tableRows) {
    await actor.selectOptions(row.querySelector('select')!, '1');
    await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  }
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  expect((await screen.findByRole('dialog')).querySelectorAll('li')).toHaveLength(1);
  await actor.click(screen.getByRole('button', { name: '追加して保存' }));

  await waitFor(() => expect(createSupplierProductMappingGlobal).toHaveBeenCalledTimes(1));
});

it('keeps supplier-required validation ahead of the mapping prompt', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings).mockResolvedValue([]);
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));

  expect(await screen.findByText('仕入先を選択してください')).toBeTruthy();
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(bulkSaveOrderItemAllocations).not.toHaveBeenCalled();
});

it('reports a mapping failure without hiding the successful allocation save', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings).mockResolvedValue([]);
  vi.mocked(createSupplierProductMappingGlobal).mockRejectedValue(
    new ServiceError('different conflict', { status: 409, code: 'OTHER_CONFLICT' }),
  );
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  await actor.click(await screen.findByRole('button', { name: '追加して保存' }));

  expect(await screen.findByText(/割当は保存されましたが、仕入先マッピングの登録に失敗しました/)).toBeTruthy();
  expect(bulkSaveOrderItemAllocations).toHaveBeenCalledTimes(1);
});

it('accepts a duplicate race only after verifying the exact mapping exists', async () => {
  const actor = userEvent.setup();
  vi.mocked(listProductSupplierMappings)
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([mapping(1, 1)])
    .mockResolvedValue([mapping(1, 1)]);
  vi.mocked(createSupplierProductMappingGlobal).mockRejectedValue(
    new ServiceError('already exists', { status: 409, code: 'SUPPLIER_PRODUCT_ALREADY_EXISTS' }),
  );
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([{ ...savedRow, allocationStatus: 'unallocated', manualSupplierId: null }]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([{ id: 1, label: '1: Supplier A' }]);
  render(<MemoryRouter><OrderItemBulkAllocationPage /></MemoryRouter>);

  const row = (await screen.findByText('ORD-1')).closest('tr')!;
  await actor.selectOptions(row.querySelector('select')!, '1');
  await actor.click(row.querySelector<HTMLInputElement>('input[type="checkbox"]')!);
  await actor.click(screen.getByRole('button', { name: '選択行を一括保存' }));
  await actor.click(await screen.findByRole('button', { name: '追加して保存' }));

  expect(await screen.findByText(/一括保存に成功しました/)).toBeTruthy();
  expect(screen.queryByText(/マッピングの登録に失敗/)).toBeNull();
});
