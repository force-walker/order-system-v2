// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProductDetailPage } from 'features/products/pages/ProductDetailPage';
import { CustomerDetailPage } from 'features/customers/pages/CustomerDetailPage';
import { SupplierDetailPage } from 'features/suppliers/pages/SupplierDetailPage';
import { getProductDetail } from 'features/products/services/productsService';
import { getCustomerDetail } from 'features/customers/services/customersService';
import { getSupplier } from 'features/suppliers/services/suppliersService';

vi.mock('features/products/components/ProductSupplierMappingPanel', () => ({ ProductSupplierMappingPanel: () => null }));
vi.mock('features/suppliers/components/SupplierProductMappingPanel', () => ({ SupplierProductMappingPanel: () => null }));
vi.mock('features/products/services/productsService', () => ({
  getProductDetail: vi.fn(), listProducts: vi.fn(), archiveProduct: vi.fn(), unarchiveProduct: vi.fn(), deleteProduct: vi.fn(),
}));
vi.mock('features/customers/services/customersService', () => ({
  getCustomerDetail: vi.fn(), listCustomers: vi.fn(), archiveCustomer: vi.fn(), unarchiveCustomer: vi.fn(), deleteCustomer: vi.fn(),
}));
vi.mock('features/suppliers/services/suppliersService', () => ({
  getSupplier: vi.fn(), listSuppliers: vi.fn(), archiveSupplier: vi.fn(), unarchiveSupplier: vi.fn(), deleteSupplier: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(getProductDetail).mockImplementation(async (id) => ({
    id, sku: `SKU-${id}`, name: `Product ${id}`, orderUom: 'PC', purchaseUom: 'PC', invoiceUom: 'PC',
    pricingBasisDefault: 'uom_count', isCatchWeight: false, weightCaptureRequired: false, active: true,
  }));
  vi.mocked(getCustomerDetail).mockImplementation(async (id) => ({ id, customerCode: `C-${id}`, name: `Customer ${id}`, active: true }));
  vi.mocked(getSupplier).mockImplementation(async (id) => ({
    id, supplierCode: `S-${id}`, name: `Supplier ${id}`, active: true, createdAt: '2026-01-01', updatedAt: '2026-01-01',
  }));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const cases = [
  { base: '/products', path: '/products/:productId', Page: ProductDetailPage, get: getProductDetail, expected: 'Product 2' },
  { base: '/customers', path: '/customers/:customerId', Page: CustomerDetailPage, get: getCustomerDetail, expected: 'Customer 2' },
  { base: '/suppliers', path: '/suppliers/:supplierId', Page: SupplierDetailPage, get: getSupplier, expected: 'Supplier 2' },
] as const;

cases.forEach(({ base, path, Page, get, expected }) => {
  it(`${base} detail keeps context while moving to the next record`, async () => {
    const actor = userEvent.setup();
    render(
      <MemoryRouter initialEntries={[`${base}/1?ids=1%2C2&list=q%3Dneedle%26sort%3Dname`]}>
        <Routes><Route path={path} element={<Page />} /></Routes>
      </MemoryRouter>,
    );
    await actor.click(await screen.findByRole('button', { name: '次へ →' }));
    await screen.findByText(expected);
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(2));
    expect(screen.getByRole('link', { name: /一覧へ戻る/ }).getAttribute('href')).toBe(`${base}?q=needle&sort=name`);
    expect((screen.getByRole('button', { name: '次へ →' }) as HTMLButtonElement).disabled).toBe(true);
  });
});
