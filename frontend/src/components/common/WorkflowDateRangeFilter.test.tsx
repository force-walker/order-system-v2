// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, expect, it } from 'vitest';
import { WorkflowDateRangeFilter } from './WorkflowDateRangeFilter';
import { useWorkflowDateRange } from 'shared/workflowDateRange';

const Harness = () => {
  const { range, update } = useWorkflowDateRange(); const location = useLocation(); const navigate = useNavigate();
  return <><WorkflowDateRangeFilter range={range} onChange={update}/><button onClick={() => navigate(-1)}>browser back</button><button onClick={() => navigate(1)}>browser forward</button><output>{location.search}</output></>;
};

afterEach(cleanup);

it('restores the URL range and preserves unrelated filters when moving periods', () => {
  render(<MemoryRouter initialEntries={['/?date_from=2026-10-12&date_to=2026-10-18&date_preset=week&supplier=7&status=allocated']}><Harness/></MemoryRouter>);
  expect((screen.getByLabelText('納品日 開始日') as HTMLInputElement).value).toBe('2026-10-12');
  fireEvent.click(screen.getByRole('button', { name: '← 前期間' }));
  expect(screen.getByText(/date_from=2026-10-05/).textContent).toContain('supplier=7');
  expect(screen.getByText(/date_from=2026-10-05/).textContent).toContain('status=allocated');
});

it('selects this month and moves to the previous calendar month', () => {
  render(<MemoryRouter><Harness/></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: '今月' }));
  fireEvent.click(screen.getByRole('button', { name: '← 前期間' }));
  const from = (screen.getByLabelText('納品日 開始日') as HTMLInputElement).value;
  const to = (screen.getByLabelText('納品日 終了日') as HTMLInputElement).value;
  expect(from.endsWith('-01')).toBe(true);
  expect(Number(to.slice(-2))).toBeGreaterThanOrEqual(28);
});

it('pushes user changes so browser back and forward restore prior periods', () => {
  render(<MemoryRouter initialEntries={['/?date_from=2026-10-12&date_to=2026-10-18&date_preset=week']}><Harness/></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: '← 前期間' }));
  fireEvent.click(screen.getByRole('button', { name: '← 前期間' }));
  expect((screen.getByLabelText('納品日 開始日') as HTMLInputElement).value).toBe('2026-09-28');
  fireEvent.click(screen.getByRole('button', { name: 'browser back' }));
  expect((screen.getByLabelText('納品日 開始日') as HTMLInputElement).value).toBe('2026-10-05');
  fireEvent.click(screen.getByRole('button', { name: 'browser forward' }));
  expect((screen.getByLabelText('納品日 開始日') as HTMLInputElement).value).toBe('2026-09-28');
});

it('shows invalid custom ranges and disables period navigation', () => {
  render(<MemoryRouter initialEntries={['/?date_from=2026-10-20&date_to=2026-10-10&date_preset=custom']}><Harness/></MemoryRouter>);
  expect(screen.getByRole('alert').textContent).toContain('開始日は終了日以前にしてください');
  expect((screen.getByRole('button', { name: '← 前期間' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '次期間 →' }) as HTMLButtonElement).disabled).toBe(true);
});
