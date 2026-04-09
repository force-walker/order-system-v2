export class ServiceError extends Error {
  code?: string;
  status?: number;
  detailMessage?: string;

  constructor(message: string, options?: { code?: string; status?: number; detailMessage?: string }) {
    super(message);
    this.name = 'ServiceError';
    this.code = options?.code;
    this.status = options?.status;
    this.detailMessage = options?.detailMessage;
  }
}

type ApiErrorPayload = {
  detail?: {
    code?: string;
    message?: string;
  };
};

const CODE_MESSAGES: Record<string, string> = {
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
  SUPPLIER_NOT_FOUND: '指定した仕入先が見つかりません。',
  SUPPLIER_CODE_ALREADY_EXISTS: '仕入先コードが既に存在します。',
  SUPPLIER_PRODUCT_ALREADY_EXISTS: 'この仕入先と商品の紐づけは既に存在します。',
  SUPPLIER_PRODUCT_NOT_FOUND: '仕入先と商品の紐づけが見つかりません。',
};

const STATUS_MESSAGES: Record<number, string> = {
  404: '対象データが見つかりません。',
  409: 'データ競合が発生しました。内容を確認して再実行してください。',
  422: '入力内容に不備があります。必須項目や形式を確認してください。',
};

const enrichUnknownMessage = (status?: number, code?: string, detailMessage?: string) => {
  const info = [
    status ? `status=${status}` : undefined,
    code ? `code=${code}` : undefined,
    detailMessage ? `message=${detailMessage}` : undefined,
  ].filter(Boolean);

  if (info.length === 0) return '不明な失敗です。';
  return `処理に失敗しました (${info.join(', ')})`;
};

export const parseApiErrorPayload = async (res: Response): Promise<ServiceError> => {
  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await res.json()) as ApiErrorPayload;
  } catch {
    payload = null;
  }

  const status = res.status;
  const code = payload?.detail?.code;
  const detailMessage = payload?.detail?.message;

  const statusMessage = STATUS_MESSAGES[status];
  const codeMessage = code ? CODE_MESSAGES[code] : undefined;

  const message = codeMessage || detailMessage || statusMessage || enrichUnknownMessage(status, code, detailMessage);

  return new ServiceError(message, { code, status, detailMessage });
};

export const isInlineFormError = (error: unknown): boolean => {
  return error instanceof ServiceError && error.status === 422;
};

export const toUserMessage = (error: unknown, fallback: string): string => {
  if (error instanceof ServiceError) {
    if (error.message && error.message.trim()) return error.message;
    return enrichUnknownMessage(error.status, error.code, error.detailMessage);
  }

  if (error instanceof Error && error.message) {
    const m = error.message.toLowerCase();
    if (m.includes('failed to fetch') || m.includes('networkerror') || m.includes('network error')) {
      return 'APIへ接続できません。backend起動状態とCORS設定を確認してください。';
    }
    return error.message;
  }

  return fallback;
};

export const toActionGuidance = (error: unknown): string => {
  if (!(error instanceof ServiceError)) return '時間をおいて再試行してください。';

  if (error.status === 422) {
    return '入力項目（必須・形式・範囲）を見直して再実行してください。';
  }
  if (error.status === 409) {
    return '最新状態を再読み込みして、重複や競合がないか確認してください。';
  }
  if (error.status === 404) {
    return '対象データが削除・無効化されていないか確認し、一覧から選び直してください。';
  }

  return '時間をおいて再試行してください。';
};

export const toActionableMessage = (error: unknown, fallback: string): string => {
  const message = toUserMessage(error, fallback);
  const guidance = toActionGuidance(error);
  return `${message} ${guidance}`.trim();
};
