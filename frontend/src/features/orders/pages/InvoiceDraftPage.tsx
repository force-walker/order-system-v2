import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listInvoiceDraftListRows } from 'features/orders/services/invoiceService';
import type { InvoiceDraftListRow, InvoiceStatus } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });

const formatGrossMargin = (value?: number) => {
  if (value == null || Number.isNaN(value)) return '-';
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toFixed(Math.abs(rounded % 1) < 1e-9 ? 1 : 2)}%`;
};

export const InvoiceDraftPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftListRow[]>([]);
  const [editedUnitPriceByItemId, setEditedUnitPriceByItemId] = useState<Record<number, string>>({});

  const [customerFilter, setCustomerFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('draft');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const draftRows = await listInvoiceDraftListRows();
        setRows(draftRows);
      } catch (e) {
        setError(toActionableMessage(e, '請求ドラフト一覧の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filtered = useMemo(() => {
    const cq = customerFilter.trim().toLowerCase();
    return rows.filter((r) => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (dateFilter && r.deliveryDate !== dateFilter) return false;
      if (cq && !r.customerName.toLowerCase().includes(cq)) return false;
      return true;
    });
  }, [rows, customerFilter, dateFilter, statusFilter]);

  if (error) return <ErrorState title="請求ドラフト一覧の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求ドラフト一覧を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求ドラフト一覧</h2>
            <p className="subtle">draftのみを作業対象として表示します。</p>
          </div>
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

        {filtered.length === 0 ? (
          <EmptyState title="表示対象がありません" description="条件に合う請求ドラフトがありません。" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>取引先名</th>
                  <th>商品名</th>
                  <th style={{ textAlign: 'right' }}>請求数量</th>
                  <th>請求単位</th>
                  <th style={{ textAlign: 'right' }}>請求単価</th>
                  <th style={{ textAlign: 'right' }}>請求金額</th>
                  <th style={{ textAlign: 'right' }}>粗利％</th>
                  <th>詳細</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const editedPriceRaw = editedUnitPriceByItemId[row.invoiceItemId];
                  const editedPrice =
                    editedPriceRaw != null && editedPriceRaw.trim() !== '' && !Number.isNaN(Number(editedPriceRaw))
                      ? Number(editedPriceRaw)
                      : row.salesUnitPrice;
                  const calculatedAmount = editedPrice * row.billableQty;
                  const baseCost = row.grossMarginPct != null
                    ? row.lineAmount * (1 - row.grossMarginPct / 100)
                    : null;
                  const calculatedMargin =
                    baseCost != null && calculatedAmount > 0
                      ? ((calculatedAmount - baseCost) / calculatedAmount) * 100
                      : row.grossMarginPct;

                  return (
                    <tr key={row.invoiceItemId}>
                      <td>{row.customerName}</td>
                      <td>{row.productName}</td>
                      <td style={{ textAlign: 'right' }}>{row.billableQty}</td>
                      <td>{row.billableUom}</td>
                      <td style={{ textAlign: 'right' }}>
                        <input
                          type="number"
                          min={0}
                          step="0.01"
                          value={editedPriceRaw ?? String(row.salesUnitPrice)}
                          onChange={(e) => setEditedUnitPriceByItemId((prev) => ({ ...prev, [row.invoiceItemId]: e.target.value }))}
                          style={{ width: 110, textAlign: 'right' }}
                        />
                      </td>
                      <td style={{ textAlign: 'right' }}>{currency.format(calculatedAmount)}</td>
                      <td style={{ textAlign: 'right' }}>{formatGrossMargin(calculatedMargin ?? undefined)}</td>
                      <td><Link to={`/invoices/drafts/${row.invoiceId}`}>詳細</Link></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
