import type { EntityId } from 'shared/entityId';

export type SupplierMappingAssignment = {
  orderItemId: EntityId;
  productId: number;
  productName: string;
  supplierId: number;
};

export type SupplierMappingCandidate = {
  productId: number;
  productName: string;
  supplierId: number;
  orderItemIds: EntityId[];
};

export const buildSupplierMappingCandidates = (
  assignments: SupplierMappingAssignment[],
  mappingCountByProduct: Readonly<Record<number, number>>,
): SupplierMappingCandidate[] => {
  const candidates = new Map<string, SupplierMappingCandidate>();

  for (const assignment of assignments) {
    if ((mappingCountByProduct[assignment.productId] ?? 0) > 0) continue;

    const key = `${assignment.productId}:${assignment.supplierId}`;
    const existing = candidates.get(key);
    if (existing) {
      if (!existing.orderItemIds.includes(assignment.orderItemId)) {
        existing.orderItemIds.push(assignment.orderItemId);
      }
      continue;
    }

    candidates.set(key, {
      productId: assignment.productId,
      productName: assignment.productName,
      supplierId: assignment.supplierId,
      orderItemIds: [assignment.orderItemId],
    });
  }

  return [...candidates.values()];
};
