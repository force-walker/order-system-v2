import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { finalizeInvoiceDraft, getInvoiceDraftItems } from 'features/orders/services/invoiceService';
import type { InvoiceDraftItem } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

export const InvoiceDraftDetailPage = () => {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftItem[]>([]);
  const [finalizing, setFinalizing] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!invoiceId) return;
      setLoading(true);
      setError('');
      try {
        const items = await getInvoiceDraftItems(Number(invoiceId));
        setRows(items);
      } catch (e) {
        setError(toActionableMessage(e, '請求ドラフト明細の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [invoiceId]);

  const onFinalize = async () => {
    if (!invoiceId) return;
    setFinalizing(true);
    try {
      await finalizeInvoiceDraft(Number(invoiceId));
      navigate('/invoices/drafts');
    } catch (e) {
      setError(toActionableMessage(e, '請求確定に失敗しました。'));
    } finally {
      setFinalizing(false);
    }
  };

  if (error) return <ErrorState title="請求ドラフト明細の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求ドラフト明細を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求ドラフト詳細 #{invoiceId}</h2>
            <p className="subtle">数量差異/単価調整後の値を確認し、必要に応じて確定します。</p>
          </div>
          <div className="list-controls">
            <button type="button" className="secondary" onClick={() => navigate('/invoices/drafts')}>戻る</button>
            <button type="button" onClick={() => void onFinalize()} disabled={finalizing}>{finalizing ? '確定中...' : '確定（別操作）'}</button>
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="明細がありません" description="このドラフトには明細がありません。" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>order_item_id</th>
                  <th>数量</th>
                  <th>単位</th>
                  <th>単価</th>
                  <th>金額</th>
                  <th>税額</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/orders/item-allocations`}>{r.orderItemId}</Link></td>
                    <td>{r.billableQty}</td>
                    <td>{r.billableUom}</td>
                    <td>{r.salesUnitPrice}</td>
                    <td>{r.lineAmount}</td>
                    <td>{r.taxAmount}</td>
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
