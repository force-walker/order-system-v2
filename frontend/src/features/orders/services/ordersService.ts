import { mockOrders } from 'features/orders/mocks/orders';
import type { CreateOrderRequest, CustomerOption, OrderDetail, OrderSummary, ProductOption } from 'features/orders/types/order';
import { parseApiErrorPayload, ServiceError } from 'shared/error';

const STORAGE_KEY = 'osv2_mock_orders';
const TOKEN_STORAGE_KEY = 'osv2_access_token';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

type ApiOrderResponse = {
  id: number;
  order_no: string;
  customer_id: number;
  delivery_date: string;
  status: OrderSummary['status'];
  note: string | null;
  created_at: string;
};

type ApiCustomerResponse = {
  id: number;
  customer_code: string;
  name: string;
};

type ApiProductResponse = {
  id: number;
  sku: string;
  name: string;
  order_uom: string;
  pricing_basis_default: 'uom_count' | 'uom_kg';
};

const apiOrderCache = new Map<number, OrderDetail>();
const customerNameCache = new Map<number, string>();

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const readOrders = (): OrderDetail[] => {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mockOrders));
    return mockOrders;
  }
  try {
    return JSON.parse(raw) as OrderDetail[];
  } catch {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mockOrders));
    return mockOrders;
  }
};

const writeOrders = (orders: OrderDetail[]) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(orders));
};

const toListItem = (o: OrderDetail): OrderSummary => ({
  id: o.id,
  orderNo: o.orderNo,
  customerName: o.customerName,
  deliveryDate: o.deliveryDate,
  status: o.status,
  items: o.items,
});

const ensureDevToken = async (): Promise<string> => {
  const cached = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (cached) return cached;

  const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: DEV_LOGIN_USER, role: DEV_LOGIN_ROLE }),
  });

  if (!res.ok) throw new ServiceError('ログインに失敗しました。設定を確認してください。', { code: 'login_failed', status: res.status });
  const data = (await res.json()) as { access_token: string };
  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
  return data.access_token;
};

const fetchWithAuth = async (path: string, init?: RequestInit) => {
  const token = await ensureDevToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) localStorage.removeItem(TOKEN_STORAGE_KEY);
  return res;
};

const mapApiOrderToDetail = (order: ApiOrderResponse): OrderDetail => {
  const cached = apiOrderCache.get(order.id);
  return {
    id: order.id,
    orderNo: order.order_no,
    customerName: cached?.customerName ?? customerNameCache.get(order.customer_id) ?? `顧客#${order.customer_id}`,
    deliveryDate: order.delivery_date,
    status: order.status,
    note: order.note ?? undefined,
    createdAt: order.created_at,
    items:
      cached?.items ?? [
        {
          id: 1,
          productName: '（明細未取得）',
          quantity: 0,
          unit: '-',
        },
      ],
  };
};

