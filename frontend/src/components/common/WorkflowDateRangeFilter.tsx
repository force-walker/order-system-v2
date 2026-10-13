import { presetRange, shiftDateRange, workflowDateRangeError, type DateRangePreset, type WorkflowDateRange } from 'shared/workflowDateRange';

export const WorkflowDateRangeFilter = ({ range, onChange, label = '納品日' }: { range: WorkflowDateRange; onChange: (range: WorkflowDateRange) => void; label?: string }) => {
  const selectPreset = (preset: Exclude<DateRangePreset, 'custom'>) => onChange(presetRange(preset));
  const validationError = workflowDateRangeError(range);
  return <div className="workflow-date-range" aria-label={`${label}期間`}>
    <div className="workflow-date-presets">
      <button type="button" className={range.preset === 'today' ? '' : 'secondary'} onClick={() => selectPreset('today')}>今日</button>
      <button type="button" className={range.preset === 'week' ? '' : 'secondary'} onClick={() => selectPreset('week')}>今週</button>
      <button type="button" className={range.preset === 'month' ? '' : 'secondary'} onClick={() => selectPreset('month')}>今月</button>
    </div>
    <label>{label} 開始<input aria-label={`${label} 開始日`} type="date" value={range.from} onChange={(e) => onChange({ from: e.target.value, to: range.to, preset: 'custom' })}/></label>
    <span>～</span>
    <label>{label} 終了<input aria-label={`${label} 終了日`} type="date" value={range.to} onChange={(e) => onChange({ from: range.from, to: e.target.value, preset: 'custom' })}/></label>
    <button type="button" className="secondary" disabled={validationError !== null} onClick={() => onChange(shiftDateRange(range, -1))}>← 前期間</button>
    <button type="button" className="secondary" disabled={validationError !== null} onClick={() => onChange(shiftDateRange(range, 1))}>次期間 →</button>
    {validationError ? <span role="alert" className="field-error">{validationError}</span> : null}
  </div>;
};
