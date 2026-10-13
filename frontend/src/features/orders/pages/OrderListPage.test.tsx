// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { OrderListPage } from './OrderListPage';
import { confirmOrder, listOrders } from '../services/ordersService';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import { presetRange } from 'shared/workflowDateRange';

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

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};

it('defaults to new and confirmed status plus the shared delivery week', async () => {
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByText('ORD-new');
  expect((screen.getByRole('checkbox', { name: '新規' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '確定' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '引当済' }) as HTMLInputElement).checked).toBe(false);
  const range = presetRange('week');
  expect((screen.getByLabelText('納品日 開始日') as HTMLInputElement).value).toBe(range.from);
  expect((screen.getByLabelText('納品日 終了日') as HTMLInputElement).value).toBe(range.to);
  expect(listOrders).toHaveBeenCalledWith(false, { dateFrom: range.from, dateTo: range.to });
});

it('hides stale rows and blocks writes while the date range is invalid, then reloads when valid', async () => {
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  expect(await screen.findByText('ORD-new')).toBeTruthy();
  const callCount = vi.mocked(listOrders).mock.calls.length;

  fireEvent.change(screen.getByLabelText('納品日 開始日'), { target: { value: '2099-10-20' } });
  expect((await screen.findByRole('alert')).textContent).toContain('開始日は終了日以前にしてください');
  expect(screen.queryByText('ORD-new')).toBeNull();
  expect((screen.getByRole('button', { name: /選択した新規注文を確定/ }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '選択注文を一括Cancel' }) as HTMLButtonElement).disabled).toBe(true);
  expect(listOrders).toHaveBeenCalledTimes(callCount);

  fireEvent.change(screen.getByLabelText('納品日 終了日'), { target: { value: '2099-10-31' } });
  await waitFor(() => expect(listOrders).toHaveBeenCalledTimes(callCount + 1));
  expect(await screen.findByText('ORD-new')).toBeTruthy();
});

it('keeps the newest date-range response when an older request finishes last', async () => {
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByText('ORD-new');
  const requestA = deferred<Awaited<ReturnType<typeof listOrders>>>();
  const requestB = deferred<Awaited<ReturnType<typeof listOrders>>>();
  vi.mocked(listOrders).mockImplementationOnce(() => requestA.promise).mockImplementationOnce(() => requestB.promise);

  fireEvent.change(screen.getByLabelText('納品日 開始日'), { target: { value: '2026-10-13' } });
  fireEvent.change(screen.getByLabelText('納品日 開始日'), { target: { value: '2026-10-14' } });
  requestB.resolve([{ id: 'order-b', orderNo: 'ORD-B', customerName: 'B', deliveryDate: '2026-10-14', status: 'new', items: [] }] as Awaited<ReturnType<typeof listOrders>>);
  expect(await screen.findByText('ORD-B')).toBeTruthy();

  requestA.resolve([{ id: 'order-a', orderNo: 'ORD-A', customerName: 'A', deliveryDate: '2026-10-13', status: 'new', items: [] }] as Awaited<ReturnType<typeof listOrders>>);
  await waitFor(() => expect(screen.queryByText('ORD-A')).toBeNull());
  expect(screen.getByText('ORD-B')).toBeTruthy();
});

it('invalidates an in-flight request when the range becomes invalid', async () => {
  render(<MemoryRouter><OrderListPage /></MemoryRouter>);
  await screen.findByText('ORD-new');
  const requestA = deferred<Awaited<ReturnType<typeof listOrders>>>();
  vi.mocked(listOrders).mockImplementationOnce(() => requestA.promise);

  fireEvent.change(screen.getByLabelText('納品日 開始日'), { target: { value: '2026-10-13' } });
  fireEvent.change(screen.getByLabelText('納品日 開始日'), { target: { value: '2099-10-20' } });
  requestA.resolve([{ id: 'order-a', orderNo: 'ORD-A', customerName: 'A', deliveryDate: '2026-10-13', status: 'new', items: [] }] as Awaited<ReturnType<typeof listOrders>>);
  expect(await screen.findByText('有効な日付範囲を入力してください')).toBeTruthy();
  expect(screen.queryByText('ORD-A')).toBeNull();

  vi.mocked(listOrders).mockResolvedValueOnce([{ id: 'order-b', orderNo: 'ORD-B', customerName: 'B', deliveryDate: '2099-10-21', status: 'new', items: [] }] as Awaited<ReturnType<typeof listOrders>>);
  fireEvent.change(screen.getByLabelText('納品日 終了日'), { target: { value: '2099-10-31' } });
  expect(await screen.findByText('ORD-B')).toBeTruthy();
  expect(screen.queryByText('ORD-A')).toBeNull();
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
