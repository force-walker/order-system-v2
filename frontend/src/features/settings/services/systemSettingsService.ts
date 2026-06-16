import { apiRequest } from 'shared/apiClient';
import { parseApiErrorPayload } from 'shared/error';
import type { SystemSettings, UpdateSystemSettingsRequest } from 'features/settings/types/systemSettings';

type ApiLoginRequest = { user_id: string; role: string };
type ApiTokenResponse = { access_token: string; refresh_token: string };

type ApiSystemSettings = {
  exchange_rate: string | number;
  jp_gross_margin_pct: string | number;
  hk_gross_margin_pct: string | number;
  freight_unit_price: string | number;
  updated_at: string;
};

const TOKEN_STORAGE_KEY = 'osv2_access_token';
const DEV_LOGIN_USER = import.meta.env.VITE_DEV_LOGIN_USER ?? 'frontend-dev-admin';
const DEV_LOGIN_ROLE = import.meta.env.VITE_DEV_LOGIN_ROLE ?? 'admin';

const ensureDevToken = async (): Promise<string> => {
  const cached = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (cached) return cached;

  const loginBody: ApiLoginRequest = { user_id: DEV_LOGIN_USER, role: DEV_LOGIN_ROLE };
  const res = await apiRequest('/api/v1/auth/login', {
    method: 'POST',
    body: loginBody,
  });
  if (!res.ok) throw await parseApiErrorPayload(res);

  const data = (await res.json()) as ApiTokenResponse;
  localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token);
  return data.access_token;
};

const fetchWithAuth = async (path: string, init?: { method?: string; body?: unknown }) => {
  const token = await ensureDevToken();
  const res = await apiRequest(path, {
    method: init?.method ?? 'GET',
    body: init?.body,
    authToken: token,
  });
  if (res.status === 401) localStorage.removeItem(TOKEN_STORAGE_KEY);
  return res;
};

const toSystemSettings = (row: ApiSystemSettings): SystemSettings => ({
  exchangeRate: String(row.exchange_rate),
  jpGrossMarginPct: String(row.jp_gross_margin_pct),
  hkGrossMarginPct: String(row.hk_gross_margin_pct),
  freightUnitPrice: String(row.freight_unit_price),
  updatedAt: row.updated_at,
});

export const getSystemSettings = async (): Promise<SystemSettings> => {
  const res = await fetchWithAuth('/api/v1/system-settings');
  if (!res.ok) throw await parseApiErrorPayload(res);
  return toSystemSettings((await res.json()) as ApiSystemSettings);
};

export const updateSystemSettings = async (payload: UpdateSystemSettingsRequest): Promise<SystemSettings> => {
  const res = await fetchWithAuth('/api/v1/system-settings', {
    method: 'PUT',
    body: {
      exchange_rate: payload.exchangeRate,
      jp_gross_margin_pct: payload.jpGrossMarginPct,
      hk_gross_margin_pct: payload.hkGrossMarginPct,
      freight_unit_price: payload.freightUnitPrice,
    },
  });
  if (!res.ok) throw await parseApiErrorPayload(res);
  return toSystemSettings((await res.json()) as ApiSystemSettings);
};
