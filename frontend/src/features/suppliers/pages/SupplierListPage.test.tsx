// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SupplierListPage } from './SupplierListPage';
import { listSuppliers } from '../services/suppliersService';

vi.mock('../services/suppliersService', () => ({ listSuppliers: vi.fn(), archiveSupplier: vi.fn(), unarchiveSupplier: vi.fn(), deleteSupplier: vi.fn() }));
beforeEach(() => vi.mocked(listSuppliers).mockResolvedValue({ items: [
  { id: 2, supplierCode: 'S-2', name: 'Zulu Supplier', active: true, createdAt: '2026-01-02', updatedAt: '2026-01-02' },
  { id: 1, supplierCode: 'S-1', name: 'Alpha Supplier', active: true, createdAt: '2026-01-01', updatedAt: '2026-01-01' },
], hasNext: false }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('selects the current filtered page and sorts a normal data column', async () => {
  const actor = userEvent.setup();
  render(<MemoryRouter><SupplierListPage /></MemoryRouter>);
  await screen.findByText('Zulu Supplier');
  await actor.click(screen.getByRole('checkbox', { name: '表示中の仕入先をすべて選択' }));
  expect((screen.getByRole('checkbox', { name: 'Alpha Supplierを選択' }) as HTMLInputElement).checked).toBe(true);
  await actor.click(screen.getByRole('button', { name: 'name' }));
  expect(screen.getAllByRole('row')[1].textContent).toContain('Alpha Supplier');
  const detail = screen.getAllByRole('link', { name: '詳細' })[0];
  expect(detail.getAttribute('href')).toContain('ids=1%2C2');
});
