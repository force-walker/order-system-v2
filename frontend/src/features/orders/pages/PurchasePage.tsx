import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { createPurchaseResult, listPurchaseResults } from 'features/orders/services/purchaseService';
import type { PurchaseResultCreateRequest, PurchaseResultFilter, PurchaseResultItem, PurchaseResultStatus } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

const STATUS_OPTIONS: Array<{ value: PurchaseResultStatus; label: string }> = [
  { value: 'not_filled', label: '未充足' },
  { value: 'filled', label: '充足' },
  { value: 'partially_filled', label: '一部充足' },
  { value: 'substituted', label: '代替' },
];

type CreateForm = {
  allocationId: string;
  supplierId: string;
  purchasedQty: string;
  purchasedUom: string;
  resultStatus: PurchaseResultStatus;
  note: string;
};

const initialForm: CreateForm = {
  allocationId: '',
  supplierId: '',
  purchasedQty: '',
  purchasedUom: 'kg',
  resultStatus: 'filled',
  note: '',
};

export const PurchasePage = () => {
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<PurchaseResultItem[] | null>(null);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<CreateForm>(initialForm);

  const [searchAllocationId, setSearchAllocationId] = useState('');
  const [searchSupplierId, setSearchSupplierId] = useState('');
  const [searchKeyword, setSearchKeyword] = useState('');

  const load = async (filter: PurchaseResultFilter = {}) => {
    setLoading(true);
    setError('');
    try {
      const result = await listPurchaseResults(filter);
      setRows(result.items);
    } catch (e) {
      setError(toUserMessage(e, '発注結果の取得に失敗しました'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filteredRows = useMemo(() => {
    if (!rows) return [];
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) return rows;

    return rows.filter((row) => {
      const target = `${row.id} ${row.allocationId} ${row.resultStatus} ${row.note ?? ''}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [rows, searchKeyword]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    const filter: PurchaseResultFilter = {
      allocationId: searchAllocationId ? Number(searchAllocationId) : undefined,
      supplierId: searchSupplierId ? Number(searchSupplierId) : undefined,
      limit: 100,
      offset: 0,
    };
    await load(filter);
  };

  const validateForm = (): string => {
    if (!form.allocationId || Number(form.allocationId) <= 0) return 'allocation_id は 1 以上で入力してください';
    if (!form.purchasedQty || Number(form.purchasedQty) <= 0) return '購入数量は 0 より大きい値で入力してください';
    if (!form.purchasedUom.trim()) return '購入単位は必須です';
    return '';
  };

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    const err = validateForm();
    if (err) {
      setFormError(err);
      return;
    }

    setFormError('');
    setSubmitting(true);

    try {
      const payload: PurchaseResultCreateRequest = {
        allocationId: Number(form.allocationId),
        supplierId: form.supplierId ? Number(form.supplierId) : undefined,
        purchasedQty: Number(form.purchasedQty),
        purchasedUom: form.purchasedUom.trim(),
        resultStatus: form.resultStatus,
        invoiceableFlag: true,
        note: form.note.trim() || undefined,
      };

      await createPurchaseResult(payload);
      setForm(initialForm);
      await load();
    } catch (e) {
      setFormError(toUserMessage(e, '発注結果の作成に失敗しました'));
    } finally {
      setSubmitting(false);
    }
  };

  if (error) return <ErrorState title="発注結果の取得に失敗しました" description={error} actionLabel="再試行" onAction={() => load()} />;
  if (loading || !rows) return <LoadingState title="発注結果を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      <div className="card" style={{ marginBottom: 12 }}>
        <h2>発注作成 / 確認</h2>
        <p className="subtle">発注結果（purchase-results）の登録と確認を行います。</p>

        <form onSubmit={onCreate} className="form-grid two-col" style={{ marginTop: 12 }}>
          <label>
            allocation_id *
            <input type="number" min={1} value={form.allocationId} onChange={(e) => setForm((p) => ({ ...p, allocationId: e.target.value }))} />
          </label>

          <label>
            supplier_id
            <input type="number" min={1} value={form.supplierId} onChange={(e) => setForm((p) => ({ ...p, supplierId: e.target.value }))} />
          </label>

          <label>
            購入数量 *
            <input type="number" min={0.001} step="0.001" value={form.purchasedQty} onChange={(e) => setForm((p) => ({ ...p, purchasedQty: e.target.value }))} />
          </label>

          <label>
            購入単位 *
            <input value={form.purchasedUom} onChange={(e) => setForm((p) => ({ ...p, purchasedUom: e.target.value }))} />
          </label>

          <label>
            結果ステータス
            <select value={form.resultStatus} onChange={(e) => setForm((p) => ({ ...p, resultStatus: e.target.value as PurchaseResultStatus }))}>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>

          <label>
            備考
            <input value={form.note} onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))} />
          </label>

          <div className="form-actions" style={{ gridColumn: '1 / -1' }}>
            <button type="submit" disabled={submitting}>{submitting ? '登録中...' : '発注結果を登録'}</button>
          </div>
          {formError ? <p className="form-error" style={{ gridColumn: '1 / -1' }}>{formError}</p> : null}
        </form>
      </div>

      <div className="card">
        <div className="list-header">
          <div>
            <h2>purchase-results 一覧</h2>
            <p className="subtle">API検索 + 画面キーワード絞り込み</p>
          </div>
        </div>

        <form onSubmit={onSearch} className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            allocation_id
            <input type="number" min={1} value={searchAllocationId} onChange={(e) => setSearchAllocationId(e.target.value)} placeholder="例: 10" />
          </label>

          <label className="filter-label">
            supplier_id
            <input type="number" min={1} value={searchSupplierId} onChange={(e) => setSearchSupplierId(e.target.value)} placeholder="例: 3" />
          </label>

          <label className="filter-label">
            キーワード
            <input value={searchKeyword} onChange={(e) => setSearchKeyword(e.target.value)} placeholder="id / status / note" />
          </label>

          <button type="submit">検索</button>
          <button type="button" className="secondary" onClick={() => { setSearchAllocationId(''); setSearchSupplierId(''); setSearchKeyword(''); load(); }}>条件クリア</button>
        </form>

        {filteredRows.length === 0 ? (
          <EmptyState
            title="データがありません"
            description="条件に合う発注結果がありません。検索条件を見直してください。"
            actionLabel="再読み込み"
            onAction={() => load()}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>allocation_id</th>
                  <th>supplier_id</th>
                  <th>数量</th>
                  <th>単位</th>
                  <th>ステータス</th>
                  <th>recorded_at</th>
                  <th>備考</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.allocationId}</td>
                    <td>{row.supplierId ?? '-'}</td>
                    <td>{row.purchasedQty}</td>
                    <td>{row.purchasedUom}</td>
                    <td>{row.resultStatus}</td>
                    <td>{new Date(row.recordedAt).toLocaleString('ja-JP')}</td>
                    <td>{row.note ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
