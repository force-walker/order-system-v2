import { describe, expect, it } from 'vitest';
import { ServiceError, toUserMessage } from './error';

describe('toUserMessage', () => {
  it('returns service error message', () => {
    const e = new ServiceError('注文一覧の取得に失敗しました', { code: 'list_orders_failed', status: 500 });
    expect(toUserMessage(e, 'fallback')).toBe('注文一覧の取得に失敗しました');
  });

  it('returns fallback for unknown error', () => {
    expect(toUserMessage(null, 'fallback')).toBe('fallback');
  });
});
