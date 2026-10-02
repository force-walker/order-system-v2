import { describe, expect, it } from 'vitest';
import { toApiProductUpdate } from './ordersDto';

describe('toApiProductUpdate', () => {
  it('includes pricing_basis_default in Product PATCH requests', () => {
    expect(toApiProductUpdate({ pricingBasisDefault: 'uom_kg' })).toMatchObject({
      pricing_basis_default: 'uom_kg',
    });
  });
});
