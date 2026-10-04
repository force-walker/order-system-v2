// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProductListPage } from './ProductListPage';
import { listProducts } from '../services/productsService';

vi.mock('../services/productsService', () => ({ listProducts: vi.fn(), archiveProduct: vi.fn(), unarchiveProduct: vi.fn(), deleteProduct: vi.fn() }));
beforeEach(() => vi.mocked(listProducts).mockResolvedValue([
  { id: 2, label: 'Banana', sku: 'SKU-2', active: true, name: 'Banana', orderUom: 'PC', pricingBasisDefault: 'uom_count' },
  { id: 1, label: 'Apple', sku: 'SKU-1', active: true, name: 'Apple', orderUom: 'CTN', pricingBasisDefault: 'uom_count' },
]));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('selects visible rows, drops hidden selections, sorts columns, and carries list context', async () => {
  const actor = userEvent.setup();
  render(<MemoryRouter><ProductListPage /></MemoryRouter>);
  await screen.findByText('Banana');
  const selectAll = screen.getByRole('checkbox', { name: '表示中の商品をすべて選択' });
  await actor.click(screen.getByRole('checkbox', { name: 'Appleを選択' }));
  expect((selectAll as HTMLInputElement).indeterminate).toBe(true);
  await actor.click(selectAll);
  expect((screen.getByRole('checkbox', { name: 'Appleを選択' }) as HTMLInputElement).checked).toBe(true);
  await actor.click(selectAll);
  expect((screen.getByRole('checkbox', { name: 'Appleを選択' }) as HTMLInputElement).checked).toBe(false);
  await actor.click(selectAll);
  await actor.type(screen.getByPlaceholderText('商品名 / SKU'), 'Banana');
  expect(screen.queryByText('Apple')).toBeNull();
  await actor.click(screen.getByRole('button', { name: '商品名' }));
  const row = screen.getByText('Banana').closest('tr')!;
  expect(within(row).getByRole('link', { name: '詳細' }).getAttribute('href')).toContain('ids=2');
  expect(screen.queryByRole('checkbox', { name: 'Appleを選択' })).toBeNull();
  expect((screen.getByRole('checkbox', { name: 'Bananaを選択' }) as HTMLInputElement).checked).toBe(true);
});
