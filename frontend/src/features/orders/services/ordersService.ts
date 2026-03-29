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

type ApiOrderItemResponse = {
  id: number;
  order_id: number;
  product_id: number;
  ordered_qty: number;
  order_uom_type: 'uom_count' | 'uom_kg';
  pricing_basis: 'uom_count' | 'uom_kg';
  unit_price_uom_count: number | null;
  unit_price_uom_kg: number | null;
  note: string | null;
};

const apiOrderCache = new Map<number, OrderDetail>();
const customerNameCache = new Map<number, string>();
const productCache = new Map<number, ProductOption>();

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
  customerId: o.customerId,
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

const loadCustomersApi = async (): Promise<CustomerOption[]> => {
  const res = await fetchWithAuth('/api/v1/customers', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiCustomerResponse[];
  return data.map((c) => {
    customerNameCache.set(c.id, c.name);
    return { id: c.id, label: `${c.id}: ${c.name} (${c.customer_code})` };
  });
};

const loadProductsApi = async (): Promise<ProductOption[]> => {
  const res = await fetchWithAuth('/api/v1/products', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiProductResponse[];
  return data.map((p) => {
    const option: ProductOption = {
      id: p.id,
      label: `${p.id}: ${p.name} (${p.pricing_basis_default})`,
      name: p.name,
      orderUom: p.order_uom,
      pricingBasisDefault: p.pricing_basis_default,
    };
    productCache.set(p.id, option);
    return option;
  });
};

const mapApiOrderToDetail = (order: ApiOrderResponse): OrderDetail => {
  const cached = apiOrderCache.get(order.id);
  return {
    id: order.id,
    customerId: order.customer_id,
    orderNo: order.order_no,
    customerName: cached?.customerName ?? customerNameCache.get(order.customer_id) ?? `顧客#${order.customer_id}`,
    deliveryDate: order.delivery_date,
    status: order.status,
    note: order.note ?? undefined,
    createdAt: order.created_at,
    items: cached?.items ?? [],
  };
};

const mapApiOrderItem = (item: ApiOrderItemResponse) => {
  const p = productCache.get(item.product_id);
  const pricingBasis = item.pricing_basis;
  const unitPrice = pricingBasis === 'uom_kg' ? item.unit_price_uom_kg : item.unit_price_uom_count;
  return {
    id: item.id,
    productId: item.product_id,
    productName: p?.name ?? `商品#${item.product_id}`,
    quantity: item.ordered_qty,
    unit: p?.orderUom ?? item.order_uom_type,
    unitPrice: unitPrice ?? 0,
    pricingBasis,
    note: item.note ?? undefined,
  };
};

const listOrdersApi = async (): Promise<OrderSummary[]> => {
  await Promise.all([loadCustomersApi(), loadProductsApi()]);
  const res = await fetchWithAuth('/api/v1/orders', { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiOrderResponse[];

  const details = await Promise.all(
    data.map(async (row) => {
      const detail = mapApiOrderToDetail(row);
      try {
        detail.items = await listOrderItemsApi(row.id);
      } catch {
        detail.items = [];
      }
      apiOrderCache.set(detail.id, detail);
      return detail;
    }),
  );

  return details.map(toListItem);
};

const listOrderItemsApi = async (orderId: number) => {
  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiOrderItemResponse[];
  return data.map(mapApiOrderItem);
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

  const itemResult = (await itemRes.json()) as { failed: number };
  if (itemResult.failed > 0) throw new ServiceError(`明細登録で ${itemResult.failed} 件失敗しました`, { code: 'ORDER_ITEM_BULK_FAILED', status: 409 });

  const items = await listOrderItemsApi(order.id);
  const detail: OrderDetail = {
    ...mapApiOrderToDetail(order),
    customerName: payload.customerName,
    items,
  };
  customerNameCache.set(payload.customerId, payload.customerName);
  apiOrderCache.set(detail.id, detail);
  return detail;
};

const updateOrderHeaderApi = async (orderId: number, payload: CreateOrderRequest) => {
  const res = await fetchWithAuth(`/api/v1/orders/${orderId}`, {
    method: 'PATCH',
    body: JSON.stringify({ customer_id: payload.customerId, delivery_date: payload.deliveryDate, note: payload.note ?? null }),
  });

  if (res.status === 405) {
    throw new ServiceError('注文ヘッダー更新API（PATCH /orders/{order_id}）がbackend側で未対応です。', {
      code: 'ORDER_HEADER_PATCH_NOT_IMPLEMENTED',
      status: 405,
    });
  }

  if (!res.ok) throw await parseApiErrorPayload(res);
};

const createOrderItemApi = async (orderId: number, item: CreateOrderRequest['items'][number]) => {
  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items`, {
    method: 'POST',
    body: JSON.stringify({
      product_id: item.productId,
      ordered_qty: item.quantity,
      order_uom_type: item.pricingBasis,
      pricing_basis: item.pricingBasis,
      unit_price_uom_count: item.pricingBasis === 'uom_count' ? item.unitPrice : null,
      unit_price_uom_kg: item.pricingBasis === 'uom_kg' ? item.unitPrice : null,
      note: null,
    }),
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
};

const updateOrderItemApi = async (orderId: number, item: CreateOrderRequest['items'][number]) => {
  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items/${item.id}`, {
    method: 'PATCH',
    body: JSON.stringify({
      ordered_qty: item.quantity,
      order_uom_type: item.pricingBasis,
      pricing_basis: item.pricingBasis,
      unit_price_uom_count: item.pricingBasis === 'uom_count' ? item.unitPrice : null,
      unit_price_uom_kg: item.pricingBasis === 'uom_kg' ? item.unitPrice : null,
      note: null,
    }),
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
};

const deleteOrderItemApi = async (orderId: number, itemId: number) => {
  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items/${itemId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
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
    customerId: payload.customerId,
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

export const updateOrder = async (orderId: number, payload: CreateOrderRequest): Promise<OrderDetail> => {
  if (USE_MOCK) {
    const current = readOrders();
    const target = current.find((o) => o.id === orderId);
    if (!target) throw new ServiceError('注文が見つかりません', { code: 'ORDER_NOT_FOUND', status: 404 });
    target.customerId = payload.customerId;
    target.customerName = payload.customerName;
    target.deliveryDate = payload.deliveryDate;
    target.note = payload.note;
    target.items = payload.items.map((i, idx) => ({
      id: i.id ?? idx + 1,
      productId: i.productId,
      productName: i.productName,
      quantity: i.quantity,
      unit: i.unit,
      unitPrice: i.unitPrice,
      pricingBasis: i.pricingBasis,
    }));
    writeOrders([...current]);
    return target;
  }

  const existingItems = await listOrderItemsApi(orderId);
  await updateOrderHeaderApi(orderId, payload);

  const existingMap = new Map(existingItems.map((i) => [i.id, i]));
  const incomingIds = new Set<number>();

  for (const item of payload.items) {
    if (item.id && existingMap.has(item.id)) {
      incomingIds.add(item.id);
      await updateOrderItemApi(orderId, item);
    } else {
      await createOrderItemApi(orderId, item);
    }
  }

  for (const old of existingItems) {
    if (!incomingIds.has(old.id)) {
      await deleteOrderItemApi(orderId, old.id);
    }
  }

  const order = await getOrder(orderId);
  if (!order) throw new ServiceError('更新後の注文取得に失敗しました', { code: 'ORDER_RELOAD_FAILED', status: 500 });
  return order;
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
  return loadProductsApi();
};

export const listOrders = async (): Promise<OrderSummary[]> => (USE_MOCK ? listOrdersMock() : listOrdersApi());

export const getOrder = async (orderId: number): Promise<OrderDetail | null> => {
  if (USE_MOCK) {
    return readOrders().find((o) => o.id === orderId) ?? null;
  }

  await Promise.all([loadCustomersApi(), loadProductsApi()]);
  const orderRes = await fetchWithAuth(`/api/v1/orders/${orderId}`, { method: 'GET' });
  if (orderRes.status === 404) return null;
  if (!orderRes.ok) throw await parseApiErrorPayload(orderRes);
  const order = (await orderRes.json()) as ApiOrderResponse;

  const items = await listOrderItemsApi(orderId);
  const detail: OrderDetail = {
    ...mapApiOrderToDetail(order),
    items,
  };
  apiOrderCache.set(orderId, detail);
  return detail;
};

export const getOrderItem = async (orderId: number, itemId: number) => {
  await sleep(100);
  const order = await getOrder(orderId);
  if (!order) return null;
  const item = order.items.find((i) => i.id === itemId);
  if (!item) return null;
  return { order, item };
};

export const createOrder = async (payload: CreateOrderRequest): Promise<OrderDetail> => (USE_MOCK ? createOrderMock(payload) : createOrderApi(payload));
