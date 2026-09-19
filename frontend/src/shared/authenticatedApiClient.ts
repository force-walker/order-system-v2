import { apiRequest } from './apiClient';
import { clearSession, readSession } from './authSession';
import { ServiceError } from './error';

export const apiRequestWithAuth = async (path: string, init?: { method?: string; body?: unknown }): Promise<Response> => {
  const token = readSession()?.access_token;
  if (!token) throw new ServiceError('ログインしてください。', { code: 'AUTH_REQUIRED', status: 401 });
  const response = await apiRequest(path, { method: init?.method, body: init?.body, authToken: token });
  if (response.status === 401 && readSession()?.access_token === token) clearSession();
  // A response started under a previous account must never populate its replacement's cache.
  if (response.ok && readSession()?.access_token !== token) {
    throw new ServiceError('認証状態が変更されました。', { code: 'AUTH_REQUIRED', status: 401 });
  }
  return response;
};
