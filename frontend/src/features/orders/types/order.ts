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
  estimatedWeightKg?: number;
  targetPrice?: number;
  priceCeiling?: number;
  stockoutPolicy?: 'backorder' | 'substitute' | 'cancel' | 'split';
  comment?: string;
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
    estimatedWeightKg?: number;
    targetPrice?: number;
    priceCeiling?: number;
    stockoutPolicy?: 'backorder' | 'substitute' | 'cancel' | 'split';
    comment?: string;
  }>;
};

export type CustomerOption = {
  id: number;
  label: string;
  customerCode?: string;
  active?: boolean;
  createdAt?: string;
  updatedAt?: string;
};

export type CustomerDetail = {
  id: number;
  customerCode: string;
  name: string;
  active: boolean;
};

export type CustomerCreateRequest = {
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
  sku?: string;
  active?: boolean;
  name: string;
  orderUom: string;
  pricingBasisDefault: 'uom_count' | 'uom_kg';
  createdAt?: string;
  updatedAt?: string;
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

export type PurchaseResultStatus = 'not_filled' | 'filled' | 'partially_filled' | 'substituted';

export type PurchaseResultItem = {
  id: number;
  allocationId: number;
  supplierId?: number;
  purchasedQty: number;
  purchasedUom: string;
  actualWeightKg?: number;
  unitCost?: number;
  finalUnitCost?: number;
  shortageQty?: number;
  shortagePolicy?: string;
  resultStatus: PurchaseResultStatus;
  invoiceableFlag: boolean;
  recordedBy?: string;
  recordedAt: string;
  note?: string;
};

export type PurchaseResultFilter = {
  allocationId?: number;
  supplierId?: number;
  keyword?: string;
  limit?: number;
  offset?: number;
};

export type PurchaseResultResponse = {
  items: PurchaseResultItem[];
  total: number;
};

export type PurchaseResultCreateRequest = {
  allocationId: number;
  supplierId?: number;
  purchasedQty: number;
  purchasedUom: string;
  actualWeightKg?: number;
  unitCost?: number;
  finalUnitCost?: number;
  shortageQty?: number;
  shortagePolicy?: string;
  resultStatus: PurchaseResultStatus;
  invoiceableFlag: boolean;
  recordedBy?: string;
  note?: string;
};
