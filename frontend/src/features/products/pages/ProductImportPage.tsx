import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import * as XLSX from 'xlsx';
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

const parseCsvLine = (line: string): string[] => {
  const cells: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];

    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === ',' && !inQuotes) {
      cells.push(current.trim());
      current = '';
      continue;
    }

    current += ch;
  }

  cells.push(current.trim());
  return cells;
};

const csvToItems = (text: string): Record<string, unknown>[] => {
  const lines = text
    .split(/\r?\n/)
    .map((row) => row.trim())
    .filter((row) => row.length > 0);

  if (lines.length < 2) {
    throw new Error('CSVはヘッダ行＋データ1行以上が必要です。');
  }

  const headers = parseCsvLine(lines[0]).map((h) => h.trim());
  if (headers.some((h) => !h)) {
    throw new Error('CSVヘッダに空列があります。');
  }

  const items: Record<string, unknown>[] = [];
  for (let i = 1; i < lines.length; i += 1) {
    const values = parseCsvLine(lines[i]);
    const row: Record<string, unknown> = {};
    headers.forEach((key, idx) => {
      const raw = values[idx] ?? '';
      row[key] = raw;
    });
    items.push(row);
  }

  return items;
};

const xlsxToItems = async (file: File): Promise<Record<string, unknown>[]> => {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });
  const first = workbook.SheetNames[0];
  if (!first) throw new Error('XLSXのシートが見つかりません。');

  const sheet = workbook.Sheets[first];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
    defval: '',
    raw: false,
  });

  if (!Array.isArray(rows) || rows.length === 0) {
    throw new Error('XLSXに取り込み対象データがありません。');
  }

  return rows;
};

export const ProductImportPage = () => {
  const [jsonText, setJsonText] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [apiError, setApiError] = useState('');
  const [result, setResult] = useState<ProductImportResult | null>(null);

  const visibleErrors = useMemo(() => result?.errors.slice(0, MAX_ERROR_ROWS) ?? [], [result]);

  const onSubmit = async () => {
    setFormError('');
    setApiError('');

    if (!jsonText.trim()) {
      setFormError('入力データが空です。JSON貼り付けまたはCSV/XLSX読込を行ってください。');
      return;
    }

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

  const onSelectFile = async (file: File | null) => {
    setFormError('');
    if (!file) return;

    const lower = file.name.toLowerCase();
    setSelectedFileName(file.name);

    try {
      let items: Record<string, unknown>[] = [];
      if (lower.endsWith('.csv')) {
        const text = await file.text();
        items = csvToItems(text);
      } else if (lower.endsWith('.xlsx')) {
        items = await xlsxToItems(file);
      } else {
        throw new Error('対応形式は .csv / .xlsx のみです。');
      }

      setJsonText(JSON.stringify({ items }, null, 2));
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'ファイル読込に失敗しました。');
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
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                void onSelectFile(file);
              }}
            />
            {selectedFileName ? <span className="subtle">選択中: {selectedFileName}</span> : <span className="subtle">CSV/XLSXを選択するとJSON欄へ変換反映します</span>}
          </label>
        </div>

        <details>
          <summary className="subtle">JSONサンプルを表示</summary>
          <pre>{SAMPLE_JSON}</pre>
        </details>

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
