import { apiRequestWithAuth as fetchWithAuth } from 'shared/authenticatedApiClient';
import { parseApiErrorPayload } from 'shared/error';
import type { SystemSettings, UpdateSystemSettingsRequest } from 'features/settings/types/systemSettings';

type ApiSystemSettings = {
  exchange_rate: string | number;
  jp_gross_margin_pct: string | number;
  hk_gross_margin_pct: string | number;
  freight_unit_price: string | number;
  updated_at: string;
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
