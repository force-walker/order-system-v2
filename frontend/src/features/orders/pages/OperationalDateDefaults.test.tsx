// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShippingReportPage } from './ShippingReportPage';
import { InvoiceDraftPage } from './InvoiceDraftPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import { getShippingReport } from '../services/shippingReportService';
import { listInvoiceDraftListRows } from '../services/invoiceService';
import { listCustomers } from '../services/ordersService';

vi.mock('../services/shippingReportService', () => ({ getShippingReport: vi.fn(), generatePurchaseConfirmationPdf: vi.fn() }));
vi.mock('../services/invoiceService', () => ({
  listInvoiceDraftListRows: vi.fn(),
  finalizeInvoiceDraftsBatch: vi.fn(),
  updateInvoiceDraftItem: vi.fn(),
}));
vi.mock('../services/ordersService', () => ({ listCustomers: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getShippingReport).mockResolvedValue([]);
  vi.mocked(listInvoiceDraftListRows).mockResolvedValue([]);
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

it('uses the shared delivery-date default for the invoice draft delivery-date filter', async () => {
  render(<InvoiceDraftPage />);
  await waitFor(() => expect(listInvoiceDraftListRows).toHaveBeenCalled());
  expect((screen.getByLabelText('納品日') as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
});