const loadCustomersApi = async (): Promise<CustomerOption[]> => {
  const res = await fetchWithAuth('/api/v1/customers', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiCustomerResponse[];
  return data.map((c) => {
    customerNameCache.set(c.id, c.name);
    return { id: c.id, label: `${c.id}: ${c.name} (${c.customer_code})` };
  });
};

const listOrdersApi = async (): Promise<OrderSummary[]> => {
  await loadCustomersApi();
  const res = await fetchWithAuth('/api/v1/orders', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiOrderResponse[];
  return data.map((row) => {
    const detail = mapApiOrderToDetail(row);
    apiOrderCache.set(detail.id, detail);
    return toListItem(detail);
  });
};

const createOrderApi = async (payload: CreateOrderRequest): Promise<OrderDetail> => {
  const res = await fetchWithAuth('/api/v1/orders', {
    method: 'POST',
    body: JSON.stringify({ customer_id: payload.customerId, delivery_date: payload.deliveryDate, note: payload.note ?? null }),
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const order = (await res.json()) as ApiOrderResponse;

  const itemRes = await fetchWithAuth(`/api/v1/orders/${order.id}/items/bulk`, {
    method: 'POST',
    body: JSON.stringify({
      items: payload.items.map((i) => ({
        product_id: i.productId,
        ordered_qty: i.quantity,
        order_uom_type: i.pricingBasis,
        pricing_basis: i.pricingBasis,
        unit_price_uom_count: i.pricingBasis === 'uom_count' ? i.unitPrice : null,
        unit_price_uom_kg: i.pricingBasis === 'uom_kg' ? i.unitPrice : null,
        note: null,
      })),
    }),
  });
  if (!itemRes.ok) throw await parseApiErrorPayload(itemRes);

  const itemResult = (await itemRes.json()) as { total: number; success: number; failed: number; errors: Array<{ message: string }> };
  if (itemResult.failed > 0) {
    throw new ServiceError(`明細登録で ${itemResult.failed} 件失敗しました`, { code: 'ORDER_ITEM_BULK_FAILED', status: 409 });
  }

  const detail: OrderDetail = {
    ...mapApiOrderToDetail(order),
    customerName: payload.customerName,
    items: payload.items.map((i, idx) => ({
      id: idx + 1,
      productId: i.productId,
      productName: i.productName,
      quantity: i.quantity,
      unit: i.unit,
      unitPrice: i.unitPrice,
      pricingBasis: i.pricingBasis,
    })),
  };
  customerNameCache.set(payload.customerId, payload.customerName);
  apiOrderCache.set(detail.id, detail);
  return detail;
};

const listOrdersMock = async (): Promise<OrderSummary[]> => {
  await sleep(250);
  return readOrders().map(toListItem);
};

const createOrderMock = async (payload: CreateOrderRequest): Promise<OrderDetail> => {
  await sleep(300);
  const current = readOrders();
  const nextId = current.length === 0 ? 1 : Math.max(...current.map((o) => o.id)) + 1;
  const newOrder: OrderDetail = {
    id: nextId,
    orderNo: payload.orderNo ?? `ORD-MOCK-${String(nextId).padStart(5, '0')}`,
    customerName: payload.customerName,
    deliveryDate: payload.deliveryDate,
    status: 'new',
    note: payload.note,
    createdAt: new Date().toISOString(),
    items: payload.items.map((item, index) => ({
      id: index + 1,
      productId: item.productId,
      productName: item.productName,
      quantity: item.quantity,
      unit: item.unit,
      unitPrice: item.unitPrice,
      pricingBasis: item.pricingBasis,
    })),
  };
  writeOrders([newOrder, ...current]);
  return newOrder;
};

export const listCustomers = async (): Promise<CustomerOption[]> => {
  if (USE_MOCK) return [{ id: 1, label: '1: テスト商事' }, { id: 2, label: '2: デモフーズ' }];
  return loadCustomersApi();
};

export const listProducts = async (): Promise<ProductOption[]> => {
  if (USE_MOCK) {
    return [
      { id: 1, label: '1: 鶏もも肉 (uom_kg)', name: '鶏もも肉', orderUom: 'kg', pricingBasisDefault: 'uom_kg' },
      { id: 2, label: '2: 玉ねぎ (uom_count)', name: '玉ねぎ', orderUom: 'case', pricingBasisDefault: 'uom_count' },
    ];
  }
  const res = await fetchWithAuth('/api/v1/products', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiProductResponse[];
  return data.map((p) => ({
    id: p.id,
    label: `${p.id}: ${p.name} (${p.pricing_basis_default})`,
    name: p.name,
    orderUom: p.order_uom,
    pricingBasisDefault: p.pricing_basis_default,
  }));
};

export const listOrders = async (): Promise<OrderSummary[]> => (USE_MOCK ? listOrdersMock() : listOrdersApi());

export const getOrderItem = async (orderId: number, itemId: number) => {
  await sleep(150);
  const order = USE_MOCK ? readOrders().find((o) => o.id === orderId) : apiOrderCache.get(orderId);
  if (!order) return null;
  const item = order.items.find((i) => i.id === itemId);
  if (!item) return null;
  return { order, item };
};

export const createOrder = async (payload: CreateOrderRequest): Promise<OrderDetail> => (USE_MOCK ? createOrderMock(payload) : createOrderApi(payload));
