// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OrderForm } from './OrderForm';

afterEach(cleanup);

const products = [
  { id: 1, label: '1: Carton Product', name: 'Carton Product', orderUom: 'CTN', pricingBasisDefault: 'uom_count' as const },
  { id: 2, label: '2: Piece Product', name: 'Piece Product', orderUom: 'PC', pricingBasisDefault: 'uom_count' as const },
];

it('reflects Product.order_uom when the SKU changes and keeps the UOM read-only', async () => {
  const actor = userEvent.setup();
  render(<OrderForm onSubmit={vi.fn()} customers={[]} products={products} />);

  const product = screen.getByPlaceholderText('商品名で検索');
  const uom = screen.getByRole('textbox', { name: '明細 1 受注単位' }) as HTMLInputElement;
  expect(uom.value).toBe('');
  expect(uom.readOnly).toBe(true);

  await actor.type(product, 'Carton Product');
  expect(uom.value).toBe('CTN');

  await actor.clear(product);
  await actor.type(product, 'Piece Product');
  expect(uom.value).toBe('PC');

  await actor.type(uom, 'KG');
  expect(uom.value).toBe('PC');
});
