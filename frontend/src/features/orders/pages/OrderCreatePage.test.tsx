// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { OrderCreatePage } from './OrderCreatePage';
import { createOrder, listCustomers, listProducts } from '../services/ordersService';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';

vi.mock('../services/ordersService', () => ({
  createOrder: vi.fn(),
  listCustomers: vi.fn(),
  listProducts: vi.fn(),
}));

const Location = () => <output data-testid="location">{useLocation().pathname}</output>;

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listCustomers).mockResolvedValue([{ id: 1, label: '1: Customer A' }]);
  vi.mocked(listProducts).mockResolvedValue([{
    id: 10,
    label: '10: Product A',
    name: 'Product A',
    orderUom: 'CTN',
    pricingBasisDefault: 'uom_count',
  }]);
  vi.mocked(createOrder).mockResolvedValue({
    id: 'order-9',
    orderNo: 'ORD-00000009',
    customerId: 1,
    customerName: 'Customer A',
    deliveryDate: getDefaultDeliveryDate(),
    status: 'new',
    items: [],
    createdAt: '2026-09-30T00:00:00Z',
  });
});

afterEach(cleanup);

it('stays on create, clears entered values, restores defaults, and shows the created order number', async () => {
  const actor = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/orders/new']}>
      <Location />
      <Routes><Route path="/orders/new" element={<OrderCreatePage />} /></Routes>
    </MemoryRouter>,
  );

  const customer = await screen.findByLabelText('顧客選択 *');
  await actor.type(customer, 'Customer A');
  await actor.type(screen.getByPlaceholderText('商品名で検索'), 'Product A');
  await actor.type(screen.getByRole('spinbutton'), '2');
  await actor.type(screen.getByLabelText('備考'), 'next order must start clean');
  await actor.click(screen.getByRole('button', { name: '注文を作成' }));

  await waitFor(() => expect(createOrder).toHaveBeenCalledTimes(1));
  expect(screen.getByTestId('location').textContent).toBe('/orders/new');
  expect(await screen.findByText('ORD-00000009 を作成しました。')).toBeTruthy();
  expect((screen.getByLabelText('顧客選択 *') as HTMLInputElement).value).toBe('');
  expect((screen.getByPlaceholderText('商品名で検索') as HTMLInputElement).value).toBe('');
  expect((screen.getByRole('spinbutton') as HTMLInputElement).value).toBe('');
  expect((screen.getByLabelText('備考') as HTMLTextAreaElement).value).toBe('');
  expect((document.querySelectorAll<HTMLInputElement>('input[type="date"]')[0]).value).toBe(getDefaultDeliveryDate());
});
