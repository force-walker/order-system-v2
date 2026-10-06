// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { InvoiceListPage } from './InvoiceListPage';
import { exportInvoiceHistory, listInvoiceHistory } from '../services/invoiceService';

vi.mock('../services/invoiceService', () => ({ listInvoiceHistory: vi.fn(), exportInvoiceHistory: vi.fn() }));
vi.mock('features/customers/services/customersService', () => ({ listCustomers: vi.fn().mockResolvedValue([]) }));
afterEach(cleanup);

it('loads finalized invoices by default and sends search/filter/sort/page to the backend', async () => {
  vi.mocked(listInvoiceHistory).mockResolvedValue({ items: [{ invoiceId: 'inv-1', invoiceNo: 'INV-1', customerId: 1,
    customerCode: 'C-1', customerName: '顧客A', issueDate: '2026-10-06', dueDate: '2026-10-31', invoiceStatus: 'finalized',
    paymentStatus: 'unpaid', overdue: true, lineCount: 2, subtotal: 100, tax: 10, total: 110 }], total: 1, page: 1, pageSize: 50 });
  render(<MemoryRouter><InvoiceListPage /></MemoryRouter>);
  expect(await screen.findByText('INV-1')).toBeTruthy();
  expect(screen.getByText('HK$100.00')).toBeTruthy();
  expect(screen.getByText('HK$10.00')).toBeTruthy();
  expect(screen.getByText('HK$110.00')).toBeTruthy();
  expect(vi.mocked(listInvoiceHistory).mock.calls[0][0].invoiceStatus).toBe('finalized');
  expect(screen.getByRole('link', { name: '詳細' }).getAttribute('href')).toBe('/invoices/inv-1?history=1');
  fireEvent.change(screen.getByLabelText('検索'), { target: { value: 'ABC' } });
  expect(await screen.findByText('INV-1')).toBeTruthy();
  await waitFor(() => { const calls = vi.mocked(listInvoiceHistory).mock.calls; expect(calls[calls.length - 1]?.[0].search).toBe('ABC'); });

  fireEvent.click(screen.getByRole('button', { name: 'Header CSV' }));
  fireEvent.click(screen.getByRole('button', { name: 'Line CSV' }));
  expect(exportInvoiceHistory).toHaveBeenCalledWith('headers', expect.objectContaining({ search: 'ABC' }));
  expect(exportInvoiceHistory).toHaveBeenCalledWith('lines', expect.objectContaining({ search: 'ABC' }));

  fireEvent.click(screen.getByRole('button', { name: 'Invoice No' }));
  await waitFor(() => { const calls = vi.mocked(listInvoiceHistory).mock.calls; expect(calls[calls.length - 1]?.[0]).toEqual(expect.objectContaining({ sort: 'invoice_no', direction: 'desc' })); });
});
