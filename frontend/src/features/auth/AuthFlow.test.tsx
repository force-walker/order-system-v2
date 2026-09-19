// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { App } from '../../app/App';
import { AUTH_STORAGE_KEY } from 'shared/authSession';

vi.mock('../orders/pages/OrderCreatePage', () => ({ OrderCreatePage: () => <h2>保護された注文画面</h2> }));
const tokens = { access_token: 'test-access', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 3600 };
const fetchMock = vi.fn<typeof fetch>();
let revoked = false;
const user = { user_id: 'alice', role: 'order_entry' };

const HistoryControls = () => {
  const navigate = useNavigate();
  const location = useLocation();
  return <><button onClick={() => navigate(-1)}>戻る操作</button><output data-testid="location">{location.pathname}</output></>;
};
const mount = (entries = ['/orders/new']) => render(
  <MemoryRouter initialEntries={entries}><App /><HistoryControls /></MemoryRouter>,
);

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  revoked = false;
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url) => {
    const path = String(url);
    if (path.endsWith('/auth/register')) return Response.json(user, { status: 201 });
    if (path.endsWith('/auth/login')) return Response.json(tokens);
    if (path.endsWith('/auth/logout')) { revoked = true; return Response.json({ ok: true }); }
    if (path.endsWith('/auth/me')) return revoked ? Response.json({}, { status: 401 }) : Response.json(user);
    throw new Error('Unexpected request: ' + path);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('authentication screens and route protection', () => {
  it('supports root redirect, header identity, logout, reload-equivalent remount and relogin', async () => {
    const actor = userEvent.setup();
    mount(['/']);
    await screen.findByRole('heading', { name: 'ログイン' });
    const enter = async () => {
      await actor.type(screen.getByLabelText('ユーザーID'), 'alice');
      await actor.type(screen.getByLabelText('パスワード'), 'long-password-123');
      await actor.click(screen.getByRole('button', { name: 'ログイン' }));
      await screen.findByText('保護された注文画面');
      expect(screen.getByText('alice').closest('header')).not.toBeNull();
    };
    await enter();
    await actor.click(screen.getByRole('button', { name: 'ログアウト' }));
    await screen.findByRole('heading', { name: 'ログイン' });
    cleanup();
    mount(['/orders/new']);
    await screen.findByRole('heading', { name: 'ログイン' });
    expect(screen.queryByText('保護された注文画面')).toBeNull();
    revoked = false; // Simulate the fresh server session issued by a new login.
    await enter();
  });

  it('redirects an anonymous direct visit to Login without fetching business data', async () => {
    mount(['/orders/new?role=admin&authenticated=true']);
    await screen.findByRole('heading', { name: 'ログイン' });
    expect(screen.getByTestId('location').textContent).toBe('/login');
    expect(screen.queryByText('保護された注文画面')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('registers, returns to Login, and then enters the app using credentials', async () => {
    const actor = userEvent.setup();
    mount(['/login']);
    await actor.click(await screen.findByRole('link', { name: '初めての方：新規登録' }));
    await actor.type(screen.getByLabelText('ユーザーID'), 'alice');
    await actor.type(screen.getByLabelText('パスワード', { exact: true }), 'long-password-123');
    await actor.type(screen.getByLabelText('パスワード（確認）'), 'long-password-123');
    await actor.click(screen.getByRole('button', { name: '登録する' }));
    await screen.findByText('登録しました。ユーザーIDとパスワードでログインしてください。');
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    await actor.type(screen.getByLabelText('ユーザーID'), 'alice');
    await actor.type(screen.getByLabelText('パスワード'), 'long-password-123');
    await actor.click(screen.getByRole('button', { name: 'ログイン' }));
    await screen.findByText('保護された注文画面');
    expect(screen.getByRole('button', { name: 'ログアウト' })).toBeTruthy();
    const request = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/login'));
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ user_id: 'alice', password: 'long-password-123' });
  });

  it('displays wrong-credentials failure without granting access', async () => {
    const actor = userEvent.setup();
    fetchMock.mockResolvedValue(Response.json({ detail: { message: 'incorrect credentials' } }, { status: 401 }));
    mount(['/login']);
    await actor.type(await screen.findByLabelText('ユーザーID'), 'alice');
    await actor.type(screen.getByLabelText('パスワード'), 'wrong');
    await actor.click(screen.getByRole('button', { name: 'ログイン' }));
    expect((await screen.findByRole('alert')).textContent).toContain('incorrect credentials');
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText('保護された注文画面')).toBeNull();
  });

  it('rejects mismatched confirmation locally', async () => {
    const actor = userEvent.setup();
    mount(['/register']);
    await actor.type(await screen.findByLabelText('ユーザーID'), 'alice');
    await actor.type(screen.getByLabelText('パスワード', { exact: true }), 'long-password-123');
    await actor.type(screen.getByLabelText('パスワード（確認）'), 'different-password');
    await actor.click(screen.getByRole('button', { name: '登録する' }));
    expect((await screen.findByRole('alert')).textContent).toContain('一致しません');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('logs out server-side, clears storage, and blocks browser Back', async () => {
    const actor = userEvent.setup();
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
    mount(['/orders/new', '/orders/new']);
    await screen.findByText('保護された注文画面');
    await actor.click(screen.getByRole('button', { name: 'ログアウト' }));
    await screen.findByRole('heading', { name: 'ログイン' });
    expect(revoked).toBe(true);
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    await actor.click(screen.getByRole('button', { name: '戻る操作' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/login'));
    expect(screen.queryByText('保護された注文画面')).toBeNull();
  });

  it('rejects a forged stored session after server validation', async () => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
    revoked = true;
    mount();
    await screen.findByRole('heading', { name: 'ログイン' });
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText('保護された注文画面')).toBeNull();
  });

  it('reflects logout from another tab', async () => {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
    mount();
    await screen.findByText('保護された注文画面');
    act(() => {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.dispatchEvent(new StorageEvent('storage', { key: AUTH_STORAGE_KEY }));
    });
    await screen.findByRole('heading', { name: 'ログイン' });
    expect(screen.queryByText('保護された注文画面')).toBeNull();
  });

  it('clears local state on offline logout and reports revocation uncertainty', async () => {
    const actor = userEvent.setup();
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
    mount();
    await screen.findByText('保護された注文画面');
    fetchMock.mockRejectedValue(new TypeError('offline'));
    await actor.click(screen.getByRole('button', { name: 'ログアウト' }));
    await screen.findByText(/サーバー側の失効を確認できません/);
    expect(localStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText('保護された注文画面')).toBeNull();
  });
});
