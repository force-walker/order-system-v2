import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { importProductsUpsert } from 'features/products/services/productsService';
import { ErrorState } from 'components/common/AsyncState';
import { toActionableMessage } from 'shared/error';

type ImportErrorRow = {
  index: number;
  itemRef?: string | null;
  code: string;
  message: string;
};

type ProductImportResult = {
  total: number;
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  errors: ImportErrorRow[];
};

const MAX_ERROR_ROWS = 100;

const SAMPLE_JSON = `[
  {
    "legacy_code": "LEG-100",
    "name": "Imported Product",
    "order_uom": "count",
    "purchase_uom": "count",
    "invoice_uom": "count",
    "pricing_basis_default": "uom_count"
  }
]`;

const normalizeImportPayload = (raw: unknown): { items: Record<string, unknown>[] } => {
  if (Array.isArray(raw)) {
    if (raw.length === 0) throw new Error('空配列は取り込めません。1件以上のデータを指定してください。');
    return { items: raw as Record<string, unknown>[] };
  }

  if (typeof raw === 'object' && raw !== null && 'items' in raw) {
    const items = (raw as { items?: unknown }).items;
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error('items は1件以上の配列で指定してください。');
    }
    return { items: items as Record<string, unknown>[] };
  }

  throw new Error('JSON形式が不正です。配列 または { "items": [...] } 形式で入力してください。');
};

export const ProductImportPage = () => {
  const [jsonText, setJsonText] = useState(SAMPLE_JSON);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [apiError, setApiError] = useState('');
  const [result, setResult] = useState<ProductImportResult | null>(null);

  const visibleErrors = useMemo(() => result?.errors.slice(0, MAX_ERROR_ROWS) ?? [], [result]);

  const onSubmit = async () => {
    setFormError('');
    setApiError('');

    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch {
      setFormError('JSONの解析に失敗しました。構文を確認してください。');
      return;
    }

    let payload: { items: Record<string, unknown>[] };
    try {
      payload = normalizeImportPayload(parsed);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '入力形式が不正です。');
      return;
    }

    setSubmitting(true);
    try {
      const res = await importProductsUpsert(payload);
      setResult(res);
    } catch (e) {
      setApiError(toActionableMessage(e, 'IMPORT実行に失敗しました。'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section>
      <div className="card form-grid">
        <div className="detail-header">
          <div>
            <h2>商品マスタ IMPORT</h2>
            <p className="subtle">POST /api/v1/products/import-upsert を実行します</p>
          </div>
          <Link to="/products" className="order-link">← 商品一覧へ戻る</Link>
        </div>

        <div className="form-grid two-col">
          <label>
            入力方式 A（JSON貼り付け）
            <textarea
              rows={16}
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              placeholder="配列 または { items: [...] } を入力"
            />
          </label>
          <label>
            入力方式 B（CSV / XLSX）
            <input type="file" disabled />
            <span className="subtle">後続対応予定（本PRでは未実装）</span>
          </label>
        </div>

        {formError ? <p className="form-error">{formError}</p> : null}
        <div className="form-actions">
          <button type="button" onClick={onSubmit} disabled={submitting}>{submitting ? 'IMPORT実行中...' : 'IMPORT実行'}</button>
        </div>
      </div>

      {apiError ? <ErrorState title="IMPORTに失敗しました" description={apiError} /> : null}

      {result ? (
        <div className="card form-grid" style={{ marginTop: 12 }}>
          <h3>実行結果</h3>
          <div className="form-grid three-col">
            <div><strong>total:</strong> {result.total}</div>
            <div><strong>created:</strong> {result.created}</div>
            <div><strong>updated:</strong> {result.updated}</div>
            <div><strong>skipped:</strong> {result.skipped}</div>
            <div><strong>failed:</strong> {result.failed}</div>
          </div>

          {visibleErrors.length > 0 ? (
            <div className="table-wrap">
              <h4>エラー行一覧（先頭 {visibleErrors.length} / {result.errors.length} 件）</h4>
              <table>
                <thead>
                  <tr>
                    <th>行</th>
                    <th>itemRef</th>
                    <th>code</th>
                    <th>message</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleErrors.map((row) => (
                    <tr key={`${row.index}-${row.code}-${row.itemRef ?? ''}`}>
                      <td>{row.index + 1}</td>
                      <td>{row.itemRef ?? '-'}</td>
                      <td>{row.code}</td>
                      <td>{row.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.errors.length > MAX_ERROR_ROWS ? (
                <p className="subtle">※ 表示上限は {MAX_ERROR_ROWS} 件です。残りは省略しています。</p>
              ) : null}
            </div>
          ) : (
            <p className="subtle">エラーはありません。</p>
          )}
        </div>
      ) : null}
    </section>
  );
};
