import { expect, it } from 'vitest';
import { hongKongDatePreset } from './hongKongDate';

it('uses the Hong Kong calendar date across a UTC boundary', () => {
  expect(hongKongDatePreset('today', new Date('2026-10-05T16:30:00Z'))).toEqual({ from: '2026-10-06', to: '2026-10-06' });
});
it('starts weeks on Monday in Hong Kong', () => {
  expect(hongKongDatePreset('week', new Date('2026-10-07T02:00:00Z'))).toEqual({ from: '2026-10-05', to: '2026-10-11' });
});
