import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { finalizeInvoiceDraft, getInvoiceDraftItems, getInvoiceReport, updateInvoiceDraftItem } from 'features/orders/services/invoiceService';
import type { InvoiceDraftItem, InvoiceReport } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY', maximumFractionDigits: 0 });

type EditRow = {
  billableQty: string;
  salesUnitPrice: string;
  rowError?: string;
};

export const InvoiceDraftDetailPage = () => {
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftItem[]>([]);
  const [report, setReport] = useState<InvoiceReport | null>(null);
  const [editByItemId, setEditByItemId] = useState<Record<number, EditRow>>({});
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);

  const isFinalized = report?.status === 'finalized';

  const load = async () => {
    if (!invoiceId) return;
    setLoading(true);
    setError('');
    try {
      const [items, reportData] = await Promise.all([
        getInvoiceDraftItems(Number(invoiceId)),
        getInvoiceReport(Number(invoiceId)),
      ]);
      setRows(items);
      setReport(reportData);
      setEditByItemId((prev) =>
        Object.fromEntries(
          items.map((r) => [
            r.id,
            {
              billableQty: prev[r.id]?.billableQty ?? String(r.billableQty),
              salesUnitPrice: prev[r.id]?.salesUnitPrice ?? String(r.salesUnitPrice),
              rowError: undefined,
            },
          ]),
        ),
      );
    } catch (e) {
      setError(toActionableMessage(e, '請求ドラフト明細の取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [invoiceId]);

  const totalsPreview = useMemo(() => {
    const subtotal = rows.reduce((acc, row) => {
      const edit = editByItemId[row.id];
      const qty = Number(edit?.billableQty ?? row.billableQty);
      const price = Number(edit?.salesUnitPrice ?? row.salesUnitPrice);
      if (!Number.isFinite(qty) || !Number.isFinite(price)) return acc;
      return acc + qty * price;
    }, 0);
    return subtotal;
  }, [rows, editByItemId]);

  const onSave = async () => {
    if (!invoiceId) return;
    if (isFinalized) return;

    const updateTargets = rows.map((row) => {
      const edit = editByItemId[row.id];
      return {
        invoiceItemId: row.id,
        billableQty: Number(edit?.billableQty ?? row.billableQty),
        salesUnitPrice: Number(edit?.salesUnitPrice ?? row.salesUnitPrice),
      };
    });

    const invalid = updateTargets.filter((r) => !Number.isFinite(r.billableQty) || !Number.isFinite(r.salesUnitPrice) || r.billableQty < 0 || r.salesUnitPrice < 0);
    if (invalid.length > 0) {
      setEditByItemId((prev) => {
        const next = { ...prev };
        invalid.forEach((r) => {
          next[r.invoiceItemId] = {
            ...next[r.invoiceItemId],
            rowError: '数量/単価は0以上の数値で入力してください',
          };
        });
        return next;
      });
      return;
    }

    setSaving(true);
    try {
      for (const target of updateTargets) {
        await updateInvoiceDraftItem(Number(invoiceId), target.invoiceItemId, {
          billableQty: target.billableQty,
          salesUnitPrice: target.salesUnitPrice,
        });
      }
      await load();
    } catch (e) {
      setError(toActionableMessage(e, '請求ドラフト明細の更新に失敗しました。'));
    } finally {
      setSaving(false);
    }
  };

  const onFinalize = async () => {
    if (!invoiceId || isFinalized) return;
    const ok = window.confirm('この請求ドラフトを確定します。確定後は編集できません。実行しますか？');
    if (!ok) return;

    setFinalizing(true);
    try {
      await finalizeInvoiceDraft(Number(invoiceId));
      await load();
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
            <p className="subtle">
              {report ? `${report.customerName} / ${report.invoiceDate} / status=${report.status}` : '請求詳細'}
            </p>
          </div>
          <div className="list-controls">
            <button type="button" className="secondary" onClick={() => navigate('/invoices/drafts')}>戻る</button>
            <button type="button" onClick={() => void onSave()} disabled={saving || isFinalized}>{saving ? '保存中...' : '保存'}</button>
            <button type="button" className="secondary" onClick={() => void onFinalize()} disabled={finalizing || isFinalized}>{finalizing ? '確定中...' : '請求確定'}</button>
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="明細がありません" description="このドラフトには明細がありません。" />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>invoice_item_id</th>
                    <th>order_item_id</th>
                    <th>請求数量</th>
                    <th>請求単位</th>
                    <th>請求単価</th>
                    <th>請求金額</th>
                    <th>税額</th>
                    <th>エラー</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const edit = editByItemId[r.id];
                    const qty = Number(edit?.billableQty ?? r.billableQty);
                    const price = Number(edit?.salesUnitPrice ?? r.salesUnitPrice);
                    const previewAmount = Number.isFinite(qty) && Number.isFinite(price) ? qty * price : r.lineAmount;

                    return (
                      <tr key={r.id}>
                        <td>{r.id}</td>
                        <td>{r.orderItemId}</td>
                        <td>
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={edit?.billableQty ?? ''}
                            disabled={isFinalized}
                            onChange={(e) => setEditByItemId((prev) => ({
                              ...prev,
                              [r.id]: { ...prev[r.id], billableQty: e.target.value, rowError: undefined },
                            }))}
                          />
                        </td>
                        <td>{r.billableUom}</td>
                        <td>
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={edit?.salesUnitPrice ?? ''}
                            disabled={isFinalized}
                            onChange={(e) => setEditByItemId((prev) => ({
                              ...prev,
                              [r.id]: { ...prev[r.id], salesUnitPrice: e.target.value, rowError: undefined },
                            }))}
                          />
                        </td>
                        <td>{currency.format(previewAmount)}</td>
                        <td>{currency.format(r.taxAmount)}</td>
                        <td>{edit?.rowError ? <span className="field-error">{edit.rowError}</span> : '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="card" style={{ marginTop: 12 }}>
              <h3>請求書ビュー（確認用）</h3>
              {report ? (
                <div className="form-grid two-col">
                  <div>
                    <p><strong>請求書番号:</strong> {report.invoiceNo}</p>
                    <p><strong>顧客名:</strong> {report.customerName}</p>
                    <p><strong>請求日:</strong> {report.invoiceDate}</p>
                    <p><strong>納品日:</strong> {report.deliveryDate}</p>
                    <p><strong>支払期日:</strong> {report.dueDate ?? '-'}</p>
                  </div>
                  <div>
                    <p><strong>小計:</strong> {currency.format(report.subtotal)}</p>
                    <p><strong>税額:</strong> {currency.format(report.taxTotal)}</p>
                    <p><strong>合計:</strong> {currency.format(report.grandTotal)}</p>
                    {!isFinalized ? <p className="subtle">保存前プレビュー小計: {currency.format(totalsPreview)}</p> : <p className="subtle">finalizedのため編集不可</p>}
                  </div>
                </div>
              ) : null}
            </div>
          </>
        )}
      </div>
    </section>
  );
};
