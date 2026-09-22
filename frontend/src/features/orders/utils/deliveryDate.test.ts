import { describe, expect, it } from 'vitest';
import { getDefaultDeliveryDate } from './deliveryDate';

describe('getDefaultDeliveryDate', () => {
  it('uses the same business day before 13:00', () => {
    expect(getDefaultDeliveryDate(new Date('2026-04-14T12:59:00+08:00'))).toBe('2026-04-14');
  });

  it('uses the next business day at 13:00 and skips Wednesday', () => {
    expect(getDefaultDeliveryDate(new Date('2026-04-14T13:00:00+08:00'))).toBe('2026-04-16');
  });

  it('advances from a closed Wednesday even before 13:00', () => {
    expect(getDefaultDeliveryDate(new Date('2026-04-15T08:00:00+08:00'))).toBe('2026-04-16');
  });

  it('skips Sunday after the Saturday cutoff', () => {
    expect(getDefaultDeliveryDate(new Date('2026-04-18T13:00:00+08:00'))).toBe('2026-04-20');
  });
});
