export type Supplier = {
  id: number;
  supplierCode: string;
  name: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
  paymentTermsType?: 'days_after_issue' | 'end_of_issue_month' | 'end_of_next_month' | 'end_of_second_month' | 'half_month_15_eom';
  paymentTermsDays?: number;
};

export type SupplierListParams = {
  q?: string;
  active?: 'all' | 'true' | 'false';
  includeInactive?: boolean;
  limit: number;
  offset: number;
};

export type SupplierListResult = {
  items: Supplier[];
  hasNext: boolean;
};

export type SupplierCreateRequest = {
  name: string;
  active: boolean;
  paymentTermsType?: Supplier['paymentTermsType'] | null;
  paymentTermsDays?: number | null;
};

export type SupplierUpdateRequest = {
  name?: string;
  active?: boolean;
  paymentTermsType?: Supplier['paymentTermsType'] | null;
  paymentTermsDays?: number | null;
};

export type SupplierProductMapping = {
  id: number;
  supplierId: number;
  productId: number;
  priority: number;
  isPreferred: boolean;
  defaultUnitCost: number | null;
  leadTimeDays: number | null;
  note: string | null;
  createdAt: string;
  updatedAt: string;
};

export type SupplierProductMappingCreateRequest = {
  productId: number;
  priority: number;
  isPreferred: boolean;
  defaultUnitCost: number | null;
  leadTimeDays: number | null;
  note: string | null;
};

export type SupplierProductMappingCreateGlobalRequest = {
  supplierId: number;
  productId: number;
  priority: number;
  isPreferred: boolean;
  defaultUnitCost: number | null;
  leadTimeDays: number | null;
  note: string | null;
};

export type SupplierProductMappingUpdateRequest = {
  priority?: number;
  isPreferred?: boolean;
  defaultUnitCost?: number | null;
  leadTimeDays?: number | null;
  note?: string | null;
};
