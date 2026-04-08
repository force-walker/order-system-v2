import type { components } from 'generated/openapi';
import type {
  CustomerCreateRequest,
  CustomerDetail,
  CustomerOption,
  CustomerUpdateRequest,
  ProductCreateRequest,
  ProductDetail,
  ProductOption,
  ProductUpdateRequest,
} from 'features/orders/types/order';

export type ApiCustomerResponse = components['schemas']['CustomerResponse'];
export type ApiProductResponse = components['schemas']['ProductResponse'];
export type ApiCustomerCreateRequest = components['schemas']['CustomerCreateRequest'];
export type ApiCustomerUpdateRequest = components['schemas']['CustomerUpdateRequest'];
export type ApiProductCreateRequest = components['schemas']['ProductCreateRequest'];
export type ApiProductUpdateRequest = components['schemas']['ProductUpdateRequest'];
export type ApiOrderResponse = components['schemas']['OrderResponse'];
export type ApiOrderCreateRequest = components['schemas']['OrderCreateRequest'];
export type ApiTokenResponse = components['schemas']['TokenResponse'];
export type ApiLoginRequest = components['schemas']['LoginRequest'];

export const toApiCustomerCreate = (payload: CustomerCreateRequest): ApiCustomerCreateRequest => ({
  name: payload.name,
  active: payload.active,
} as unknown as ApiCustomerCreateRequest);

export const toApiCustomerUpdate = (payload: CustomerUpdateRequest): ApiCustomerUpdateRequest => ({
  name: payload.name,
  active: payload.active,
});

export const toApiProductCreate = (payload: ProductCreateRequest): ApiProductCreateRequest => ({
  name: payload.name,
  order_uom: payload.orderUom,
  purchase_uom: payload.purchaseUom,
  invoice_uom: payload.invoiceUom,
  is_catch_weight: payload.isCatchWeight,
  weight_capture_required: payload.weightCaptureRequired,
  pricing_basis_default: payload.pricingBasisDefault,
} as unknown as ApiProductCreateRequest);

export const toApiProductUpdate = (payload: ProductUpdateRequest): ApiProductUpdateRequest => ({
  name: payload.name,
  order_uom: payload.orderUom,
  purchase_uom: payload.purchaseUom,
  invoice_uom: payload.invoiceUom,
  is_catch_weight: payload.isCatchWeight,
  weight_capture_required: payload.weightCaptureRequired,
  active: payload.active,
});

export const toApiOrderCreateHeader = (
  customerId: number,
  deliveryDate: string,
  note?: string,
  orderNo?: string,
): ApiOrderCreateRequest => ({
  order_no: orderNo ?? 'AUTO',
  customer_id: customerId,
  delivery_date: deliveryDate,
  note: note ?? null,
});

const resolveCustomerCode = (row: ApiCustomerResponse): string => {
  const dynamic = row as unknown as { code?: string; customer_code?: string };
  return dynamic.code ?? dynamic.customer_code ?? '-';
};

export const toCustomerOption = (row: ApiCustomerResponse): CustomerOption => {
  const customerCode = resolveCustomerCode(row);
  return {
    id: row.id,
    label: `${row.id}: ${row.name} (${customerCode})`,
    customerCode,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
};

export const toCustomerDetail = (row: ApiCustomerResponse): CustomerDetail => ({
  id: row.id,
  customerCode: resolveCustomerCode(row),
  name: row.name,
  active: row.active,
});

export const toProductOption = (row: ApiProductResponse): ProductOption => ({
  id: row.id,
  label: `${row.id}: ${row.name} (${row.pricing_basis_default})`,
  sku: row.sku,
  name: row.name,
  orderUom: row.order_uom,
  pricingBasisDefault: row.pricing_basis_default,
  createdAt: row.created_at,
  updatedAt: row.updated_at,
});

export const toProductDetail = (row: ApiProductResponse): ProductDetail => ({
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
});
