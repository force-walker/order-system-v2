const parts = (now: Date) => Object.fromEntries(new Intl.DateTimeFormat('en-US', {
  timeZone: 'Asia/Hong_Kong', year: 'numeric', month: '2-digit', day: '2-digit',
}).formatToParts(now).filter(p => p.type !== 'literal').map(p => [p.type, Number(p.value)]));
const isoUtc = (d: Date) => d.toISOString().slice(0, 10);

export const hongKongDatePreset = (kind: 'today'|'week'|'month'|'year', now = new Date()) => {
  const p = parts(now); const current = new Date(Date.UTC(p.year, p.month - 1, p.day));
  const start = new Date(current); const end = new Date(current);
  if (kind === 'week') { const day = (current.getUTCDay() + 6) % 7; start.setUTCDate(current.getUTCDate() - day); end.setUTCDate(start.getUTCDate() + 6); }
  if (kind === 'month') { start.setUTCDate(1); end.setUTCMonth(current.getUTCMonth() + 1, 0); }
  if (kind === 'year') { start.setUTCMonth(0, 1); end.setUTCMonth(11, 31); }
  return { from: isoUtc(start), to: isoUtc(end) };
};
