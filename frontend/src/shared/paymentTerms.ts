export const paymentTermsLabel = (type?: string | null, days?: number | null) => {
  if (!type) return '-';
  if (type === 'days_after_issue') return `発行日から${days ?? 0}日後`;
  if (type === 'end_of_issue_month') return '当月末';
  if (type === 'end_of_next_month') return '翌月末';
  if (type === 'end_of_second_month') return '翌々月末';
  if (type === 'half_month_15_eom') return '15日締め・月末/翌15日払い';
  return type;
};
