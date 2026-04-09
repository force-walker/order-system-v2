import { mockOrders } from 'features/orders/mocks/orders';
import type {
  CreateOrderRequest,
  CustomerCreateRequest,
  CustomerDetail,
  CustomerOption,
  CustomerUpdateRequest,
  OrderDetail,
  OrderSummary,
  ProductCreateRequest,
  ProductDetail,
  ProductOption,
  ProductUpdateRequest,
} from 'features/orders/types/order';
import { apiJson, apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload, ServiceError } from 'shared/error';
import {
  toApiCustomerCreate,
  toApiCustomerUpdate,
  toApiOrderCreateHeader,
  toApiProductCreate,
  toApiProductUpdate,
  toCustomerDetail,
  toCustomerOption,
  toProductDetail,
  toProductOption,
  type ApiCustomerResponse,
  type ApiLoginRequest,
  type ApiOrderCreateRequest,
  type ApiOrderResponse,
  type ApiProductResponse,
  type ApiTokenResponse,
} from './ordersDto';

const DEBUG_ORDER_ITEM_FIELDS = (import.meta.env.VITE_DEBUG_ORDER_ITEM_FIELDS ?? 'true') === 'true';

const STORAGE_KEY = 'osv2_mock_orders';
const TOKEN_STORAGE_KEY = 'osv2_access_token';
const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

type ApiOrderItemResponse = {
  id: number;
  order_id: number;
  product_id: number;
  ordered_qty: number;
  order_uom_type: 'uom_count' | 'uom_kg';
  estimated_weight_kg: number | null;
  target_price: number | null;
  price_ceiling: number | null;
  stockout_policy: 'backorder' | 'substitute' | 'cancel' | 'split' | null;
  pricing_basis: 'uom_count' | 'uom_kg';
  unit_price_uom_count: number | null;
  unit_price_uom_kg: number | null;
  note: string | null;
  comment: string | null;
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

  const loginBody: ApiLoginRequest = { user_id: DEV_LOGIN_USER, role: DEV_LOGIN_ROLE };
  const data = await apiJson<ApiTokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: loginBody,
  });

  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
  return data.access_token;
};

const fetchWithAuth = async (path: string, init?: { method?: string; body?: unknown }) => {
  const token = await ensureDevToken();
  const res = await apiRequest(path, {
    method: init?.method,
    body: init?.body,
    authToken: token,
  });

  if (res.status === 401) localStorage.removeItem(TOKEN_STORAGE_KEY);
  return res;
};

