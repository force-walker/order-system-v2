import { expect, it } from 'vitest';
import { presetRange, shiftDateRange, workflowDateRangeError } from './workflowDateRange';

const now = new Date('2026-10-13T04:00:00Z');

it('builds Hong Kong today, Monday-Sunday week, and calendar month presets', () => {
  expect(presetRange('today', now)).toMatchObject({ from: '2026-10-13', to: '2026-10-13' });
  expect(presetRange('week', now)).toMatchObject({ from: '2026-10-12', to: '2026-10-18' });
  expect(presetRange('month', now)).toMatchObject({ from: '2026-10-01', to: '2026-10-31' });
});

it('moves daily and weekly ranges by the same inclusive duration', () => {
  expect(shiftDateRange(presetRange('today', now), -1)).toMatchObject({ from: '2026-10-12', to: '2026-10-12' });
  expect(shiftDateRange(presetRange('week', now), -1)).toMatchObject({ from: '2026-10-05', to: '2026-10-11' });
  expect(shiftDateRange(presetRange('week', now), 1)).toMatchObject({ from: '2026-10-19', to: '2026-10-25' });
});

it('moves months by calendar month across leap years and year boundaries', () => {
  expect(shiftDateRange({ from: '2028-03-01', to: '2028-03-31', preset: 'month' }, -1)).toMatchObject({ from: '2028-02-01', to: '2028-02-29' });
  expect(shiftDateRange({ from: '2026-12-01', to: '2026-12-31', preset: 'month' }, 1)).toMatchObject({ from: '2027-01-01', to: '2027-01-31' });
});

it('moves a custom range by its inclusive length', () => {
  const range = { from: '2026-10-01', to: '2026-10-10', preset: 'custom' as const };
  expect(shiftDateRange(range, -1)).toMatchObject({ from: '2026-09-21', to: '2026-09-30' });
  expect(shiftDateRange(range, 1)).toMatchObject({ from: '2026-10-11', to: '2026-10-20' });
});

it('rejects incomplete and reversed custom ranges', () => {
  expect(workflowDateRangeError({ from: '', to: '2026-10-10', preset: 'custom' })).toBeTruthy();
  expect(workflowDateRangeError({ from: '2026-10-20', to: '2026-10-10', preset: 'custom' })).toBe('開始日は終了日以前にしてください');
});
