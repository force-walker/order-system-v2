// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { CustomerListPage } from './CustomerListPage';
import { listCustomers } from '../services/customersService';

vi.mock('../services/customersService', () => ({ listCustomers: vi.fn(), archiveCustomer: vi.fn(), unarchiveCustomer: vi.fn(), deleteCustomer: vi.fn() }));
beforeEach(() => vi.mocked(listCustomers).mockResolvedValue([
  { id: 2, label: 'Zulu', customerCode: 'C-2', active: true },
  { id: 1, label: 'Alpha', customerCode: 'C-1', active: true },
]));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('supports visible-row selection and ascending/descending column sorting', async () => {
  const actor = userEvent.setup();
  render(<MemoryRouter><CustomerListPage /></MemoryRouter>);
  await screen.findByText('Zulu');
  await actor.click(screen.getByRole('checkbox', { name: '表示中の顧客をすべて選択' }));
  expect((screen.getByRole('checkbox', { name: 'Alphaを選択' }) as HTMLInputElement).checked).toBe(true);
  await actor.click(screen.getByRole('button', { name: '表示名' }));
  expect(screen.getAllByRole('row')[1].textContent).toContain('Alpha');
  await actor.click(screen.getByRole('button', { name: '表示名 ▲' }));
  expect(screen.getAllByRole('row')[1].textContent).toContain('Zulu');
  await actor.click(screen.getByRole('button', { name: '表示名 ▼' }));
  expect(screen.getAllByRole('row')[1].textContent).toContain('Alpha');
});
