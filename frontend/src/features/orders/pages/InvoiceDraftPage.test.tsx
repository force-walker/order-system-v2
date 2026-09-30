// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { InvoiceDraftPage } from './InvoiceDraftPage';
import { getDefaultDeliveryDate } from '../utils/deliveryDate';
import { finalizeInvoiceDraftsBatch, listInvoiceDraftCandidates, listInvoiceDraftListRows, updateInvoiceDraftItem } from '../services/invoiceService';
import { generateDraftInvoiceFromPurchase } from '../services/purchaseService';
import { listCustomers } from '../services/ordersService';
import type { InvoiceDraftListRow } from '../types/order';

vi.mock('../services/invoiceService', () => ({
  finalizeInvoiceDraftsBatch: vi.fn(),
  listInvoiceDraftCandidates: vi.fn(),
  listInvoiceDraftListRows: vi.fn(),
  updateInvoiceDraftItem: vi.fn(),
}));
vi.mock('../services/purchaseService', () => ({ generateDraftInvoiceFromPurchase: vi.fn() }));
vi.mock('../services/ordersService', () => ({ listCustomers: vi.fn() }));

const defaultDate = getDefaultDeliveryDate();
const otherDate = new Date(`${defaultDate}T00:00:00Z`);
otherDate.setUTCDate(otherDate.getUTCDate() + 1);
const nextDate = otherDate.toISOString().slice(0, 10);

const row = (
  invoiceId: string,
  customerName: string,
  deliveryDate = defaultDate,
): InvoiceDraftListRow => ({
  invoiceId,
  invoiceItemId: `${invoiceId}-item`,
  invoiceNo: `IVD-${invoiceId}`,
  lineNo: 10,
  lineRef: `IVL-${invoiceId}-0010`,
  invoiceDate: defaultDate,
  deliveryDate,
  status: 'draft',
  orderNo: `ORD-${invoiceId}`,
  customerName,
  productName: `Product ${invoiceId}`,
  billableQty: 1,
  billableUom: 'PC',
  salesUnitPrice: 100,
  unitCostBasis: 80,
  lineAmount: 100,
  grossMarginPct: 20,
});

const rows = [
  row('abc-trading', 'ABC Trading'),
  row('abc-foods', 'ABC Foods'),
  row('other', 'Other Corp'),
  row('abc-trading-later', 'ABC Trading', nextDate),
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listInvoiceDraftListRows).mockResolvedValue(rows);
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([]);
  vi.mocked(listCustomers).mockResolvedValue([
    { id: 1, label: '1: ABC Trading (CUST-ABC)', customerCode: 'CUST-ABC' },
    { id: 2, label: '2: ABC Foods (CUST-FOODS)', customerCode: 'CUST-FOODS' },
    { id: 3, label: '3: Other Corp (CUST-OTHER)', customerCode: 'CUST-OTHER' },
  ]);
  vi.mocked(finalizeInvoiceDraftsBatch).mockResolvedValue({ success_count: 1, failure_count: 0, results: [] });
});

it('shows a purchased order without a Delivery as an invoice candidate and creates its draft', async () => {
  const actor = userEvent.setup();
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([{
    orderId: 'order-purchased',
    orderNo: 'ORD-PURCHASED',
    orderStatus: 'purchased',
    customerId: 1,
    customerName: 'ABC Trading',
    deliveryDate: defaultDate,
    itemCount: 2,
    purchaseResultIds: [101, 102],
  }]);
  vi.mocked(generateDraftInvoiceFromPurchase).mockResolvedValue('invoice-new');
  vi.mocked(listInvoiceDraftCandidates)
    .mockResolvedValueOnce([{
      orderId: 'order-purchased',
      orderNo: 'ORD-PURCHASED',
      orderStatus: 'purchased',
      customerId: 1,
      customerName: 'ABC Trading',
      deliveryDate: defaultDate,
      itemCount: 2,
      purchaseResultIds: [101, 102],
    }])
    .mockResolvedValueOnce([]);
  vi.mocked(listInvoiceDraftListRows)
    .mockResolvedValueOnce(rows)
    .mockResolvedValueOnce([...rows, row('new', 'ABC Trading')]);
  renderPage();

  expect(await screen.findByText('ORD-PURCHASED')).toBeTruthy();
  expect(screen.queryByRole('heading', { name: '請求候補' })).toBeNull();
  await actor.click(screen.getByRole('button', { name: 'ドラフト作成' }));

  await waitFor(() => expect(generateDraftInvoiceFromPurchase).toHaveBeenCalledWith({
    orderId: 'order-purchased',
    invoiceDate: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    purchaseResultIds: [101, 102],
  }));
  expect(await screen.findByText('IVD-new')).toBeTruthy();
  expect(screen.queryByText('ORD-PURCHASED')).toBeNull();
});

