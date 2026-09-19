import { apiJson, apiRequest } from './apiClient';
import { parseApiErrorPayload } from './error';
import type { components } from '../generated/openapi';

export const AUTH_STORAGE_KEY = 'osv2_auth_session';
export const AUTH_CHANGED = 'osv2-auth-changed';
export type AuthUser = components['schemas']['MeResponse'];
export type AuthTokens = components['schemas']['TokenResponse'];

export const readSession = (): AuthTokens | null => {
  try {
    const value = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) ?? 'null') as AuthTokens | null;
    return value && typeof value.access_token === 'string' && typeof value.refresh_token === 'string' ? value : null;
  } catch {
    return null;
  }
};

const notify = () => window.dispatchEvent(new Event(AUTH_CHANGED));

export const clearSession = () => {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem('osv2_access_token');
  localStorage.removeItem('osv2_refresh_token');
  notify();
};

export const currentUser = (token = readSession()?.access_token): Promise<AuthUser> =>
  apiJson<AuthUser>('/api/v1/auth/me', { authToken: token });

export const signIn = async (user_id: string, password: string) => {
  const tokens = await apiJson<AuthTokens>('/api/v1/auth/login', { method: 'POST', body: { user_id, password } });
  // Verify against the server before declaring a stored token authenticated.
  await currentUser(tokens.access_token);
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokens));
  localStorage.removeItem('osv2_access_token');
  notify();
};

export const registerUser = (user_id: string, password: string) =>
  apiJson<AuthUser>('/api/v1/auth/register', { method: 'POST', body: { user_id, password } });

export const signOut = async (): Promise<void> => {
  const session = readSession();
  // Lock every local route immediately, even when the network is unavailable.
  clearSession();
  if (!session) return;
  const response = await apiRequest('/api/v1/auth/logout', {
    method: 'POST', body: { refresh_token: session.refresh_token },
  });
  if (!response.ok && response.status !== 401) throw await parseApiErrorPayload(response);
};
