export type Supplier = {
  id: number;
  supplierCode: string;
  name: string;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type SupplierListParams = {
  q?: string;
  active?: 'all' | 'true' | 'false';
  limit: number;
  offset: number;
};

export type SupplierListResult = {
  items: Supplier[];
  hasNext: boolean;
};