it('shows the backend UOM validation reason when candidate draft creation fails', async () => {
  const actor = userEvent.setup();
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([{
    orderId: 'order-sku-9',
    orderNo: 'ORD-SKU-9',
    orderStatus: 'purchased',
    customerId: 1,
    customerName: 'ABC Trading',
    deliveryDate: defaultDate,
    itemCount: 1,
    purchaseResultIds: [109],
  }]);
  vi.mocked(generateDraftInvoiceFromPurchase).mockRejectedValue(new Error('INVOICE_UOM_UNSUPPORTED: catch-weight item must use KG invoice_uom'));
  renderPage();
  await screen.findByText('ORD-SKU-9');
  await actor.click(screen.getByRole('button', { name: 'ドラフト作成' }));

  expect(await screen.findByText(/INVOICE_UOM_UNSUPPORTED/)).toBeTruthy();
});

afterEach(cleanup);

const renderPage = () => render(<MemoryRouter><InvoiceDraftPage /></MemoryRouter>);

it('starts with all customers and does not apply a customer filter', async () => {
  renderPage();

  expect(await screen.findByText('IVD-abc-trading')).toBeTruthy();
  expect((screen.getByLabelText('取引先') as HTMLInputElement).value).toBe('全取引先');
  expect(screen.getByText('IVD-abc-foods')).toBeTruthy();
  expect(screen.getByText('IVD-other')).toBeTruthy();
  expect(listInvoiceDraftListRows).toHaveBeenCalledWith();
  expect(listCustomers).toHaveBeenCalledWith(true);
});

it('searches customer names by case-insensitive partial match', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('IVD-abc-trading');

  const filter = screen.getByLabelText('取引先');
  await actor.clear(filter);
  await actor.type(filter, 'abc');

  expect(screen.getByText('IVD-abc-trading')).toBeTruthy();
  expect(screen.getByText('IVD-abc-foods')).toBeTruthy();
  expect(screen.queryByText('IVD-other')).toBeNull();
});

it('selects a customer by customer code and filters to that customer', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('IVD-abc-trading');

  const filter = screen.getByLabelText('取引先');
  await actor.clear(filter);
  await actor.type(filter, 'CUST-FOODS');

  expect((filter as HTMLInputElement).value).toBe('ABC Foods (CUST-FOODS)');
  expect(screen.getByText('IVD-abc-foods')).toBeTruthy();
  expect(screen.queryByText('IVD-abc-trading')).toBeNull();
});

it('returns to all customers after a customer has been selected', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('IVD-abc-trading');
  const filter = screen.getByLabelText('取引先');
  await actor.clear(filter);
  await actor.type(filter, 'CUST-FOODS');
  expect(screen.queryByText('IVD-other')).toBeNull();

  await actor.click(screen.getByRole('button', { name: '全取引先' }));

  expect((filter as HTMLInputElement).value).toBe('全取引先');
  expect(screen.getByText('IVD-other')).toBeTruthy();
});

it('combines the customer and delivery-date filters with AND semantics', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('IVD-abc-trading');
  const filter = screen.getByLabelText('取引先');
  await actor.clear(filter);
  await actor.type(filter, 'CUST-ABC');
  fireEvent.change(screen.getByLabelText('納品日'), { target: { value: nextDate } });

  expect(screen.getByText('IVD-abc-trading-later')).toBeTruthy();
  expect(screen.queryByText('IVD-abc-trading')).toBeNull();
  expect(screen.queryByText('IVD-abc-foods')).toBeNull();
});

it('keeps the existing invoice draft finalization flow working', async () => {
  const actor = userEvent.setup();
  renderPage();
  await screen.findByText('IVD-abc-trading');

  await actor.click(screen.getByRole('checkbox', { name: '請求書 IVD-abc-trading を選択' }));
  await actor.click(screen.getByRole('button', { name: '選択した請求ドラフトを発行 (1)' }));

  await waitFor(() => expect(finalizeInvoiceDraftsBatch).toHaveBeenCalledWith(['abc-trading']));
  expect(updateInvoiceDraftItem).not.toHaveBeenCalled();
});
