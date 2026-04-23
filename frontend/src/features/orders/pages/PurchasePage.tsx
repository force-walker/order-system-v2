import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
  type OrderItemAllocationWorkItem,
  type SupplierFilterOption,
} from 'features/orders/services/orderItemAllocationsService';
import {
  bulkUpsertPurchaseResults,
  deferPurchaseResult,
  generateDraftInvoiceFromPurchase,
  listPurchaseWorkQueue,
  undeferPurchaseResult,
} from 'features/orders/services/purchaseService';
import type { PurchaseResultItem } from 'features/orders/types/order';
import { getProductDetail } from 'features/products/services/productsService';
import { toActionableMessage } from 'shared/error';

type RowEdit = {
  selected: boolean;
  invoiceQty: string;
  rowError?: string;
};

type UnitPair = {
  orderUom: string;
  invoiceUom: string;
};

type SortKey = 'customerName' | 'productName' | 'supplierName';
type SortDirection = 'asc' | 'desc';

export const PurchasePage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [rows, setRows] = useState<OrderItemAllocationWorkItem[]>([]);
  const [queueItems, setQueueItems] = useState<PurchaseResultItem[]>([]);
  const [queueResultMessage, setQueueResultMessage] = useState<Record<number, string>>({});
  const [queueDraftInvoiceId, setQueueDraftInvoiceId] = useState<Record<number, number>>({});
  const [suppliers, setSuppliers] = useState<SupplierFilterOption[]>([]);
  const [unitsByProductId, setUnitsByProductId] = useState<Record<number, UnitPair>>({});
  const [editByItemId, setEditByItemId] = useState<Record<number, RowEdit>>({});
  const [saving, setSaving] = useState(false);
  const [customerFilter, setCustomerFilter] = useState('');
  const [productFilter, setProductFilter] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('customerName');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [lastSelectedId, setLastSelectedId] = useState<number | null>(null);

  const supplierNameById = useMemo(() => {
    const map = new Map<number, string>();
    suppliers.forEach((s) => {
      const name = s.label.includes(':') ? s.label.split(':').slice(1).join(':').trim() : s.label;
      map.set(s.id, name);
    });
    return map;
  }, [suppliers]);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [all, supplierOptions, queue] = await Promise.all([
        listOrderItemAllocationWorkItems({ unallocatedOnly: false }),
        listSupplierFilterOptions(),
        listPurchaseWorkQueue(),
      ]);
      setSuppliers(supplierOptions);
      setQueueItems(queue.items);

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
              invoiceQty: prev[r.orderItemId]?.invoiceQty ?? '',
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

  const filteredRows = useMemo(() => {
    const customerQ = customerFilter.trim().toLowerCase();
    const productQ = productFilter.trim().toLowerCase();
    const supplierQ = supplierFilter.trim().toLowerCase();

    return rows.filter((r) => {
      const supplierName = r.manualSupplierId ? supplierNameById.get(r.manualSupplierId) ?? `仕入先#${r.manualSupplierId}` : '';
      if (customerQ && !r.customerName.toLowerCase().includes(customerQ)) return false;
      if (productQ && !r.productName.toLowerCase().includes(productQ)) return false;
      if (supplierQ && !supplierName.toLowerCase().includes(supplierQ)) return false;
      return true;
    });
  }, [rows, customerFilter, productFilter, supplierFilter, supplierNameById]);

  const sortedRows = useMemo(() => {
    const sorted = [...filteredRows];
    const dir = sortDirection === 'asc' ? 1 : -1;

    sorted.sort((a, b) => {
      const supplierA = a.manualSupplierId ? supplierNameById.get(a.manualSupplierId) ?? `仕入先#${a.manualSupplierId}` : '';
      const supplierB = b.manualSupplierId ? supplierNameById.get(b.manualSupplierId) ?? `仕入先#${b.manualSupplierId}` : '';

      const av = sortKey === 'customerName' ? a.customerName : sortKey === 'productName' ? a.productName : supplierA;
      const bv = sortKey === 'customerName' ? b.customerName : sortKey === 'productName' ? b.productName : supplierB;

      return av.localeCompare(bv, 'ja') * dir;
    });

    return sorted;
  }, [filteredRows, sortKey, sortDirection, supplierNameById]);

  const onSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDirection('asc');
  };

  const sortLabel = (key: SortKey, label: string) => {
    if (sortKey !== key) return label;
    return `${label} ${sortDirection === 'asc' ? '▲' : '▼'}`;
  };

  const visibleIds = useMemo(() => sortedRows.map((r) => r.orderItemId), [sortedRows]);

  const selectVisibleChecked = useMemo(
    () => visibleIds.length > 0 && visibleIds.every((id) => editByItemId[id]?.selected),
    [visibleIds, editByItemId],
  );

  const toggleSelectVisible = (checked: boolean) => {
    setEditByItemId((prev) => {
      const next = { ...prev };
      visibleIds.forEach((id) => {
        if (!next[id]) return;
        next[id] = { ...next[id], selected: checked };
      });
      return next;
    });
  };

  const onRowCheckboxChange = (orderItemId: number, checked: boolean, shiftKey: boolean) => {
    const targetIndex = sortedRows.findIndex((row) => row.orderItemId === orderItemId);

    setEditByItemId((prev) => {
      const next = { ...prev };
      if (shiftKey && lastSelectedId != null) {
        const lastIndex = sortedRows.findIndex((row) => row.orderItemId === lastSelectedId);
        if (lastIndex >= 0 && targetIndex >= 0) {
          const [start, end] = lastIndex < targetIndex ? [lastIndex, targetIndex] : [targetIndex, lastIndex];
          for (let i = start; i <= end; i += 1) {
            const id = sortedRows[i].orderItemId;
            if (!next[id]) continue;
            next[id] = { ...next[id], selected: checked };
          }
        }
      } else if (next[orderItemId]) {
        next[orderItemId] = { ...next[orderItemId], selected: checked };
      }
      return next;
    });

    setLastSelectedId(orderItemId);
  };

  const selectedCount = useMemo(() => rows.filter((r) => editByItemId[r.orderItemId]?.selected).length, [rows, editByItemId]);

  const onDefer = async (id: number) => {
    try {
      await deferPurchaseResult(id, 'manual defer');
      setQueueResultMessage((prev) => ({ ...prev, [id]: '後回しに設定しました' }));
      await load();
    } catch (e) {
      setQueueResultMessage((prev) => ({ ...prev, [id]: toActionableMessage(e, '後回し設定に失敗') }));
    }
  };

  const onUndefer = async (id: number) => {
    try {
      await undeferPurchaseResult(id);
      setQueueResultMessage((prev) => ({ ...prev, [id]: '後回し解除しました' }));
      await load();
    } catch (e) {
      setQueueResultMessage((prev) => ({ ...prev, [id]: toActionableMessage(e, '後回し解除に失敗') }));
    }
  };

  const onGenerateDraft = async (item: PurchaseResultItem) => {
    const orderId = rows.find((r) => r.allocationId === item.allocationId)?.orderId;
    if (!orderId) {
      setQueueResultMessage((prev) => ({ ...prev, [item.id]: 'order特定不可のためdraft生成不可' }));
      return;
    }
    const invoiceNo = `DRAFT-${item.id}-${Date.now()}`;
    const invoiceDate = new Date().toISOString().slice(0, 10);
    try {
      const invoiceId = await generateDraftInvoiceFromPurchase({ invoiceNo, orderId, invoiceDate });
      setQueueDraftInvoiceId((prev) => ({ ...prev, [item.id]: invoiceId }));
      setQueueResultMessage((prev) => ({ ...prev, [item.id]: `請求ドラフト作成完了: invoice#${invoiceId}` }));
      setToast({ type: 'success', message: `請求ドラフトを作成しました（invoice#${invoiceId}）。` });
    } catch (e) {
      setQueueResultMessage((prev) => ({ ...prev, [item.id]: toActionableMessage(e, 'draft生成失敗') }));
    }
  };

  const saveBulk = async () => {
    const selectedRows = rows.filter((r) => editByItemId[r.orderItemId]?.selected);
    if (selectedRows.length === 0) {
      setToast({ type: 'error', message: '保存対象がありません。行を選択してください。' });
      return;
    }

    const payload = selectedRows.map((r) => {
      const edit = editByItemId[r.orderItemId];
      const units = unitsByProductId[r.productId] ?? { orderUom: 'count', invoiceUom: 'count' };
      const received = Number(r.manualQty ?? r.orderedQty);
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

        <div className="card" style={{ marginBottom: 12 }}>
          <div className="list-header">
            <h3>作業キュー（納品確認）</h3>
            <button type="button" className="secondary" onClick={() => navigate('/invoices/drafts')}>請求ドラフト一覧へ</button>
          </div>
          {queueItems.length === 0 ? <p className="subtle">対象なし</p> : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>顧客</th>
                  <th>商品</th>
                  <th>仕入先</th>
                  <th>受取</th>
                  <th>請求</th>
                  <th>操作</th>
                  <th>結果</th>
                </tr>
              </thead>
              <tbody>
                {queueItems.map((q) => (
                  <tr key={q.id}>
                    <td>{q.id}</td>
                    <td>{q.customerName ?? '-'}</td>
                    <td>{q.productName ?? '-'}</td>
                    <td>{q.supplierName ?? '-'}</td>
                    <td>{q.receivedQty ?? q.purchasedQty} {q.orderUom ?? q.purchasedUom}</td>
                    <td>{q.invoiceQty ?? ''} {q.invoiceUom ?? ''}</td>
                    <td>
                      {q.isDeferred ? (
                        <button type="button" className="secondary" onClick={() => void onUndefer(q.id)}>後回し解除</button>
                      ) : (
                        <button type="button" className="secondary" onClick={() => void onDefer(q.id)}>作業キューから後回し</button>
                      )}
                      <button type="button" onClick={() => void onGenerateDraft(q)} style={{ marginLeft: 8 }}>請求ドラフト生成</button>
                    </td>
                    <td>
                      {queueResultMessage[q.id] ?? ''}
                      {queueDraftInvoiceId[q.id] ? (
                        <>
                          {' '}
                          <Link to={`/invoices/drafts/${queueDraftInvoiceId[q.id]}`}>確認</Link>
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            顧客フィルター
            <input value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)} placeholder="例: テスト商事" />
          </label>
          <label className="filter-label">
            商品フィルター
            <input value={productFilter} onChange={(e) => setProductFilter(e.target.value)} placeholder="例: 鶏もも" />
          </label>
          <label className="filter-label">
            仕入先フィルター
            <input value={supplierFilter} onChange={(e) => setSupplierFilter(e.target.value)} placeholder="例: サプライヤA" />
          </label>
          <button type="button" className="secondary" onClick={() => { setCustomerFilter(''); setProductFilter(''); setSupplierFilter(''); }}>フィルター解除</button>
        </div>

        {rows.length === 0 ? (
          <EmptyState title="対象データがありません" description="一括割当で保存済み行が見つかりません。" actionLabel="再読み込み" onAction={load} />
        ) : sortedRows.length === 0 ? (
          <EmptyState title="対象データがありません" description="条件に合う行がありません。" actionLabel="条件をリセット" onAction={() => { setCustomerFilter(''); setProductFilter(''); setSupplierFilter(''); }} />
        ) : (
          <div className="table-wrap">
            <table className="purchase-result-table">
              <thead>
                <tr>
                  <th className="col-select">
                    <input type="checkbox" checked={selectVisibleChecked} onChange={(e) => toggleSelectVisible(e.target.checked)} />
                  </th>
                  <th className="col-order-no">注文番号</th>
                  <th className="col-customer" onClick={() => onSort('customerName')} style={{ cursor: 'pointer' }}>{sortLabel('customerName', '顧客')}</th>
                  <th className="col-product" onClick={() => onSort('productName')} style={{ cursor: 'pointer' }}>{sortLabel('productName', '商品')}</th>
                  <th className="col-supplier" onClick={() => onSort('supplierName')} style={{ cursor: 'pointer' }}>{sortLabel('supplierName', '仕入先')}</th>
                  <th className="col-ordered">受注数量</th>
                  <th className="col-invoice">請求数量</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((r, rowIndex) => {
                  const units = unitsByProductId[r.productId] ?? { orderUom: 'count', invoiceUom: 'count' };
                  const edit = editByItemId[r.orderItemId];
                  const supplierName = r.manualSupplierId ? supplierNameById.get(r.manualSupplierId) ?? `仕入先#${r.manualSupplierId}` : '-';

                  return (
                    <tr key={r.orderItemId}>
                      <td>
                        <input
                          type="checkbox"
                          checked={Boolean(edit?.selected)}
                          onClick={(e) => onRowCheckboxChange(r.orderItemId, !Boolean(edit?.selected), e.shiftKey)}
                          readOnly
                        />
                      </td>
                      <td className="col-order-no">
                        {r.orderId ? <Link to={`/orders/${r.orderId}/edit`} className="order-link">{r.orderNo}</Link> : r.orderNo}
                      </td>
                      <td className="col-customer">{r.customerName}</td>
                      <td className="col-product">{r.productName}</td>
                      <td className="col-supplier">{supplierName}</td>
                      <td className="col-ordered">{r.orderedQty} {units.orderUom}</td>
                      <td className="col-invoice">
                        <input
                          type="number"
                          min={0}
                          step="1"
                          data-invoice-row={rowIndex}
                          value={edit?.invoiceQty ?? ''}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], invoiceQty: e.target.value, rowError: undefined } }))}
                          onKeyDown={(e) => {
                            const moveDown = e.key === 'ArrowDown' || (e.key === 'Tab' && !e.shiftKey);
                            const moveUp = e.key === 'ArrowUp';
                            if (!moveDown && !moveUp) return;

                            const targetRow = moveUp ? rowIndex - 1 : rowIndex + 1;
                            const target = document.querySelector<HTMLInputElement>(`input[data-invoice-row="${targetRow}"]`);
                            if (!target) return;

                            e.preventDefault();
                            target.focus();
                          }}
                          placeholder=""
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
