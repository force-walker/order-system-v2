// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { InvoiceListPage } from './InvoiceListPage';
import { listInvoiceSummaries } from '../services/invoiceService';

vi.mock('../services/invoiceService', () => ({
  listInvoiceSummaries: vi.fn(),
  generateInvoicePdf: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listInvoiceSummaries).mockResolvedValue([
    { invoiceId: 'inv-1', invoiceNo: 'INV-00000001', customerName: 'A', invoiceDate: '2026-09-29', deliveryDate: '2026-09-28', status: 'finalized', subtotal: 100, taxTotal: 0, grandTotal: 100, itemCount: 1 },
    { invoiceId: 'inv-2', invoiceNo: 'INV-00000002', customerName: 'B', invoiceDate: '2026-09-30', deliveryDate: '2026-09-29', status: 'finalized', subtotal: 200, taxTotal: 0, grandTotal: 200, itemCount: 2 },
  ]);
});

afterEach(cleanup);

const renderPage = () => render(<MemoryRouter><InvoiceListPage /></MemoryRouter>);

it('filters by invoice_date and clears back to all periods', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('INV-00000001');

  await actor.type(screen.getByLabelText('請求日'), '2026-09-30');
  expect(screen.queryByText('INV-00000001')).toBeNull();
  expect(screen.getByText('INV-00000002')).toBeTruthy();

  await actor.click(screen.getByRole('button', { name: '全期間' }));
  expect(screen.getByText('INV-00000001')).toBeTruthy();
});

it('selects only visible invoices, supports indeterminate state, and clears hidden selections on filter change', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('INV-00000001');
  const header = screen.getByRole('checkbox', { name: '表示中の請求書を全選択' }) as HTMLInputElement;
  const first = screen.getByRole('checkbox', { name: '請求書 INV-00000001 を選択' }) as HTMLInputElement;

  await actor.click(first);
  expect(header.indeterminate).toBe(true);
  await actor.click(header);
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000001 を選択' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000002 を選択' }) as HTMLInputElement).checked).toBe(true);

  await actor.type(screen.getByLabelText('請求日'), '2026-09-30');
  expect(screen.queryByRole('checkbox', { name: '請求書 INV-00000001 を選択' })).toBeNull();
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000002 を選択' }) as HTMLInputElement).checked).toBe(true);
  await actor.click(screen.getByRole('button', { name: '全期間' }));
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000001 を選択' }) as HTMLInputElement).checked).toBe(false);
  expect(header.indeterminate).toBe(true);
  await actor.click(header);
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000001 を選択' }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByRole('checkbox', { name: '請求書 INV-00000002 を選択' }) as HTMLInputElement).checked).toBe(true);
});
