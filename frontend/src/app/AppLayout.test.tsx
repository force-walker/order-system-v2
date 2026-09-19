// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppLayout } from './AppLayout';

vi.mock('features/auth/AuthContext', () => ({ useAuth: () => ({ user: null }) }));
vi.mock('features/auth/LogoutButton', () => ({ LogoutButton: () => null }));
afterEach(cleanup);

const cases = [
  ['/orders/new', '注文作成'], ['/orders', '注文一覧'],
  ['/orders/item-allocations', '一括割当'],
  ['/orders/uuid/edit', '注文一覧'], ['/orders/uuid/items/item-uuid', '注文一覧'],
  ['/reports/shipping', '帳票'], ['/purchases', '納品確認'],
  ['/invoices/drafts', '請求ドラフト'], ['/invoices/drafts/uuid', '請求ドラフト'],
  ['/invoices', '請求書'], ['/invoices/uuid', '請求書'],
  ...['products', 'customers', 'suppliers'].flatMap((section, index) =>
    ['', '/new', '/import', '/123', '/123/edit'].map(suffix =>
      ['/' + section + suffix, ['商品', '顧客', '仕入先'][index]])),
  ['/settings/system', '環境設定'], ['/orders/new/?x=1#top', '注文作成'],
];

function expectSelected(label: string) {
  const active = document.querySelectorAll('.nav-link.active');
  expect(active).toHaveLength(1);
  expect(active[0].textContent).toBe(label);
  expect(document.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(active[0].getAttribute('aria-current')).toBe('page');
}

describe('navigation selection', () => {
  it.each(cases)('%s selects only %s', (path, label) => {
    render(<MemoryRouter initialEntries={[path]}><AppLayout /></MemoryRouter>);
    expectSelected(label);
  });

  it('updates selection when moving between overlapping sections', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={['/orders/new']}><AppLayout /></MemoryRouter>);
    for (const label of ['注文一覧', '一括割当', '注文作成', '請求ドラフト', '請求書']) {
      await user.click(screen.getByRole('link', { name: label }));
      expectSelected(label);
    }
  });

  it('does not match a partial path segment', () => {
    render(<MemoryRouter initialEntries={['/orders-other']}><AppLayout /></MemoryRouter>);
    expect(document.querySelectorAll('.nav-link.active')).toHaveLength(0);
  });
});
