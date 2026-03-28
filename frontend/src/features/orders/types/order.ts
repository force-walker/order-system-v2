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
  productId?: number;
  productName: string;
  quantity: number;
  unit: string;
  unitPrice?: number;
  pricingBasis?: 'uom_count' | 'uom_kg';
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
    productId?: number;
    productName: string;
    quantity: number;
    unit: string;
    unitPrice: number;
    pricingBasis: 'uom_count' | 'uom_kg';
  }>;
};

export type CustomerOption = {
  id: number;
  label: string;
};

export type ProductOption = {
  id: number;
  label: string;
  name: string;
  orderUom: string;
  pricingBasisDefault: 'uom_count' | 'uom_kg';
};
