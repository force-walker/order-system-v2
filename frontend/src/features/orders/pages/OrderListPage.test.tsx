// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { OrderListPage } from './OrderListPage';
import { confirmOrder, listOrders } from '../services/ordersService';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';

vi.mock('../services/ordersService', () => ({
  listOrders: vi.fn(), confirmOrder: vi.fn(), bulkCancelOrders: vi.fn(),
  clearDirtyOrderStatus: vi.fn(), hasDirtyOrderStatus: () => false,
}));
beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  const deliveryDate = getDefaultDeliveryDate();
  vi.mocked(listOrders).mockResolvedValue([
    { id: 'order-uuid', orderNo: 'ORD-new', customerName: 'Test', deliveryDate, status: 'new', items: [] },
    { id: 'confirmed-uuid', orderNo: 'ORD-confirmed', customerName: 'Test', deliveryDate, status: 'confirmed', items: [] },
  ] as unknown as Awaited<ReturnType<typeof listOrders>>);
  vi.mocked(confirmOrder).mockResolvedValue();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('defaults to new and confirmed status plus the shared delivery date', async () => {
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByText('ORD-new');
  expect((screen.getByRole('checkbox', { name: '新規' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '確定' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '引当済' }) as HTMLInputElement).checked).toBe(false);
  expect((screen.getByLabelText('納品日') as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
});

it('only confirms selected new orders and refreshes the list', async () => {
  const actor = userEvent.setup();
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  const button = await screen.findByRole('button', { name: /選択した新規注文を確定/ });
  expect((button as HTMLButtonElement).disabled).toBe(true);
  const table = screen.getByRole('table');
  await actor.click(table.querySelector('thead input')!);
  await actor.click(button);
  await screen.findByText('1件の注文を確定しました。');
  expect(confirmOrder).toHaveBeenCalledTimes(1);
  expect(confirmOrder).toHaveBeenCalledWith('order-uuid');
  await waitFor(() => expect(listOrders).toHaveBeenCalledTimes(2));
});

it('does not submit when confirmation is dismissed', async () => {
  const actor = userEvent.setup();
  vi.mocked(window.confirm).mockReturnValue(false);
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByRole('table');
  await actor.click(screen.getByRole('table').querySelector('thead input')!);
  await actor.click(screen.getByRole('button', { name: /選択した新規注文を確定/ }));
  expect(confirmOrder).not.toHaveBeenCalled();
});

it('shows a conflict and reloads without reporting success', async () => {
  const actor = userEvent.setup();
  vi.mocked(confirmOrder).mockRejectedValue(new Error('state changed'));
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByRole('table');
  await actor.click(screen.getByRole('table').querySelector('thead input')!);
  await actor.click(screen.getByRole('button', { name: /選択した新規注文を確定/ }));
  await screen.findByText(/確定成功 0件 \/ 失敗 1件/);
  expect(listOrders).toHaveBeenCalledTimes(2);
});
