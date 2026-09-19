import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Exercise public service functions before and after consolidating authentication.
const services = [
  { name: 'orders', call: async () => (await import('../features/orders/services/ordersService')).listCustomers() },
  { name: 'invoices', call: async () => (await import('../features/orders/services/invoiceService')).listInvoiceDrafts() },
  { name: 'purchases', call: async () => (await import('../features/orders/services/purchaseService')).listPurchaseWorkQueue() },
  { name: 'allocations', call: async () => (await import('../features/orders/services/orderItemAllocationsService')).suggestOrderItemAllocations([12]) },
  { name: 'shipping', call: async () => (await import('../features/orders/services/shippingReportService')).getShippingReport('2026-09-17', 'customer') },
  { name: 'suppliers', call: async () => (await import('../features/suppliers/services/suppliersService')).listSupplierProductMappings(12) },
  { name: 'settings', call: async () => (await import('../features/settings/services/systemSettingsService')).getSystemSettings() },
];

const TOKEN_KEY = 'osv2_auth_session';
const saveToken = (token: string) => storage.set(TOKEN_KEY, JSON.stringify({ access_token: token, refresh_token: 'refresh' }));
const fetchMock = vi.fn<typeof fetch>();
let storage: Map<string, string>;

const successResponse = () => Response.json([]);

beforeEach(() => {
  storage = new Map();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, String(value)),
    removeItem: (key: string) => storage.delete(key),
  });
  vi.stubGlobal('window', { setTimeout, clearTimeout, dispatchEvent: vi.fn() });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubEnv('VITE_USE_MOCK', 'false');
  vi.stubEnv('VITE_API_BASE_URL', '');
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it('confirms a UUID order without converting its ID to a number', async () => {
  vi.stubGlobal('sessionStorage', { setItem: vi.fn() });
  saveToken('test-access');
  fetchMock.mockResolvedValue(Response.json({ updated_order_status: 'confirmed' }));
  const { confirmOrder } = await import('../features/orders/services/ordersService');
  await confirmOrder('30ae4186-04b9-4a13-985b-79edf1d061bc');
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/orders/30ae4186-04b9-4a13-985b-79edf1d061bc/bulk-transition');
  expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ from_status: 'new', to_status: 'confirmed' });
});

describe.each(services)('$name authentication contract', ({ call, name }) => {
  it('never automatically logs in an anonymous user', async () => {
    await expect(call()).rejects.toMatchObject({ status: 401, code: 'AUTH_REQUIRED' });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('reuses the saved token without logging in', async () => {
    saveToken('cached-token');
    fetchMock.mockResolvedValueOnce(successResponse());
    await call();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({ Authorization: 'Bearer cached-token' });
  });

  it('removes an expired token on 401 without retrying the request', async () => {
    saveToken('expired');
    fetchMock.mockResolvedValueOnce(Response.json({ detail: { code: 'AUTH_REQUIRED', message: 'expired' } }, { status: 401 }));
    await expect(call()).rejects.toMatchObject({ status: 401, code: 'AUTH_REQUIRED' });
    expect(storage.has(TOKEN_KEY)).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('preserves request methods and body for a signed-in user', async () => {
    saveToken('cached-token');
    fetchMock.mockResolvedValueOnce(successResponse());
    await call();
    expect(fetchMock.mock.calls[0][1]?.method).toBe(name === 'allocations' ? 'POST' : 'GET');
    if (name === 'allocations') expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ order_item_ids: [12] }));
  });

  it('keeps the token on a transport failure', async () => {
    saveToken('cached-token');
    const failure = new TypeError('network unavailable');
    fetchMock.mockRejectedValueOnce(failure);
    await expect(call()).rejects.toBe(failure);
    expect(JSON.parse(storage.get(TOKEN_KEY)!).access_token).toBe('cached-token');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
