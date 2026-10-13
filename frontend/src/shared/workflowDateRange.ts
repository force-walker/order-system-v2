import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { hongKongDatePreset } from './hongKongDate';

export type DateRangePreset = 'today' | 'week' | 'month' | 'custom';
export type WorkflowDateRange = { from: string; to: string; preset: DateRangePreset };

export const workflowDateRangeError = (range: WorkflowDateRange): string | null => {
  if (!range.from || !range.to) return '開始日と終了日を入力してください';
  if (range.from > range.to) return '開始日は終了日以前にしてください';
  return null;
};

const iso = (date: Date) => date.toISOString().slice(0, 10);
const utcDate = (value: string) => new Date(`${value}T00:00:00Z`);

export const presetRange = (preset: Exclude<DateRangePreset, 'custom'>, now = new Date()): WorkflowDateRange => {
  const kind = preset === 'today' ? 'today' : preset;
  return { ...hongKongDatePreset(kind, now), preset };
};

export const shiftDateRange = (range: WorkflowDateRange, direction: -1 | 1): WorkflowDateRange => {
  if (range.preset === 'month') {
    const base = utcDate(range.from);
    base.setUTCMonth(base.getUTCMonth() + direction, 1);
    const end = new Date(base);
    end.setUTCMonth(end.getUTCMonth() + 1, 0);
    return { from: iso(base), to: iso(end), preset: 'month' };
  }
  const from = utcDate(range.from);
  const to = utcDate(range.to);
  const days = Math.round((to.getTime() - from.getTime()) / 86_400_000) + 1;
  from.setUTCDate(from.getUTCDate() + direction * days);
  to.setUTCDate(to.getUTCDate() + direction * days);
  return { from: iso(from), to: iso(to), preset: range.preset };
};

export const useWorkflowDateRange = (prefix = 'date') => {
  const [params, setParams] = useSearchParams();
  const fromKey = `${prefix}_from`; const toKey = `${prefix}_to`; const presetKey = `${prefix}_preset`;
  const range = useMemo(() => {
    const preset = params.get(presetKey) as DateRangePreset | null;
    const from = params.get(fromKey); const to = params.get(toKey);
    const hasUrlRange = params.has(fromKey) || params.has(toKey) || params.has(presetKey);
    if (hasUrlRange) return {
      from: from ?? '',
      to: to ?? '',
      preset: ['today', 'week', 'month', 'custom'].includes(preset ?? '') ? preset! : 'custom',
    };
    return presetRange('week');
  }, [params.toString(), prefix]);
  const update = (next: WorkflowDateRange) => {
    const copy = new URLSearchParams(params);
    copy.set(fromKey, next.from); copy.set(toKey, next.to); copy.set(presetKey, next.preset);
    setParams(copy);
  };
  const validationError = workflowDateRangeError(range);
  return { range, update, validationError, isValid: validationError === null };
};
