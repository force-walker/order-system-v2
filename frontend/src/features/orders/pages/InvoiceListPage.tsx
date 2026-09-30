import type { EntityId } from 'shared/entityId';
import { newestInvoiceFirst } from 'shared/entityId';
import { useEffect, useMemo, useRef, useState } from 'react';
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
  const [pdfGeneratingId, setPdfGeneratingId] = useState<EntityId | null>(null);
  const [pdfError, setPdfError] = useState('');
  const [invoiceDate, setInvoiceDate] = useState('');
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<EntityId[]>([]);
  const selectAllRef = useRef<HTMLInputElement>(null);

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

  const sorted = useMemo(
    () => rows.filter((row) => !invoiceDate || row.invoiceDate === invoiceDate).sort(newestInvoiceFirst),
    [rows, invoiceDate],
  );
  const visibleIds = useMemo(() => sorted.map((row) => row.invoiceId), [sorted]);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedInvoiceIds.includes(id));
  const someVisibleSelected = visibleIds.some((id) => selectedInvoiceIds.includes(id));

  useEffect(() => {
    const visible = new Set(visibleIds);
    setSelectedInvoiceIds((current) => current.filter((id) => visible.has(id)));
  }, [invoiceDate, rows]);

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someVisibleSelected && !allVisibleSelected;
  }, [allVisibleSelected, someVisibleSelected]);

  const toggleAllVisible = (checked: boolean) => {
    setSelectedInvoiceIds(checked ? visibleIds : []);
  };

  const onGeneratePdf = async (invoiceId: EntityId) => {
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
            <p className="subtle">発行済み請求書の参照ページです。請求書PDF は帳票出力のみで、ステータス変更は行いません。</p>
          </div>
        </div>
        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            請求日
            <input aria-label="請求日" type="date" value={invoiceDate} onChange={(event) => setInvoiceDate(event.target.value)} />
          </label>
          <button type="button" className="secondary" onClick={() => setInvoiceDate('')}>全期間</button>
        </div>
        {pdfError ? <p className="field-error" style={{ marginTop: 0, marginBottom: 12 }}>{pdfError}</p> : null}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    aria-label="表示中の請求書を全選択"
                    checked={allVisibleSelected}
                    disabled={visibleIds.length === 0}
                    onChange={(event) => toggleAllVisible(event.target.checked)}
                  />
                </th>
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
              {sorted.length === 0 ? (
                <tr><td colSpan={9} className="subtle">指定した請求日の請求書はありません。</td></tr>
              ) : sorted.map((r) => (
                <tr key={r.invoiceId}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`請求書 ${r.invoiceNo} を選択`}
                      checked={selectedInvoiceIds.includes(r.invoiceId)}
                      onChange={(event) => setSelectedInvoiceIds((current) => (
                        event.target.checked
                          ? [...new Set([...current, r.invoiceId])]
                          : current.filter((id) => id !== r.invoiceId)
                      ))}
                    />
                  </td>
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
