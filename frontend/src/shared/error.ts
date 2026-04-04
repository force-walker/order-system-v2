export class ServiceError extends Error {
  code?: string;
  status?: number;

  constructor(message: string, options?: { code?: string; status?: number }) {
    super(message);
    this.name = 'ServiceError';
    this.code = options?.code;
    this.status = options?.status;
  }
}

type ApiErrorPayload = {
  detail?: {
    code?: string;
    message?: string;
  };
};

const DEFAULT_MESSAGES: Record<string, string> = {
  login_failed: 'ログインに失敗しました。設定を確認してください。',
  list_orders_failed: '注文一覧の取得に失敗しました。',
  create_order_failed: '注文作成に失敗しました。',
  STATUS_NO_TARGET_LINES: '対象データが見つかりませんでした。条件を見直してください。',
  VALIDATION_ERROR: '入力内容に不備があります。必須項目や形式を確認してください。',
  ORDER_CONFLICT: '注文状態の競合が発生しました。最新状態で再度お試しください。',
  CUSTOMER_NOT_FOUND: '指定した顧客が見つかりません。',
  CUSTOMER_CODE_ALREADY_EXISTS: '顧客コードが既に存在します。',
  PRODUCT_NOT_FOUND: '指定した商品が見つかりません。',
  PRODUCT_CODE_ALREADY_EXISTS: '商品コードが既に存在します。',
};

export const parseApiErrorPayload = async (res: Response): Promise<ServiceError> => {
  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await res.json()) as ApiErrorPayload;
  } catch {
    payload = null;
  }

  const code = payload?.detail?.code;
  const detailMessage = payload?.detail?.message;
  const message = detailMessage || (code ? DEFAULT_MESSAGES[code] : undefined) || `APIエラーが発生しました (status: ${res.status})`;

  return new ServiceError(message, { code, status: res.status });
};

export const toUserMessage = (error: unknown, fallback: string): string => {
  if (error instanceof ServiceError) return error.message;

  if (error instanceof Error && error.message) {
    const m = error.message.toLowerCase();
    if (m.includes('failed to fetch') || m.includes('networkerror') || m.includes('network error')) {
      return 'APIへ接続できません。backend起動状態とCORS設定を確認してください。';
    }
    return error.message;
  }

  return fallback;
};
