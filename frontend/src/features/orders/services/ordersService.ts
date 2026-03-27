import { mockOrders } from 'features/orders/mocks/orders';
import type { CreateOrderRequest, OrderDetail, OrderSummary } from 'features/orders/types/order';

const STORAGE_KEY = 'osv2_mock_orders';

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

export const listOrders = async (): Promise<OrderSummary[]> => {
  await sleep(250);
  return readOrders().map((o) => ({
    id: o.id,
    orderNo: o.orderNo,
    customerName: o.customerName,
    deliveryDate: o.deliveryDate,
    status: o.status,
    items: o.items,
  }));
};

export const getOrderItem = async (orderId: number, itemId: number) => {
  await sleep(200);
  const order = readOrders().find((o) => o.id === orderId);
  if (!order) return null;
  const item = order.items.find((i) => i.id === itemId);
  if (!item) return null;
  return { order, item };
};

export const createOrder = async (payload: CreateOrderRequest): Promise<OrderDetail> => {
  await sleep(300);
  const current = readOrders();
  const nextId = current.length === 0 ? 1 : Math.max(...current.map((o) => o.id)) + 1;

  const newOrder: OrderDetail = {
    id: nextId,
    orderNo: payload.orderNo,
    customerName: payload.customerName,
    deliveryDate: payload.deliveryDate,
    status: 'new',
    note: payload.note,
    createdAt: new Date().toISOString(),
    items: payload.items.map((item, index) => ({
      id: index + 1,
      productName: item.productName,
      quantity: item.quantity,
      unit: item.unit,
    })),
  };

  writeOrders([newOrder, ...current]);
  return newOrder;
};
