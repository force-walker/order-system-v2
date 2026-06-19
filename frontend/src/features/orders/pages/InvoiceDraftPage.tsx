import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  finalizeInvoiceDraftsBatch,
  listInvoiceDraftListRows,
  updateInvoiceDraftItem,
} from 'features/orders/services/invoiceService';
import type { InvoiceDraftListRow, InvoiceStatus } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });
const numberFormatter = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 2 });
const percentFormatter = new Intl.NumberFormat('ja-JP', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

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
type PriceInputMap = Record<number, string>;
type SavingMap = Record<number, boolean>;

const formatNumber = (value: number | undefined) => {
  if (value === undefined) return '-';
  return numberFormatter.format(value);
};

const formatGrossMargin = (row: Pick<InvoiceDraftListRow, 'grossMarginPct' | 'grossMarginUnavailable'>) => {
  if (row.grossMarginUnavailable || row.grossMarginPct === undefined) return '-';
  return `${percentFormatter.format(row.grossMarginPct)}%`;
};

export const InvoiceDraftPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftListRow[]>([]);
  const [customerFilter, setCustomerFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('draft');
  const [selectedByInvoiceId, setSelectedByInvoiceId] = useState<RowSelect>({});
  const [priceInputs, setPriceInputs] = useState<PriceInputMap>({});
  const [savingByItemId, setSavingByItemId] = useState<SavingMap>({});
  const [bulkFinalizing, setBulkFinalizing] = useState(false);
  const [toast, setToast] = useState<ToastPayload | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const nextRows = await listInvoiceDraftListRows();
      setRows(nextRows);
      setSelectedByInvoiceId((prev) =>
        Object.fromEntries([...new Set(nextRows.map((row) => row.invoiceId))].map((invoiceId) => [invoiceId, prev[invoiceId] ?? false])),
      );
      setPriceInputs(Object.fromEntries(nextRows.map((row) => [row.invoiceItemId, String(row.salesUnitPrice)])));
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
      .sort((a, b) => (a.invoiceId === b.invoiceId ? a.invoiceItemId - b.invoiceItemId : b.invoiceId - a.invoiceId));
  }, [rows, customerFilter, dateFilter, statusFilter]);

  const draftInvoiceIds = useMemo(() => [...new Set(rows.filter((row) => row.status === 'draft').map((row) => row.invoiceId))], [rows]);
  const finalizedInvoiceIds = useMemo(
    () => [...new Set(rows.filter((row) => row.status === 'finalized').map((row) => row.invoiceId))],
    [rows],
  );
  const visibleDraftIds = useMemo(
    () => [...new Set(filtered.filter((row) => row.status === 'draft').map((row) => row.invoiceId))],
    [filtered],
  );
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
        const failedText = failed
          .slice(0, 3)
          .map((row) => `#${row.invoice_id}: ${row.reason_code ?? 'FAILED'}`)
          .join(', ');
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

  const commitSalesUnitPrice = async (row: InvoiceDraftListRow) => {
    const rawValue = priceInputs[row.invoiceItemId]?.trim() ?? '';
    if (rawValue.length === 0) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    const nextValue = Number(rawValue);
    if (!Number.isFinite(nextValue) || nextValue < 0) {
      setToast({ type: 'error', message: '請求単価には 0 以上の数値を入力してください。' });
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    if (nextValue === row.salesUnitPrice) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    setSavingByItemId((prev) => ({ ...prev, [row.invoiceItemId]: true }));
    setError('');
    try {
      const updated = await updateInvoiceDraftItem(row.invoiceId, row.invoiceItemId, {
        billableQty: row.billableQty,
        salesUnitPrice: nextValue,
      });
      setRows((prev) =>
        prev.map((current) =>
          current.invoiceItemId === row.invoiceItemId
            ? {
                ...current,
                billableQty: updated.billableQty,
                billableUom: updated.billableUom,
                salesUnitPrice: updated.salesUnitPrice,
                unitCostBasis: updated.unitCostBasis,
                autoPriceError: updated.autoPriceError,
                lineAmount: updated.lineAmount,
                grossMarginPct: updated.grossMarginPct,
                grossMarginUnavailable: updated.grossMarginUnavailable,
              }
            : current,
        ),
      );
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(updated.salesUnitPrice) }));
      setToast({ type: 'success', message: `請求単価を更新しました: ${row.invoiceNo}` });
    } catch (e) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      setToast({ type: 'error', message: toActionableMessage(e, '請求単価の更新に失敗しました。') });
    } finally {
      setSavingByItemId((prev) => ({ ...prev, [row.invoiceItemId]: false }));
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
            <p className="subtle">請求明細行を一覧で確認し、請求単価の調整と請求書発行を行います。</p>
          </div>
          <div className="list-controls">
            <button type="button" onClick={() => void onFinalizeBulk()} disabled={bulkFinalizing || selectedDraftIds.length === 0}>
              {bulkFinalizing ? '一括発行中...' : `選択した請求ドラフトを発行${selectedDraftIds.length > 0 ? ` (${selectedDraftIds.length})` : ''}`}
            </button>
          </div>
        </div>

        <div className="subtle" style={{ marginBottom: 12 }}>
          draft 件数: {draftInvoiceIds.length} / finalized 件数: {finalizedInvoiceIds.length}
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            取引先
            <input value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)} placeholder="取引先名で検索" />
          </label>
          <label className="filter-label">
            納品日
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
                <th>詳細</th>
                <th>請求ヘッダー番号</th>
                <th>取引先名</th>
                <th>請求日</th>
                <th>納品日</th>
                <th>ステータス</th>
                <th style={{ textAlign: 'right' }}>仕入単価</th>
                <th style={{ textAlign: 'right' }}>請求単価</th>
                <th style={{ textAlign: 'right' }}>請求数量</th>
                <th style={{ textAlign: 'right' }}>請求金額</th>
                <th style={{ textAlign: 'right' }}>粗利%</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={12} className="subtle">条件に合う請求データがありません。</td>
                </tr>
              ) : (
                filtered.map((row) => {
                  const isDraft = row.status === 'draft';
                  const isSaving = Boolean(savingByItemId[row.invoiceItemId]);
                  return (
                    <tr key={row.invoiceItemId}>
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
                      <td><Link to={`/invoices/drafts/${row.invoiceId}`}>詳細</Link></td>
                      <td>{row.invoiceNo}</td>
                      <td>{row.customerName}</td>
                      <td>{row.invoiceDate}</td>
                      <td>{row.deliveryDate}</td>
                      <td>{STATUS_LABEL[row.status]}</td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(row.unitCostBasis)}</td>
                      <td style={{ textAlign: 'right', minWidth: 140 }}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={priceInputs[row.invoiceItemId] ?? String(row.salesUnitPrice)}
                          disabled={!isDraft || isSaving || bulkFinalizing}
                          onChange={(e) => {
                            const value = e.target.value;
                            setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: value }));
                          }}
                          onBlur={() => void commitSalesUnitPrice(row)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.currentTarget.blur();
                            }
                          }}
                        />
                        {row.autoPriceError ? <div className="field-error">{row.autoPriceError}</div> : null}
                      </td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(row.billableQty)}</td>
                      <td style={{ textAlign: 'right' }}>{currency.format(row.lineAmount)}</td>
                      <td style={{ textAlign: 'right' }}>{formatGrossMargin(row)}</td>
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
