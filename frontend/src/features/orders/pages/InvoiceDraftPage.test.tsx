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
import type { InvoiceDraftCandidate, InvoiceDraftListRow } from '../types/order';

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

const candidate = (orderId: string, itemIds = ['item-1']): InvoiceDraftCandidate => ({
  orderId,
  orderNo: `ORD-${orderId}`,
  orderStatus: 'purchased',
  customerId: 1,
  customerName: 'ABC Trading',
  deliveryDate: defaultDate,
  itemCount: itemIds.length,
  purchaseResultIds: itemIds.map((_, index) => 101 + index),
  items: itemIds.map((itemId, index) => ({
    orderItemId: itemId,
    productSku: `SKU-${index + 1}`,
    productName: `Candidate Product ${index + 1}`,
    purchaseResultIds: [101 + index],
    billableQty: 2,
    billableUom: 'CTN',
    salesUnitPrice: 100,
    unitCostBasis: 60,
    lineAmount: 200,
    grossProfitAmount: 80,
    grossMarginPct: 40,
    grossMarginUnavailable: false,
  })),
});

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
  const purchaseCandidate = candidate('PURCHASED', ['item-1', 'item-2']);
  purchaseCandidate.orderId = 'order-purchased';
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([purchaseCandidate]);
  vi.mocked(generateDraftInvoiceFromPurchase).mockResolvedValue('invoice-new');
  vi.mocked(listInvoiceDraftCandidates)
    .mockResolvedValueOnce([purchaseCandidate])
    .mockResolvedValueOnce([]);
  vi.mocked(listInvoiceDraftListRows)
    .mockResolvedValueOnce(rows)
    .mockResolvedValueOnce([...rows, row('new', 'ABC Trading')]);
  renderPage();

  expect(await screen.findAllByText('ORD-PURCHASED')).toHaveLength(2);
  expect(screen.queryByRole('heading', { name: '請求候補' })).toBeNull();
  await actor.click(screen.getByRole('checkbox', { name: 'ORD-PURCHASED SKU-1 を選択' }));
  await actor.click(screen.getByRole('checkbox', { name: 'ORD-PURCHASED SKU-2 を選択' }));
  await actor.clear(screen.getByLabelText('ORD-PURCHASED SKU-1 請求単価'));
  await actor.type(screen.getByLabelText('ORD-PURCHASED SKU-1 請求単価'), '123.45');
  await actor.click(screen.getByRole('button', { name: '選択した候補からドラフト作成 (2)' }));

  await waitFor(() => expect(generateDraftInvoiceFromPurchase).toHaveBeenCalledWith({
    orderId: 'order-purchased',
    invoiceDate: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    purchaseResultIds: [101, 102],
    salesUnitPrices: { 'item-1': 123.45, 'item-2': 100 },
  }));
  expect(await screen.findByText('IVD-new')).toBeTruthy();
  expect(screen.queryAllByText('ORD-PURCHASED')).toHaveLength(0);
});

it('shows the backend UOM validation reason when candidate draft creation fails', async () => {
  const actor = userEvent.setup();
  const invalid = candidate('SKU-9');
  invalid.orderId = 'order-sku-9';
  invalid.items[0].productSku = 'SKU-000009';
  invalid.items[0].validationCode = 'INVOICE_UOM_UNSUPPORTED';
  invalid.items[0].validationMessage = 'SKU-000009: 不定貫商品の請求単位がCASEです。';
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([invalid]);
  renderPage();
  expect(await screen.findAllByText('ORD-SKU-9')).toHaveLength(1);
  expect(await screen.findByText(/SKU-000009: 不定貫商品の請求単位がCASE/)).toBeTruthy();
  expect(generateDraftInvoiceFromPurchase).not.toHaveBeenCalled();
});

it('toggles candidate checkboxes, supports multi-select/select-all and shows pricing and profit previews', async () => {
  const actor = userEvent.setup();
  vi.mocked(listInvoiceDraftListRows).mockResolvedValue([]);
  vi.mocked(listInvoiceDraftCandidates).mockResolvedValue([candidate('MULTI', ['candidate-a', 'candidate-b'])]);
  renderPage();

  const first = await screen.findByRole('checkbox', { name: 'ORD-MULTI SKU-1 を選択' });
  const second = screen.getByRole('checkbox', { name: 'ORD-MULTI SKU-2 を選択' });
  const all = screen.getByRole('checkbox', { name: '表示中の選択可能行を全選択' });
  await actor.click(first);
  expect((first as HTMLInputElement).checked).toBe(true);
  expect((all as HTMLInputElement).indeterminate).toBe(true);
  await actor.click(second);
  expect((all as HTMLInputElement).checked).toBe(true);
  await actor.click(all);
  expect((first as HTMLInputElement).checked).toBe(false);
  expect((second as HTMLInputElement).checked).toBe(false);
  expect(screen.getAllByDisplayValue('100')).toHaveLength(2);
  expect(screen.getAllByText('￥80')).toHaveLength(2);
  expect(screen.getAllByText('40.0%')).toHaveLength(2);
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
