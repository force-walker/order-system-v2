import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { finalizeInvoiceDraft, finalizeInvoiceDraftsBatch, listInvoiceSummaries } from 'features/orders/services/invoiceService';
import type { InvoiceStatus, InvoiceSummaryRow } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  draft: 'draft',
  finalized: 'finalized',
  sent: 'sent',
  cancelled: 'cancelled',
};

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

type RowSelect = Record<number, boolean>;

export const InvoiceDraftPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceSummaryRow[]>([]);
  const [customerFilter, setCustomerFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('');
  const [selectedByInvoiceId, setSelectedByInvoiceId] = useState<RowSelect>({});
  const [finalizingInvoiceId, setFinalizingInvoiceId] = useState<number | null>(null);
  const [bulkFinalizing, setBulkFinalizing] = useState(false);
  const [toast, setToast] = useState<ToastPayload | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const summaries = await listInvoiceSummaries();
      setRows(summaries);
      setSelectedByInvoiceId((prev) => Object.fromEntries(summaries.map((row) => [row.invoiceId, prev[row.invoiceId] ?? false])));
    } catch (e) {
      setError(toActionableMessage(e, '請求ドラフト一覧の取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filtered = useMemo(() => {
    const customerQuery = customerFilter.trim().toLowerCase();
    return rows
      .filter((row) => {
        if (statusFilter && row.status !== statusFilter) return false;
        if (dateFilter && row.deliveryDate !== dateFilter) return false;
        if (customerQuery && !row.customerName.toLowerCase().includes(customerQuery)) return false;
        return true;
      })
      .sort((a, b) => b.invoiceId - a.invoiceId);
  }, [rows, customerFilter, dateFilter, statusFilter]);

  const draftCount = useMemo(() => rows.filter((row) => row.status === 'draft').length, [rows]);
  const finalizedCount = useMemo(() => rows.filter((row) => row.status === 'finalized').length, [rows]);
  const visibleDraftIds = useMemo(() => filtered.filter((row) => row.status === 'draft').map((row) => row.invoiceId), [filtered]);
  const selectedDraftIds = useMemo(
    () => visibleDraftIds.filter((invoiceId) => selectedByInvoiceId[invoiceId]),
    [selectedByInvoiceId, visibleDraftIds],
  );
  const allVisibleDraftsSelected = visibleDraftIds.length > 0 && visibleDraftIds.every((invoiceId) => selectedByInvoiceId[invoiceId]);

  const onToggleAll = (checked: boolean) => {
    setSelectedByInvoiceId((prev) => {
      const next = { ...prev };
      for (const invoiceId of visibleDraftIds) next[invoiceId] = checked;
      return next;
    });
  };

  const onFinalizeSingle = async (invoiceId: number) => {
    setFinalizingInvoiceId(invoiceId);
    setError('');
    try {
      await finalizeInvoiceDraft(invoiceId);
      await load();
      setToast({ type: 'success', message: `請求書 ${invoiceId} を発行しました。` });
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '請求書発行に失敗しました。') });
    } finally {
      setFinalizingInvoiceId(null);
    }
  };

  const onFinalizeBulk = async () => {
    if (selectedDraftIds.length === 0) {
      setToast({ type: 'error', message: '発行対象のドラフトを選択してください。' });
      return;
    }

    setBulkFinalizing(true);
    setError('');
    try {
      const result = await finalizeInvoiceDraftsBatch(selectedDraftIds);
      await load();
      const failed = (result.results ?? []).filter((row) => !row.ok);
      if (failed.length > 0) {
        const failedText = failed.slice(0, 3).map((row) => `#${row.invoice_id}: ${row.reason_code ?? 'FAILED'}`).join(', ');
        setToast({
          type: 'error',
          message: `一括発行は部分成功です。成功 ${result.success_count} / 失敗 ${result.failure_count}${failedText ? ` (${failedText})` : ''}`,
        });
      } else {
        setToast({ type: 'success', message: `${result.success_count}件の請求ドラフトを発行しました。` });
      }
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '請求ドラフトの一括発行に失敗しました。') });
    } finally {
      setBulkFinalizing(false);
    }
  };

  if (error) return <ErrorState title="請求ドラフト一覧の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求ドラフト一覧を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求ドラフト一覧</h2>
            <p className="subtle">発行前後の業務操作をこの画面に集約しています。PDF出力は請求書一覧側の参照機能です。</p>
          </div>
          <div className="list-controls">
            <button type="button" onClick={() => void onFinalizeBulk()} disabled={bulkFinalizing || selectedDraftIds.length === 0}>
              {bulkFinalizing ? '一括発行中...' : `選択した請求ドラフトを発行${selectedDraftIds.length > 0 ? ` (${selectedDraftIds.length})` : ''}`}
            </button>
          </div>
        </div>

        <div className="subtle" style={{ marginBottom: 12 }}>
          draft 件数: {draftCount} / finalized 件数: {finalizedCount}
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            取引先
            <input value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)} placeholder="取引先名で検索" />
          </label>
          <label className="filter-label">
            対象日
            <input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} />
          </label>
          <label className="filter-label">
            ステータス
            <select value={statusFilter} onChange={(e) => setStatusFilter((e.target.value || '') as InvoiceStatus | '')}>
              <option value="">all</option>
              <option value="draft">draft</option>
              <option value="finalized">finalized</option>
              <option value="sent">sent</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="表示中のdraftを全選択"
                    checked={allVisibleDraftsSelected}
                    onChange={(e) => onToggleAll(e.target.checked)}
                    disabled={visibleDraftIds.length === 0}
                  />
                </th>
                <th>請求書番号</th>
                <th>取引先名</th>
                <th>請求日</th>
                <th>対象日</th>
                <th>請求ステータス</th>
                <th style={{ textAlign: 'right' }}>合計金額</th>
                <th style={{ textAlign: 'right' }}>明細件数</th>
                <th>操作</th>
                <th>詳細</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} className="subtle">条件に合う請求データがありません。</td>
                </tr>
              ) : (
                filtered.map((row) => {
                  const isDraft = row.status === 'draft';
                  return (
                    <tr key={row.invoiceId}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`請求書 ${row.invoiceNo} を選択`}
                          checked={Boolean(selectedByInvoiceId[row.invoiceId])}
                          disabled={!isDraft || bulkFinalizing}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setSelectedByInvoiceId((prev) => ({ ...prev, [row.invoiceId]: checked }));
                          }}
                        />
                      </td>
                      <td>{row.invoiceNo}</td>
                      <td>{row.customerName}</td>
                      <td>{row.invoiceDate}</td>
                      <td>{row.deliveryDate}</td>
                      <td>{STATUS_LABEL[row.status]}</td>
                      <td style={{ textAlign: 'right' }}>{currency.format(row.grandTotal)}</td>
                      <td style={{ textAlign: 'right' }}>{row.itemCount}</td>
                      <td>
                        <button
                          type="button"
                          className="secondary"
                          disabled={!isDraft || bulkFinalizing || finalizingInvoiceId === row.invoiceId}
                          onClick={() => void onFinalizeSingle(row.invoiceId)}
                        >
                          {finalizingInvoiceId === row.invoiceId ? '発行中...' : isDraft ? '請求書発行' : '発行済み'}
                        </button>
                      </td>
                      <td><Link to={`/invoices/drafts/${row.invoiceId}`}>詳細</Link></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
