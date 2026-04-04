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
  customerId?: number;
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
    id?: number;
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

export type CustomerDetail = {
  id: number;
  customerCode: string;
  name: string;
  active: boolean;
};

export type CustomerCreateRequest = {
  customerCode: string;
  name: string;
  active: boolean;
};

export type CustomerUpdateRequest = {
  name?: string;
  active?: boolean;
};

export type ProductOption = {
  id: number;
  label: string;
  name: string;
  orderUom: string;
  pricingBasisDefault: 'uom_count' | 'uom_kg';
};

export type ProductDetail = {
  id: number;
  sku: string;
  name: string;
  orderUom: string;
  purchaseUom: string;
  invoiceUom: string;
  pricingBasisDefault: 'uom_count' | 'uom_kg';
  isCatchWeight: boolean;
  weightCaptureRequired: boolean;
  active: boolean;
};

export type ProductCreateRequest = {
  sku: string;
  name: string;
  orderUom: string;
  purchaseUom: string;
  invoiceUom: string;
  pricingBasisDefault: 'uom_count' | 'uom_kg';
  isCatchWeight: boolean;
  weightCaptureRequired: boolean;
};

export type ProductUpdateRequest = {
  name?: string;
  orderUom?: string;
  purchaseUom?: string;
  invoiceUom?: string;
  isCatchWeight?: boolean;
  weightCaptureRequired?: boolean;
  active?: boolean;
};