const loadCustomersApi = async (includeInactive = false): Promise<CustomerOption[]> => {
  const query = includeInactive ? '?include_inactive=true' : '';
  const res = await fetchWithAuth(`/api/v1/customers${query}`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiCustomerResponse[];
  return data.map((c) => {
    customerNameCache.set(c.id, c.name);
    return toCustomerOption(c);
  });
};

const loadProductsApi = async (includeInactive = false): Promise<ProductOption[]> => {
  const query = includeInactive ? '?include_inactive=true' : '';
  const res = await fetchWithAuth(`/api/v1/products${query}`, { method: 'GET' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const data = (await res.json()) as ApiProductResponse[];
  return data.map((p) => {
    const option = toProductOption(p);
    productCache.set(p.id, option);
    return option;
  });
};

const mapApiOrderToDetail = (order: ApiOrderResponse): OrderDetail => {
  const cached = apiOrderCache.get(order.id);
  const mappedByCustomerId = customerNameCache.get(order.customer_id);
  const mappedByOrderCache = cached?.customerId === order.customer_id ? cached?.customerName : undefined;
  return {
    id: order.id,
    customerId: order.customer_id,
    orderNo: order.order_no,
    customerName: mappedByCustomerId ?? mappedByOrderCache ?? `顧客#${order.customer_id}`,
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
    estimatedWeightKg: item.estimated_weight_kg ?? undefined,
    targetPrice: item.target_price ?? undefined,
    priceCeiling: item.price_ceiling ?? undefined,
    stockoutPolicy: item.stockout_policy ?? undefined,
    comment: item.comment ?? undefined,
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
  if (DEBUG_ORDER_ITEM_FIELDS) {
    console.debug('[order-items][read][response]', data);
  }
  return data.map(mapApiOrderItem);
};

const createOrderApi = async (payload: CreateOrderRequest): Promise<OrderDetail> => {
  const orderBody: ApiOrderCreateRequest = toApiOrderCreateHeader(
    payload.customerId,
    payload.deliveryDate,
    payload.note,
    payload.orderNo,
  );

  const res = await fetchWithAuth('/api/v1/orders', {
    method: 'POST',
    body: orderBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const order = (await res.json()) as ApiOrderResponse;

  const bulkPayload = {
    items: payload.items.map((i) => ({
      product_id: i.productId,
      ordered_qty: i.quantity,
      order_uom_type: i.pricingBasis,
      estimated_weight_kg: i.estimatedWeightKg ?? null,
      target_price: i.targetPrice ?? null,
      price_ceiling: i.priceCeiling ?? null,
      stockout_policy: i.stockoutPolicy ?? null,
      pricing_basis: i.pricingBasis,
      unit_price_uom_count: i.pricingBasis === 'uom_count' ? i.unitPrice : null,
      unit_price_uom_kg: i.pricingBasis === 'uom_kg' ? i.unitPrice : null,
      note: null,
      comment: i.comment ?? null,
    })),
  };

  if (DEBUG_ORDER_ITEM_FIELDS) {
    console.debug('[order-items][create][request]', bulkPayload);
  }

  const itemRes = await fetchWithAuth(`/api/v1/orders/${order.id}/items/bulk`, {
    method: 'POST',
    body: bulkPayload,
  });
  if (!itemRes.ok) throw await parseApiErrorPayload(itemRes);

  const itemResult = (await itemRes.json()) as { failed: number };
  if (DEBUG_ORDER_ITEM_FIELDS) {
    console.debug('[order-items][create][response]', itemResult);
  }
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
    body: { customer_id: payload.customerId, delivery_date: payload.deliveryDate, note: payload.note ?? null },
  });

  if (!res.ok) throw await parseApiErrorPayload(res);
};

const createOrderItemApi = async (orderId: number, item: CreateOrderRequest['items'][number]) => {
  const itemPayload = {
    product_id: item.productId,
    ordered_qty: item.quantity,
    order_uom_type: item.pricingBasis,
    estimated_weight_kg: item.estimatedWeightKg ?? null,
    target_price: item.targetPrice ?? null,
    price_ceiling: item.priceCeiling ?? null,
    stockout_policy: item.stockoutPolicy ?? null,
    pricing_basis: item.pricingBasis,
    unit_price_uom_count: item.pricingBasis === 'uom_count' ? item.unitPrice : null,
    unit_price_uom_kg: item.pricingBasis === 'uom_kg' ? item.unitPrice : null,
    note: null,
    comment: item.comment ?? null,
  };
  if (DEBUG_ORDER_ITEM_FIELDS) {
    console.debug('[order-items][update-flow][create][request]', itemPayload);
  }

  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items`, {
    method: 'POST',
    body: itemPayload,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
};

const updateOrderItemApi = async (orderId: number, item: CreateOrderRequest['items'][number]) => {
  const itemPayload = {
    ordered_qty: item.quantity,
    order_uom_type: item.pricingBasis,
    estimated_weight_kg: item.estimatedWeightKg ?? null,
    target_price: item.targetPrice ?? null,
    price_ceiling: item.priceCeiling ?? null,
    stockout_policy: item.stockoutPolicy ?? null,
    pricing_basis: item.pricingBasis,
    unit_price_uom_count: item.pricingBasis === 'uom_count' ? item.unitPrice : null,
    unit_price_uom_kg: item.pricingBasis === 'uom_kg' ? item.unitPrice : null,
    note: null,
    comment: item.comment ?? null,
  };
  if (DEBUG_ORDER_ITEM_FIELDS) {
    console.debug('[order-items][update-flow][update][request]', { itemId: item.id, payload: itemPayload });
  }

  const res = await fetchWithAuth(`/api/v1/orders/${orderId}/items/${item.id}`, {
    method: 'PATCH',
    body: itemPayload,
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
      estimatedWeightKg: item.estimatedWeightKg,
      targetPrice: item.targetPrice,
      priceCeiling: item.priceCeiling,
      stockoutPolicy: item.stockoutPolicy,
      comment: item.comment,
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
      estimatedWeightKg: i.estimatedWeightKg,
      targetPrice: i.targetPrice,
      priceCeiling: i.priceCeiling,
      stockoutPolicy: i.stockoutPolicy,
      comment: i.comment,
    }));
    writeOrders([...current]);
    return target;
  }

  const existingItems = await listOrderItemsApi(orderId);
  await updateOrderHeaderApi(orderId, payload);
  customerNameCache.set(payload.customerId, payload.customerName);

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

export const listCustomers = async (includeInactive = false): Promise<CustomerOption[]> => {
  if (USE_MOCK) return [{ id: 1, label: '1: テスト商事' }, { id: 2, label: '2: デモフーズ' }];
  return loadCustomersApi(includeInactive);
};

export const getCustomer = async (customerId: number): Promise<CustomerOption | null> => {
  const customers = await listCustomers();
  return customers.find((c) => c.id === customerId) ?? null;
};

export const getCustomerDetail = async (customerId: number): Promise<CustomerDetail | null> => {
  if (USE_MOCK) {
    const row = [
      { id: 1, customerCode: 'CUST-001', name: 'テスト商事', active: true },
      { id: 2, customerCode: 'CUST-002', name: 'デモフーズ', active: true },
    ].find((c) => c.id === customerId);
    return row ?? null;
  }

  const res = await fetchWithAuth(`/api/v1/customers/${customerId}`, { method: 'GET' });
  if (res.status === 404) return null;
  if (!res.ok) throw await parseApiErrorPayload(res);

  const row = (await res.json()) as ApiCustomerResponse;
  customerNameCache.set(row.id, row.name);
  return toCustomerDetail(row);
};

export const createCustomer = async (payload: CustomerCreateRequest): Promise<CustomerDetail> => {
  if (USE_MOCK) {
    return {
      id: Date.now(),
      customerCode: `CUST-MOCK-${Date.now()}`,
      name: payload.name,
      active: payload.active,
    };
  }

  const customerBody = toApiCustomerCreate(payload);

  const res = await fetchWithAuth('/api/v1/customers', {
    method: 'POST',
    body: customerBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const row = (await res.json()) as ApiCustomerResponse;
  customerNameCache.set(row.id, row.name);
  return toCustomerDetail(row);
};

export const updateCustomer = async (customerId: number, payload: CustomerUpdateRequest): Promise<CustomerDetail> => {
  if (USE_MOCK) {
    return {
      id: customerId,
      customerCode: `CUST-${String(customerId).padStart(3, '0')}`,
      name: payload.name ?? 'テスト商事',
      active: payload.active ?? true,
    };
  }

  const customerPatchBody = toApiCustomerUpdate(payload);

  const res = await fetchWithAuth(`/api/v1/customers/${customerId}`, {
    method: 'PATCH',
    body: customerPatchBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const row = (await res.json()) as ApiCustomerResponse;
  customerNameCache.set(row.id, row.name);
  return toCustomerDetail(row);
};

export const archiveCustomer = async (customerId: number): Promise<CustomerDetail> => {
  const res = await fetchWithAuth(`/api/v1/customers/${customerId}/archive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiCustomerResponse;
  return toCustomerDetail(row);
};

export const unarchiveCustomer = async (customerId: number): Promise<CustomerDetail> => {
  const res = await fetchWithAuth(`/api/v1/customers/${customerId}/unarchive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiCustomerResponse;
  return toCustomerDetail(row);
};

export const deleteCustomer = async (customerId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/customers/${customerId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
};

export const listProducts = async (includeInactive = false): Promise<ProductOption[]> => {
  if (USE_MOCK) {
    return [
      { id: 1, label: '1: 鶏もも肉 (uom_kg)', name: '鶏もも肉', orderUom: 'kg', pricingBasisDefault: 'uom_kg' },
      { id: 2, label: '2: 玉ねぎ (uom_count)', name: '玉ねぎ', orderUom: 'case', pricingBasisDefault: 'uom_count' },
    ];
  }
  return loadProductsApi(includeInactive);
};

export const getProduct = async (productId: number): Promise<ProductOption | null> => {
  const products = await listProducts();
  return products.find((p) => p.id === productId) ?? null;
};

export const getProductDetail = async (productId: number): Promise<ProductDetail | null> => {
  if (USE_MOCK) {
    const row = [
      {
        id: 1,
        sku: 'PRD-001',
        name: '鶏もも肉',
        orderUom: 'kg',
        purchaseUom: 'kg',
        invoiceUom: 'kg',
        pricingBasisDefault: 'uom_kg' as const,
        isCatchWeight: true,
        weightCaptureRequired: true,
        active: true,
      },
      {
        id: 2,
        sku: 'PRD-002',
        name: '玉ねぎ',
        orderUom: 'case',
        purchaseUom: 'case',
        invoiceUom: 'case',
        pricingBasisDefault: 'uom_count' as const,
        isCatchWeight: false,
        weightCaptureRequired: false,
        active: true,
      },
    ].find((p) => p.id === productId);
    return row ?? null;
  }

  const res = await fetchWithAuth(`/api/v1/products/${productId}`, { method: 'GET' });
  if (res.status === 404) return null;
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiProductResponse;
  return {
    id: row.id,
    sku: row.sku,
    name: row.name,
    orderUom: row.order_uom,
    purchaseUom: row.purchase_uom,
    invoiceUom: row.invoice_uom,
    pricingBasisDefault: row.pricing_basis_default,
    isCatchWeight: row.is_catch_weight,
    weightCaptureRequired: row.weight_capture_required,
    active: row.active,
  };
};

export const createProduct = async (payload: ProductCreateRequest): Promise<ProductDetail> => {
  if (USE_MOCK) {
    return {
      id: Date.now(),
      sku: `PRD-MOCK-${Date.now()}`,
      name: payload.name,
      orderUom: payload.orderUom,
      purchaseUom: payload.purchaseUom,
      invoiceUom: payload.invoiceUom,
      pricingBasisDefault: payload.pricingBasisDefault,
      isCatchWeight: payload.isCatchWeight,
      weightCaptureRequired: payload.weightCaptureRequired,
      active: true,
    };
  }

  const productBody = toApiProductCreate(payload);

  const res = await fetchWithAuth('/api/v1/products', {
    method: 'POST',
    body: productBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiProductResponse;
  return toProductDetail(row);
};

export const updateProduct = async (productId: number, payload: ProductUpdateRequest): Promise<ProductDetail> => {
  if (USE_MOCK) {
    return {
      id: productId,
      sku: `PRD-${String(productId).padStart(3, '0')}`,
      name: payload.name ?? 'サンプル商品',
      orderUom: payload.orderUom ?? 'kg',
      purchaseUom: payload.purchaseUom ?? 'kg',
      invoiceUom: payload.invoiceUom ?? 'kg',
      pricingBasisDefault: 'uom_count',
      isCatchWeight: payload.isCatchWeight ?? false,
      weightCaptureRequired: payload.weightCaptureRequired ?? false,
      active: payload.active ?? true,
    };
  }

  const productPatchBody = toApiProductUpdate(payload);

  const res = await fetchWithAuth(`/api/v1/products/${productId}`, {
    method: 'PATCH',
    body: productPatchBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiProductResponse;
  return toProductDetail(row);
};

export const archiveProduct = async (productId: number): Promise<ProductDetail> => {
  const res = await fetchWithAuth(`/api/v1/products/${productId}/archive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiProductResponse;
  return toProductDetail(row);
};

export const unarchiveProduct = async (productId: number): Promise<ProductDetail> => {
  const res = await fetchWithAuth(`/api/v1/products/${productId}/unarchive`, { method: 'POST' });
  if (!res.ok) throw await parseApiErrorPayload(res);
  const row = (await res.json()) as ApiProductResponse;
  return toProductDetail(row);
};

export const deleteProduct = async (productId: number): Promise<void> => {
  const res = await fetchWithAuth(`/api/v1/products/${productId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) throw await parseApiErrorPayload(res);
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
