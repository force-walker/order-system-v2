import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listOrderItemAllocationWorkItems, type OrderItemAllocationWorkItem } from 'features/orders/services/orderItemAllocationsService';
import { bulkUpsertPurchaseResults } from 'features/orders/services/purchaseService';
import { getProductDetail } from 'features/products/services/productsService';
import { toActionableMessage } from 'shared/error';

type RowEdit = {
  selected: boolean;
  receivedQty: string;
  invoiceQty: string;
  rowError?: string;
};

type UnitPair = {
  orderUom: string;
  invoiceUom: string;
};

export const PurchasePage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [rows, setRows] = useState<OrderItemAllocationWorkItem[]>([]);
  const [unitsByProductId, setUnitsByProductId] = useState<Record<number, UnitPair>>({});
  const [editByItemId, setEditByItemId] = useState<Record<number, RowEdit>>({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const all = await listOrderItemAllocationWorkItems({ unallocatedOnly: false });
      const allocated = all.filter((r) => r.allocationStatus === 'allocated' && r.allocationId != null);

      const raw = sessionStorage.getItem('osv2_purchase_target_allocations');
      const targetAllocationIds: number[] = raw ? (JSON.parse(raw) as number[]) : [];
      const filtered = targetAllocationIds.length > 0
        ? allocated.filter((r) => {
            const aid = r.allocationId;
            return typeof aid === 'number' && targetAllocationIds.includes(aid);
          })
        : allocated;

      setRows(filtered);

      const productIds = [...new Set(filtered.map((r) => r.productId))];
      const unitEntries = await Promise.all(
        productIds.map(async (productId) => {
          try {
            const p = await getProductDetail(productId);
            if (!p) throw new Error('product not found');
            return [productId, { orderUom: p.orderUom, invoiceUom: p.invoiceUom }] as const;
          } catch {
            return [productId, { orderUom: 'count', invoiceUom: 'count' }] as const;
          }
        }),
      );
      setUnitsByProductId(Object.fromEntries(unitEntries));

      setEditByItemId((prev) =>
        Object.fromEntries(
          filtered.map((r) => [
            r.orderItemId,
            {
              selected: prev[r.orderItemId]?.selected ?? false,
              receivedQty: prev[r.orderItemId]?.receivedQty ?? String(r.manualQty ?? r.orderedQty),
              invoiceQty: prev[r.orderItemId]?.invoiceQty ?? String(r.manualQty ?? r.orderedQty),
              rowError: undefined,
            },
          ]),
        ),
      );
    } catch (e) {
      setError(toActionableMessage(e, '納品確認対象の取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const selectedCount = useMemo(() => rows.filter((r) => editByItemId[r.orderItemId]?.selected).length, [rows, editByItemId]);

  const saveBulk = async () => {
    const selectedRows = rows.filter((r) => editByItemId[r.orderItemId]?.selected);
    if (selectedRows.length === 0) {
      setToast({ type: 'error', message: '保存対象がありません。行を選択してください。' });
      return;
    }

    const payload = selectedRows.map((r) => {
      const edit = editByItemId[r.orderItemId];
      const units = unitsByProductId[r.productId] ?? { orderUom: 'count', invoiceUom: 'count' };
      const received = Number(edit.receivedQty);
      const invoiced = Number(edit.invoiceQty);
      const shortage = Math.max(r.orderedQty - received, 0);
      return {
        orderItemId: r.orderItemId,
        row: {
          allocationId: Number(r.allocationId),
          supplierId: r.manualSupplierId ?? undefined,
          purchasedQty: received,
          purchasedUom: units.orderUom,
          shortageQty: shortage > 0 ? shortage : undefined,
          resultStatus: shortage > 0 ? ('partially_filled' as const) : ('filled' as const),
          invoiceableFlag: true,
          note: `invoice_qty=${invoiced} ${units.invoiceUom}`,
        },
      };
    });

    const invalid = payload.filter((p) => !Number.isFinite(p.row.purchasedQty) || p.row.purchasedQty < 0 || Number.isNaN(Number((editByItemId[p.orderItemId]?.invoiceQty ?? ''))));
    if (invalid.length > 0) {
      setToast({ type: 'error', message: '受取数量/請求数量の数値入力を確認してください。' });
      return;
    }

    setSaving(true);
    try {
      const upserted = await bulkUpsertPurchaseResults(payload.map((p) => p.row));
      setToast({ type: 'success', message: `納品確認を保存しました（${upserted}件）。` });
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '納品確認の保存に失敗しました。') });
    } finally {
      setSaving(false);
    }
  };

  if (error) return <ErrorState title="納品確認対象の取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  if (loading) return <LoadingState title="納品確認ページを読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      {toast ? <div className={`toast toast-overlay ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>納品確認（Purchase Result）</h2>
            <p className="subtle">一括割当で保存済みの行を、そのまま一覧で確認・登録できます。</p>
          </div>
          <div className="list-controls">
            <button type="button" onClick={() => void saveBulk()} disabled={saving}>{saving ? '保存中...' : `選択行を保存 (${selectedCount})`}</button>
          </div>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="対象データがありません" description="一括割当で保存済み行が見つかりません。" actionLabel="再読み込み" onAction={load} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>選択</th>
                  <th>注文番号</th>
                  <th>顧客</th>
                  <th>商品</th>
                  <th>受注数量 + 受注単位</th>
                  <th>受取数量 + 受注単位</th>
                  <th>請求数量 + 請求単位</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const units = unitsByProductId[r.productId] ?? { orderUom: 'count', invoiceUom: 'count' };
                  const edit = editByItemId[r.orderItemId];
                  return (
                    <tr key={r.orderItemId}>
                      <td>
                        <input
                          type="checkbox"
                          checked={Boolean(edit?.selected)}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], selected: e.target.checked } }))}
                        />
                      </td>
                      <td>
                        {r.orderId ? <Link to={`/orders/${r.orderId}/edit`} className="order-link">{r.orderNo}</Link> : r.orderNo}
                      </td>
                      <td>{r.customerName}</td>
                      <td>{r.productName}</td>
                      <td>{r.orderedQty} {units.orderUom}</td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          step="1"
                          value={edit?.receivedQty ?? ''}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], receivedQty: e.target.value, rowError: undefined } }))}
                        /> {units.orderUom}
                      </td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          step="1"
                          value={edit?.invoiceQty ?? ''}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], invoiceQty: e.target.value, rowError: undefined } }))}
                        /> {units.invoiceUom}
                      </td>
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
