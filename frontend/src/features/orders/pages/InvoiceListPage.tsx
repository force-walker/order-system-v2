import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { PdfExportButton } from 'components/common/PdfExportButton';
import { generateInvoicePdf, listInvoiceSummaries } from 'features/orders/services/invoiceService';
import type { InvoiceSummaryRow } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';
import { openPdfBlob } from 'shared/pdf';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });

export const InvoiceListPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceSummaryRow[]>([]);
  const [pdfGeneratingId, setPdfGeneratingId] = useState<number | null>(null);
  const [pdfError, setPdfError] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        setRows(await listInvoiceSummaries());
      } catch (e) {
        setError(toActionableMessage(e, '請求書一覧の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const sorted = useMemo(() => [...rows].sort((a, b) => b.invoiceId - a.invoiceId), [rows]);

  const onGeneratePdf = async (invoiceId: number) => {
    setPdfGeneratingId(invoiceId);
    setPdfError('');
    try {
      const blob = await generateInvoicePdf(invoiceId);
      openPdfBlob(blob);
    } catch (e) {
      setPdfError(toActionableMessage(e, '請求書PDFの生成に失敗しました。'));
    } finally {
      setPdfGeneratingId(null);
    }
  };

  if (error) return <ErrorState title="請求書一覧の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求書一覧を読み込み中" description="しばらくお待ちください。" />;

  if (sorted.length === 0) return <EmptyState title="請求書がありません" description="発行済み/下書き請求書がありません。" />;

  return (
    <section>
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求書一覧</h2>
            <p className="subtle">請求書単位で表示します。</p>
          </div>
        </div>
        {pdfError ? <p className="field-error" style={{ marginTop: 0, marginBottom: 12 }}>{pdfError}</p> : null}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>請求書番号</th>
                <th>取引先</th>
                <th>日付</th>
                <th>ステータス</th>
                <th style={{ textAlign: 'right' }}>合計金額</th>
                <th style={{ textAlign: 'right' }}>明細件数</th>
                <th>請求書PDF</th>
                <th>詳細</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.invoiceId}>
                  <td>{r.invoiceNo}</td>
                  <td>{r.customerName}</td>
                  <td>{r.invoiceDate}</td>
                  <td>{r.status}</td>
                  <td style={{ textAlign: 'right' }}>{currency.format(r.grandTotal)}</td>
                  <td style={{ textAlign: 'right' }}>{r.itemCount}</td>
                  <td>
                    <PdfExportButton
                      busy={pdfGeneratingId === r.invoiceId}
                      idleLabel="請求書PDF"
                      busyLabel="ダウンロード中..."
                      onClick={() => {
                        void onGeneratePdf(r.invoiceId);
                      }}
                    />
                  </td>
                  <td><Link to={`/invoices/${r.invoiceId}`}>詳細</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
