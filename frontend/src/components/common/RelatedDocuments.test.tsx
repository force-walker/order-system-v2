// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RelatedDocuments } from './RelatedDocuments';
import { getRelatedDocuments, type RelatedDocumentsResponse } from './relatedDocumentsService';

vi.mock('./relatedDocumentsService', () => ({ getRelatedDocuments: vi.fn() }));

const empty = (): RelatedDocumentsResponse => ({ orders: [], deliveries: [], invoices: [], supplier_bills: [] });

beforeEach(() => vi.mocked(getRelatedDocuments).mockResolvedValue(empty()));
afterEach(cleanup);

const show = (type: 'order' | 'invoice' | 'supplier_bill', id: string) => render(
  <MemoryRouter><RelatedDocuments type={type} id={id} /></MemoryRouter>,
);

it('renders nothing for an order without related business documents', async () => {
  const { container } = show('order', 'o1');
  await vi.waitFor(() => expect(getRelatedDocuments).toHaveBeenCalled());
  expect(container.querySelector('[aria-label="関連データ"]')).toBeNull();
  expect(screen.queryByText('未作成')).toBeNull();
});

it('links a single finalized invoice directly', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({ ...empty(), invoices: [{ type: 'invoice', id: 'i1', number: 'INV-1', status: 'finalized' }] });
  show('order', 'o1');
  const link = await screen.findByRole('link', { name: /請求.*1/ });
  expect(link.getAttribute('href')).toBe('/invoices/i1');
});

it('links a single draft invoice to its draft detail', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({ ...empty(), invoices: [{ type: 'invoice', id: 'i1', number: 'IVD-00000001', status: 'draft' }] });
  show('order', 'o1');
  expect((await screen.findByRole('link', { name: /請求.*1/ })).getAttribute('href')).toBe('/invoices/drafts/i1');
});

it('shows a compact menu for multiple invoices and keeps each route selectable', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({ ...empty(), invoices: [
    { type: 'invoice', id: 'i1', number: 'IVD-1', status: 'draft' },
    { type: 'invoice', id: 'i2', number: 'INV-2', status: 'finalized' },
  ] });
  show('order', 'o1');
  fireEvent.click(await screen.findByText('請求'));
  expect(screen.getByRole('link', { name: /IVD-1/ }).getAttribute('href')).toBe('/invoices/drafts/i1');
  expect(screen.getByRole('link', { name: /INV-2/ }).getAttribute('href')).toBe('/invoices/i2');
});

it('shows the supplier bill count and menu', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({ ...empty(), supplier_bills: [
    { type: 'supplier_bill', id: 'b1', number: 'APB-1', status: 'finalized' },
    { type: 'supplier_bill', id: 'b2', number: 'APB-2', status: 'cancelled' },
  ] });
  show('order', 'o1');
  expect(await screen.findByText('仕入請求')).toBeTruthy();
  expect(screen.getByText('2')).toBeTruthy();
});

it('hides the current invoice and shows its related order', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({
    ...empty(),
    orders: [{ type: 'order', id: 'o1', number: 'ORD-1', status: 'invoiced' }],
    invoices: [{ type: 'invoice', id: 'i1', number: 'INV-1', status: 'finalized' }],
  });
  show('invoice', 'i1');
  expect((await screen.findByRole('link', { name: /受注.*1/ })).getAttribute('href')).toBe('/orders/o1/edit');
  expect(screen.queryByText('請求')).toBeNull();
});

it('shows order and customer invoice links on a supplier bill', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({
    ...empty(),
    orders: [{ type: 'order', id: 'o1', number: 'ORD-1', status: 'invoiced' }],
    invoices: [{ type: 'invoice', id: 'i1', number: 'INV-1', status: 'finalized' }],
    supplier_bills: [{ type: 'supplier_bill', id: 'b1', number: 'APB-1', status: 'finalized' }],
  });
  show('supplier_bill', 'b1');
  expect((await screen.findByRole('link', { name: /受注.*1/ })).getAttribute('href')).toBe('/orders/o1/edit');
  expect(screen.getByRole('link', { name: /請求.*1/ }).getAttribute('href')).toBe('/invoices/i1');
  expect(screen.queryByText('仕入請求')).toBeNull();
});

it('does not expose Delivery as a primary related smart button', async () => {
  vi.mocked(getRelatedDocuments).mockResolvedValue({ ...empty(), deliveries: [{ type: 'delivery', id: 'd1', number: 'DEL-1', status: null }] });
  const { container } = show('order', 'o1');
  await vi.waitFor(() => expect(getRelatedDocuments).toHaveBeenCalled());
  expect(container.querySelector('[aria-label="関連データ"]')).toBeNull();
  expect(screen.queryByText('納品')).toBeNull();
});
