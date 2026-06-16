export type SystemSettings = {
  exchangeRate: string;
  jpGrossMarginPct: string;
  hkGrossMarginPct: string;
  freightUnitPrice: string;
  updatedAt: string;
};

export type UpdateSystemSettingsRequest = {
  exchangeRate: string;
  jpGrossMarginPct: string;
  hkGrossMarginPct: string;
  freightUnitPrice: string;
};
