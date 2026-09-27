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

vi.mock('../services/orderItemAllocationsService', () => ({
  listOrderItemAllocationWorkItems: vi.fn(),
  listSupplierFilterOptions: vi.fn(),
  bulkSaveOrderItemAllocations: vi.fn(),
  generateOrderItemLabelsPdf: vi.fn(),
  suggestOrderItemAllocations: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listOrderItemAllocationWorkItems).mockResolvedValue([]);
  vi.mocked(listSupplierFilterOptions).mockResolvedValue([]);
  vi.mocked(bulkSaveOrderItemAllocations).mockResolvedValue({ total: 1, succeeded: 1, failed: 0, errors: [] });
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
  expect((screen.getByRole('checkbox', { name: '新規' }) as HTMLInputElement).checked).toBe(false);
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
  orderedQty: 2,
  deliveryDate: getDefaultDeliveryDate(),
  shippedDate: null,
  allocationStatus: 'allocated' as const,
  proposedSupplierId: 1,
  proposedQty: 2,
  manualSupplierId: 1,
  manualQty: 2,
};

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
