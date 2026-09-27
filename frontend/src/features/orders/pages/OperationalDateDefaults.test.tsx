// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { ShippingReportPage } from './ShippingReportPage';
import { InvoiceDraftPage } from './InvoiceDraftPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import { getShippingReport } from '../services/shippingReportService';
import { listInvoiceDraftListRows } from '../services/invoiceService';

vi.mock('../services/shippingReportService', () => ({ getShippingReport: vi.fn(), generatePurchaseConfirmationPdf: vi.fn() }));
vi.mock('../services/invoiceService', () => ({
  listInvoiceDraftListRows: vi.fn(),
  finalizeInvoiceDraftsBatch: vi.fn(),
  updateInvoiceDraftItem: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getShippingReport).mockResolvedValue([]);
  vi.mocked(listInvoiceDraftListRows).mockResolvedValue([]);
});

afterEach(cleanup);

it('uses the shared delivery-date default on the shipping report page', () => {
  render(<ShippingReportPage />);
  expect((screen.getByLabelText(/出荷日/) as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
});

it('uses the shared delivery-date default for the invoice draft delivery-date filter', async () => {
  render(<InvoiceDraftPage />);
  await waitFor(() => expect(listInvoiceDraftListRows).toHaveBeenCalled());
  expect((screen.getByLabelText('納品日') as HTMLInputElement).value).toBe(getDefaultDeliveryDate());
});
