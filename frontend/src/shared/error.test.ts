import { describe, expect, it } from 'vitest';
import { ServiceError, toActionableMessage, toUserMessage } from './error';

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

  it('adds actionable guidance for 409 conflict', () => {
    const e = new ServiceError('重複です', { status: 409, code: 'SUPPLIER_PRODUCT_ALREADY_EXISTS' });
    expect(toActionableMessage(e, 'fallback')).toContain('最新状態を再読み込み');
  });

  it('adds actionable guidance for 422 validation', () => {
    const e = new ServiceError('入力不備', { status: 422, code: 'VALIDATION_ERROR' });
    expect(toActionableMessage(e, 'fallback')).toContain('入力項目');
  });

  it('adds actionable guidance for 404 not found', () => {
    const e = new ServiceError('見つかりません', { status: 404, code: 'SUPPLIER_NOT_FOUND' });
    expect(toActionableMessage(e, 'fallback')).toContain('一覧から選び直し');
  });
});
