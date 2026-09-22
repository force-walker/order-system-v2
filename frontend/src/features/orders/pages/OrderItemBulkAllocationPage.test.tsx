// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OrderItemBulkAllocationPage } from './OrderItemBulkAllocationPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import {
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
});

afterEach(cleanup);

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
