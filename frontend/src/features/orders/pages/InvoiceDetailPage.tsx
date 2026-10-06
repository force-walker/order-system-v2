import type { EntityId } from 'shared/entityId';
import { newestInvoiceFirst } from 'shared/entityId';
import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { PdfExportButton } from 'components/common/PdfExportButton';
import { generateInvoicePdf, getInvoiceDetailView, getInvoiceHistoryNeighbors, listInvoiceSummaries, updateInvoicePaymentStatus } from 'features/orders/services/invoiceService';
import type { InvoiceDetailView, InvoiceSummaryRow } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';
import { openPdfBlob } from 'shared/pdf';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'HKD', minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const InvoiceDetailPage = () => {
  const { invoiceId } = useParams();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<InvoiceDetailView | null>(null);
  const [summaries, setSummaries] = useState<InvoiceSummaryRow[]>([]);
  const [historyNav, setHistoryNav] = useState<{prevId: EntityId | null; nextId: EntityId | null} | null>(null);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [pdfError, setPdfError] = useState('');

  useEffect(() => {
    const load = async () => {
      if (!invoiceId) return;
      setLoading(true);
      setError('');
      try {
        const historyContext = searchParams.get('history') === '1';
        const contextParams = { search: searchParams.get('q') ?? undefined, dateFrom: searchParams.get('from') ?? undefined,
          dateTo: searchParams.get('to') ?? undefined, customerId: searchParams.get('customer') ? Number(searchParams.get('customer')) : undefined,
          invoiceStatus: searchParams.get('status') ?? 'finalized', paymentStatus: searchParams.get('payment') ?? undefined,
          overdue: searchParams.get('overdue') ?? undefined, sort: searchParams.get('sort') ?? 'issue_date', direction: searchParams.get('dir') ?? 'desc',
          page: Number(searchParams.get('page') ?? 1), pageSize: 50 };
        const [detail, list, neighbors] = await Promise.all([
          getInvoiceDetailView(invoiceId ?? ''),
          historyContext ? Promise.resolve([]) : listInvoiceSummaries(),
          historyContext ? getInvoiceHistoryNeighbors(invoiceId ?? '', contextParams) : Promise.resolve(null),
        ]);
        setData(detail);
        setSummaries(list);
        setHistoryNav(neighbors);
      } catch (e) {
        setError(toActionableMessage(e, '請求書詳細の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [invoiceId, searchParams.toString()]);

  const onGeneratePdf = async () => {
    if (!data) return;
    setPdfGenerating(true);
    setPdfError('');
    try {
      const blob = await generateInvoicePdf(data.invoiceId);
      openPdfBlob(blob);
    } catch (e) {
      setPdfError(toActionableMessage(e, '請求書PDFの生成に失敗しました。'));
    } finally {
      setPdfGenerating(false);
    }
  };

  const onPaymentStatus = async (paymentStatus: 'unpaid' | 'partially_paid' | 'paid') => {
    if (!data) return;
    await updateInvoicePaymentStatus(data.invoiceId, paymentStatus);
    setData({ ...data, paymentStatus });
  };

  const nav = useMemo(() => {
    if (historyNav) return historyNav;
    if (!data) return { prevId: null as EntityId | null, nextId: null as EntityId | null };
    const sorted = [...summaries].sort(newestInvoiceFirst);
    const idx = sorted.findIndex((r) => r.invoiceId === data.invoiceId);
    if (idx < 0) return { prevId: null as EntityId | null, nextId: null as EntityId | null };
    return {
      nextId: sorted[idx - 1]?.invoiceId ?? null,
      prevId: sorted[idx + 1]?.invoiceId ?? null,
    };
  }, [data, summaries, searchParams.toString(), historyNav]);

  const historyParams = new URLSearchParams(searchParams);
  historyParams.delete('history');

  if (error) return <ErrorState title="請求書詳細の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求書詳細を読み込み中" description="しばらくお待ちください。" />;
  if (!data) return <EmptyState title="請求書がありません" description="対象データが見つかりません。" />;

  return (
    <section>
      <div className="card form-grid">
        <div className="list-header">
          <div>
            <h2>請求書詳細 #{data.invoiceNo}</h2>
            <p className="subtle">ステータス: {data.status}</p>
            {pdfError ? <p className="field-error">{pdfError}</p> : null}
          </div>
          <div style={{ display: 'grid', gap: 6, justifyItems: 'end' }}>
            <Link to={`/invoices?${historyParams}`} className="order-link">← 請求履歴へ</Link>
            <PdfExportButton
              busy={pdfGenerating}
              idleLabel="請求書PDF"
              busyLabel="ダウンロード中..."
              onClick={() => {
                void onGeneratePdf();
              }}
            />
            <div style={{ display: 'flex', gap: 14 }}>
              {nav.nextId ? (
                <Link to={`/invoices/${nav.nextId}?${searchParams}`} className="order-link">次の請求書詳細へジャンプ</Link>
              ) : (
                <span className="nav-link-disabled">次の請求書詳細へジャンプ</span>
              )}
              {nav.prevId ? (
                <Link to={`/invoices/${nav.prevId}?${searchParams}`} className="order-link">前の請求書詳細へジャンプ</Link>
              ) : (
                <span className="nav-link-disabled">前の請求書詳細へジャンプ</span>
              )}
            </div>
          </div>
        </div>

        <div className="form-grid two-col">
          <div>
            <p><strong>取引先:</strong> {data.customerName}</p>
            <p><strong>請求日:</strong> {data.invoiceDate}</p>
            <p><strong>納品日:</strong> {data.deliveryDate}</p>
            <p><strong>支払期限:</strong> {data.dueDate ?? '-'}</p>
            <label><strong>回収状況:</strong> <select value={data.paymentStatus ?? 'unpaid'} onChange={(e) => void onPaymentStatus(e.target.value as any)}>
              <option value="unpaid">未回収</option><option value="partially_paid">一部回収</option><option value="paid">回収済み</option>
            </select></label>
          </div>
          <div>
            <p><strong>小計:</strong> {currency.format(data.subtotal)}</p>
            <p><strong>税額:</strong> {currency.format(data.taxTotal)}</p>
            <p><strong>合計:</strong> {currency.format(data.grandTotal)}</p>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>商品名</th>
                <th style={{ textAlign: 'right' }}>請求数量</th>
                <th>請求単位</th>
                <th style={{ textAlign: 'right' }}>請求単価</th>
                <th style={{ textAlign: 'right' }}>請求金額</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.invoiceItemId}>
                  <td>{row.productName}</td>
                  <td style={{ textAlign: 'right' }}>{row.billableQty}</td>
                  <td>{row.billableUom}</td>
                  <td style={{ textAlign: 'right' }}>{currency.format(row.salesUnitPrice)}</td>
                  <td style={{ textAlign: 'right' }}>{currency.format(row.lineAmount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
