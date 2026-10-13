// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShippingReportPage } from './ShippingReportPage';
import { InvoiceDraftPage } from './InvoiceDraftPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import { getShippingReport } from '../services/shippingReportService';
import { listInvoiceDraftCandidates, listInvoiceDraftListRows } from '../services/invoiceService';
import { listCustomers } from '../services/ordersService';
import { MemoryRouter } from 'react-router-dom';
import { presetRange } from 'shared/workflowDateRange';

vi.mock('../services/shippingReportService', () => ({ getShippingReport: vi.fn(), generatePurchaseConfirmationPdf: vi.fn() }));
vi.mock('../services/invoiceService', () => ({
  listInvoiceDraftListRows: vi.fn(),
  listInvoiceDraftCandidates: vi.fn(),
  finalizeInvoiceDraftsBatch: vi.fn(),
  updateInvoiceDraftItem: vi.fn(),
}));
vi.mock('../services/ordersService', () => ({ listCustomers: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getShippingReport).mockResolvedValue([]);
  vi.mocked(listInvoiceDraftListRows).mockResolvedValue([]);
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([]);
  vi.mocked(listCustomers).mockResolvedValue([]);
});

afterEach(cleanup);

it('uses the shared delivery-date default and supplier-product mode on the shipping report page', async () => {
  render(<ShippingReportPage />);
  expect((screen.getByLabelText(/納品日/) as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
  expect((screen.getByLabelText('表示モード') as HTMLSelectElement).value).toBe('supplier_product');
  await waitFor(() => expect(getShippingReport).toHaveBeenCalledWith(getDefaultDeliveryDate(), 'supplier_product'));

  await userEvent.selectOptions(screen.getByLabelText('表示モード'), 'customer');
  await waitFor(() => expect(getShippingReport).toHaveBeenLastCalledWith(getDefaultDeliveryDate(), 'customer'));
});

it('uses the shared delivery-week defaults for invoice candidates and drafts', async () => {
  render(<MemoryRouter><InvoiceDraftPage /></MemoryRouter>);
  await waitFor(() => expect(listInvoiceDraftListRows).toHaveBeenCalled());
  const range = presetRange('week');
  expect((screen.getByLabelText('候補納品日 開始日') as HTMLInputElement).value).toBe(range.from);
  expect((screen.getByLabelText('候補納品日 終了日') as HTMLInputElement).value).toBe(range.to);
  expect((screen.getByLabelText('ドラフト請求日 開始日') as HTMLInputElement).value).toBe(range.from);
  expect((screen.getByLabelText('ドラフト請求日 終了日') as HTMLInputElement).value).toBe(range.to);
});
