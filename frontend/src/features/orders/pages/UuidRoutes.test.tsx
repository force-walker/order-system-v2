// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { OrderEditPage } from './OrderEditPage';
import { OrderItemDetailPage } from './OrderItemDetailPage';
import { InvoiceDetailPage } from './InvoiceDetailPage';
import { InvoiceDraftDetailPage } from './InvoiceDraftDetailPage';
import * as orders from '../services/ordersService';
import * as invoices from '../services/invoiceService';
import { ShippingReportPage } from './ShippingReportPage';
import * as shipping from '../services/shippingReportService';

vi.mock('../services/shippingReportService', () => ({ getShippingReport: vi.fn(), generatePurchaseConfirmationPdf: vi.fn() }));

vi.mock('../services/ordersService', () => ({
  getOrder: vi.fn(), getOrderItem: vi.fn(), updateOrder: vi.fn(),
  listCustomers: vi.fn(), listProducts: vi.fn(),
  clearDirtyOrderStatus: vi.fn(), hasDirtyOrderStatus: () => false,
}));
vi.mock('../services/invoiceService', () => ({
  getInvoiceDetailView: vi.fn(), listInvoiceSummaries: vi.fn(), generateInvoicePdf: vi.fn(),
  getInvoiceDraftItems: vi.fn(), finalizeInvoiceDraft: vi.fn(), finalizeInvoiceItemLine: vi.fn(),
}));
vi.mock('../components/OrderForm', () => ({
  OrderForm: ({ onSubmit, initialValue }: any) => <button onClick={() => onSubmit(initialValue)}>保存テスト</button>,
}));
const id = '30ae4186-04b9-4a13-985b-79edf1d061bc';
const itemId = '57048d30-023a-4886-a623-3ef334c8d51c';
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(orders.listCustomers).mockResolvedValue([]);
  vi.mocked(orders.listProducts).mockResolvedValue([]);
  vi.mocked(orders.getOrder).mockResolvedValue({ id, orderNo: 'TEST', customerId: 1, customerName: 'Test', deliveryDate: '2026-09-20', status: 'new', createdAt: '', items: [{ id: itemId, productName: 'Test', quantity: 2, unit: 'kg' }] });
  vi.mocked(orders.updateOrder).mockResolvedValue({ id } as any);
  vi.mocked(orders.getOrderItem).mockResolvedValue(null);
  vi.mocked(invoices.getInvoiceDraftItems).mockResolvedValue([]);
  vi.mocked(invoices.listInvoiceSummaries).mockResolvedValue([]);
  vi.mocked(invoices.getInvoiceDetailView).mockResolvedValue({ invoiceId: id, invoiceNo: 'INV', customerName: 'Test', invoiceDate: '', deliveryDate: '', status: 'draft', subtotal: 0, taxTotal: 0, grandTotal: 0, items: [] });
});
afterEach(cleanup);
const show = (path: string, url: string, page: React.ReactElement) => render(
  <MemoryRouter initialEntries={[url]}><Routes><Route path={path} element={page} /><Route path="*" element={<div>戻り先</div>} /></Routes></MemoryRouter>,
);
it('loads and saves an order without losing its UUID or item UUID', async () => {
  show('/orders/:orderId/edit', `/orders/${id}/edit`, <OrderEditPage />);
  await userEvent.click(await screen.findByText('保存テスト'));
  expect(orders.getOrder).toHaveBeenCalledWith(id);
  await waitFor(() => expect(orders.updateOrder).toHaveBeenCalledWith(id, expect.objectContaining({ items: [expect.objectContaining({ id: itemId })] })));
});
it('loads order item details with both UUIDs', async () => {
  show('/orders/:orderId/items/:itemId', `/orders/${id}/items/${itemId}`, <OrderItemDetailPage />);
  await waitFor(() => expect(orders.getOrderItem).toHaveBeenCalledWith(id, itemId));
});
it('loads invoice details using the route UUID', async () => {
  show('/invoices/:invoiceId', `/invoices/${id}`, <InvoiceDetailPage />);
  await waitFor(() => expect(invoices.getInvoiceDetailView).toHaveBeenCalledWith(id));
});
it('loads and finalizes an invoice draft using its UUID', async () => {
  show('/invoices/drafts/:invoiceId', `/invoices/drafts/${id}`, <InvoiceDraftDetailPage />);
  await userEvent.click(await screen.findByRole('button', { name: '請求書発行' }));
  expect(invoices.getInvoiceDraftItems).toHaveBeenCalledWith(id);
  expect(invoices.finalizeInvoiceDraft).toHaveBeenCalledWith(id);
});
it('keeps the selected UUID when generating a shipping PDF', async () => {
  vi.mocked(shipping.getShippingReport).mockResolvedValue([{ orderItemId: itemId, shippedDate: '2026-09-20', supplierName: 'Test', customerName: 'Test', productName: 'Test', quantity: 2, unit: 'kg' }]);
  // Stop before opening a window; this test verifies the selected ID passed to the service.
  vi.mocked(shipping.generatePurchaseConfirmationPdf).mockRejectedValue(new Error('test PDF stop'));
  render(<ShippingReportPage />);
  fireEvent.change(screen.getByLabelText(/出荷日/), { target: { value: '2026-09-20' } });
  await userEvent.selectOptions(screen.getByLabelText('表示モード'), 'customer');
  await screen.findByRole('table');
  await userEvent.click(screen.getAllByRole('checkbox')[0]);
  await userEvent.click(screen.getByRole('button', { name: 'PDF作成' }));
  expect(shipping.generatePurchaseConfirmationPdf).toHaveBeenCalledWith([itemId]);
});
