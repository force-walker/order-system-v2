import { describe, expect, it } from 'vitest';
import { ServiceError, toUserMessage } from './error';

describe('toUserMessage', () => {
  it('returns service error message', () => {
    const e = new ServiceError('注文一覧の取得に失敗しました', { code: 'list_orders_failed', status: 500 });
    expect(toUserMessage(e, 'fallback')).toBe('注文一覧の取得に失敗しました');
  });

  it('includes status/code/message for unknown service failure', () => {
    const e = new ServiceError('', { code: 'UNKNOWN_CODE', status: 500, detailMessage: 'boom' });
    expect(toUserMessage(e, 'fallback')).toBe('処理に失敗しました (status=500, code=UNKNOWN_CODE, message=boom)');
  });

  it('returns fallback for unknown error', () => {
    expect(toUserMessage(null, 'fallback')).toBe('fallback');
  });
});
