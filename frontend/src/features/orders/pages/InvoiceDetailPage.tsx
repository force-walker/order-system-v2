import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { PdfExportButton } from 'components/common/PdfExportButton';
import { generateInvoicePdf, getInvoiceDetailView, listInvoiceSummaries } from 'features/orders/services/invoiceService';
import type { InvoiceDetailView, InvoiceSummaryRow } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';
import { openPdfBlob } from 'shared/pdf';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });

export const InvoiceDetailPage = () => {
  const { invoiceId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState<InvoiceDetailView | null>(null);
  const [summaries, setSummaries] = useState<InvoiceSummaryRow[]>([]);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [pdfError, setPdfError] = useState('');

  useEffect(() => {
    const load = async () => {
      if (!invoiceId) return;
      setLoading(true);
      setError('');
      try {
        const [detail, list] = await Promise.all([
          getInvoiceDetailView(Number(invoiceId)),
          listInvoiceSummaries(),
        ]);
        setData(detail);
        setSummaries(list);
      } catch (e) {
        setError(toActionableMessage(e, '請求書詳細の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [invoiceId]);

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

  const nav = useMemo(() => {
    if (!data) return { prevId: null as number | null, nextId: null as number | null };
    const sorted = [...summaries].sort((a, b) => b.invoiceId - a.invoiceId);
    const idx = sorted.findIndex((r) => r.invoiceId === data.invoiceId);
    if (idx < 0) return { prevId: null as number | null, nextId: null as number | null };
    return {
      nextId: sorted[idx - 1]?.invoiceId ?? null,
      prevId: sorted[idx + 1]?.invoiceId ?? null,
    };
  }, [data, summaries]);

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
            <Link to="/invoices" className="order-link">← 請求書一覧へ</Link>
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
                <Link to={`/invoices/${nav.nextId}`} className="order-link">次の請求書詳細へジャンプ</Link>
              ) : (
                <span className="nav-link-disabled">次の請求書詳細へジャンプ</span>
              )}
              {nav.prevId ? (
                <Link to={`/invoices/${nav.prevId}`} className="order-link">前の請求書詳細へジャンプ</Link>
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
