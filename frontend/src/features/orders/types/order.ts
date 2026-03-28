export type OrderStatus =
  | 'new'
  | 'confirmed'
  | 'allocated'
  | 'purchased'
  | 'shipped'
  | 'invoiced'
  | 'cancelled';

export type OrderItem = {
  id: number;
  productName: string;
  quantity: number;
  unit: string;
  note?: string;
};

export type OrderSummary = {
  id: number;
  orderNo: string;
  customerName: string;
  deliveryDate: string;
  status: OrderStatus;
  items: OrderItem[];
};

export type OrderDetail = OrderSummary & {
  note?: string;
  createdAt: string;
};

export type CreateOrderRequest = {
  orderNo?: string;
  customerId: number;
  customerName: string;
  deliveryDate: string;
  note?: string;
  items: Array<{
    productName: string;
    quantity: number;
    unit: string;
  }>;
};

export type CustomerOption = {
  id: number;
  label: string;
};
