import { describe, expect, it } from 'vitest';
import { buildSupplierMappingCandidates } from './supplierMappingCandidates';

describe('buildSupplierMappingCandidates', () => {
  it('deduplicates the same product and supplier across order items', () => {
    expect(buildSupplierMappingCandidates([
      { orderItemId: 'item-a', productId: 10, productName: 'Product A', supplierId: 20 },
      { orderItemId: 'item-b', productId: 10, productName: 'Product A', supplierId: 20 },
    ], { 10: 0 })).toEqual([{
      productId: 10,
      productName: 'Product A',
      supplierId: 20,
      orderItemIds: ['item-a', 'item-b'],
    }]);
  });

  it('keeps separate supplier pairs for a split-style assignment', () => {
    expect(buildSupplierMappingCandidates([
      { orderItemId: 'item-a', productId: 10, productName: 'Product A', supplierId: 20 },
      { orderItemId: 'item-a', productId: 10, productName: 'Product A', supplierId: 30 },
    ], { 10: 0 })).toEqual([
      { productId: 10, productName: 'Product A', supplierId: 20, orderItemIds: ['item-a'] },
      { productId: 10, productName: 'Product A', supplierId: 30, orderItemIds: ['item-a'] },
    ]);
  });

  it('does not offer mappings when a product already has any mapping', () => {
    expect(buildSupplierMappingCandidates([
      { orderItemId: 'item-a', productId: 10, productName: 'Product A', supplierId: 30 },
    ], { 10: 1 })).toEqual([]);
  });
});
