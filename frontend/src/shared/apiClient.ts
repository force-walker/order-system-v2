import { ServiceError, parseApiErrorPayload } from 'shared/error';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? '15000');

type RequestOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: unknown;
  authToken?: string;
};

export const apiRequest = async (path: string, options?: RequestOptions): Promise<Response> => {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const headers: Record<string, string> = {
      ...(options?.headers ?? {}),
    };

    let body: BodyInit | undefined;
    if (options?.body !== undefined) {
      headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
      body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    if (options?.authToken) {
      headers.Authorization = `Bearer ${options.authToken}`;
    }

    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: options?.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    });

    return res;
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ServiceError('APIリクエストがタイムアウトしました。', { code: 'API_TIMEOUT' });
    }
    throw e;
  } finally {
    window.clearTimeout(timeout);
  }
};

export const apiJson = async <T>(path: string, options?: RequestOptions): Promise<T> => {
  const res = await apiRequest(path, options);
  if (!res.ok) throw await parseApiErrorPayload(res);
  return (await res.json()) as T;
};
