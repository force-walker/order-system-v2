import type { EntityId } from 'shared/entityId';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
  type OrderItemAllocationWorkItem,
  type SupplierFilterOption,
} from 'features/orders/services/orderItemAllocationsService';
import {
  bulkUpsertPurchaseResults,
  listPurchaseResults,
} from 'features/orders/services/purchaseService';
import type { OrderStatus, PurchaseResultItem } from 'features/orders/types/order';
import { getDefaultDeliveryDate } from 'features/orders/utils/deliveryDate';
import { getProductDetail } from 'features/products/services/productsService';
import { toActionableMessage } from 'shared/error';

type RowEdit = {
  selected: boolean;
  purchaseUnitCost: string;
  actualQty: string;
  rowError?: string;
};

type UnitPair = {
  orderUom: string;
  purchaseUom: string;
  invoiceUom: string;
  isCatchWeight: boolean;
  weightCaptureRequired: boolean;
};

type SortKey = 'customerName' | 'productName' | 'supplierName';
type SortDirection = 'asc' | 'desc';
const PURCHASE_TARGET_ALLOCATIONS_KEY = 'osv2_purchase_target_allocations';
const DEFAULT_PURCHASE_ORDER_STATUSES: OrderStatus[] = ['allocated', 'purchased'];

const consumePurchaseTargetAllocationIds = (): number[] | null => {
  const raw = sessionStorage.getItem(PURCHASE_TARGET_ALLOCATIONS_KEY);
  sessionStorage.removeItem(PURCHASE_TARGET_ALLOCATIONS_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    const ids = Array.from(new Set(parsed.filter((value): value is number => Number.isInteger(value) && value > 0)));
    return ids.length > 0 ? ids : null;
  } catch {
    return null;
  }
};

export const PurchasePage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [rows, setRows] = useState<OrderItemAllocationWorkItem[]>([]);
  const [purchaseResultByAllocationId, setPurchaseResultByAllocationId] = useState<Record<number, PurchaseResultItem>>({});
  const [suppliers, setSuppliers] = useState<SupplierFilterOption[]>([]);
  const [unitsByProductId, setUnitsByProductId] = useState<Record<number, UnitPair>>({});
  const [editByItemId, setEditByItemId] = useState<Record<EntityId, RowEdit>>({});
  const [saving, setSaving] = useState(false);
  const [customerFilter, setCustomerFilter] = useState('');
  const [productFilter, setProductFilter] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('customerName');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [lastSelectedId, setLastSelectedId] = useState<EntityId | null>(null);
  const [deliveryDate, setDeliveryDate] = useState(getDefaultDeliveryDate);
  const [orderStatuses, setOrderStatuses] = useState<OrderStatus[]>(DEFAULT_PURCHASE_ORDER_STATUSES);
  const [targetAllocationIds, setTargetAllocationIds] = useState<number[] | null>(null);
  const targetAllocationIdsRef = useRef<number[] | null>(null);
  const handoffConsumedRef = useRef(false);

  const supplierNameById = useMemo(() => {
    const map = new Map<number, string>();
    suppliers.forEach((s) => {
      const name = s.label.includes(':') ? s.label.split(':').slice(1).join(':').trim() : s.label;
      map.set(s.id, name);
    });
    return map;
  }, [suppliers]);

  const load = async () => {
    if (!handoffConsumedRef.current) {
      handoffConsumedRef.current = true;
      const consumedIds = consumePurchaseTargetAllocationIds();
      targetAllocationIdsRef.current = consumedIds;
      setTargetAllocationIds(consumedIds);
    }

    setLoading(true);
    setError('');
    try {
      const [all, supplierOptions, persisted] = await Promise.all([
        listOrderItemAllocationWorkItems({ unallocatedOnly: false, deliveryDate, orderStatuses }),
        listSupplierFilterOptions(),
        listPurchaseResults({ limit: 500, offset: 0 }),
      ]);
      setSuppliers(supplierOptions);

      const unitCostByAllocationId = new Map<number, number | undefined>();
      const persistedByAllocationId: Record<number, PurchaseResultItem> = {};
      persisted.items.forEach((q) => {
        unitCostByAllocationId.set(q.allocationId, q.unitCost);
        persistedByAllocationId[q.allocationId] = q;
      });
      setPurchaseResultByAllocationId(persistedByAllocationId);

      const allocated = all.filter((r) => r.allocationStatus === 'allocated' && r.allocationId != null);
      const validAllocationIds = new Set(
        allocated
          .map((row) => row.allocationId)
          .filter((allocationId): allocationId is number => typeof allocationId === 'number'),
      );
      const requestedIds = targetAllocationIdsRef.current;
      if (requestedIds?.some((allocationId) => !validAllocationIds.has(allocationId))) {
        targetAllocationIdsRef.current = null;
        setTargetAllocationIds(null);
      }

      setRows(allocated);

      const productIds = [...new Set(allocated.map((r) => r.productId))];
      const unitEntries = await Promise.all(
        productIds.map(async (productId) => {
          try {
            const p = await getProductDetail(productId);
            if (!p) throw new Error('product not found');
            return [productId, {
              orderUom: p.orderUom,
              purchaseUom: p.purchaseUom,
              invoiceUom: p.invoiceUom,
              isCatchWeight: p.isCatchWeight,
              weightCaptureRequired: p.weightCaptureRequired,
            }] as const;
          } catch {
            return [productId, { orderUom: 'count', purchaseUom: 'count', invoiceUom: 'count', isCatchWeight: false, weightCaptureRequired: false }] as const;
          }
        }),
      );
      const unitsByProductIdLocal = Object.fromEntries(unitEntries);
      setUnitsByProductId(unitsByProductIdLocal);

      setEditByItemId((prev) =>
        Object.fromEntries(
          allocated.map((r) => {
            const persistedResult = typeof r.allocationId === 'number' ? persistedByAllocationId[r.allocationId] : undefined;
            const restoredActualQty = r.pricingBasis === 'uom_kg'
              ? persistedResult?.actualWeightKg ?? persistedResult?.purchasedQty
              : persistedResult?.purchasedQty;
            const restoredUnitCost = typeof r.allocationId === 'number' ? unitCostByAllocationId.get(r.allocationId) : undefined;
            return [
              r.orderItemId,
              {
                selected: prev[r.orderItemId]?.selected ?? false,
                purchaseUnitCost: prev[r.orderItemId]?.purchaseUnitCost ?? (restoredUnitCost != null ? String(restoredUnitCost) : ''),
                actualQty: prev[r.orderItemId]?.actualQty ?? String(restoredActualQty ?? r.manualQty ?? r.orderedQty),
                rowError: undefined,
              },
            ];
          }),
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
  }, [deliveryDate, orderStatuses]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const handoffRows = useMemo(() => {
    if (!targetAllocationIds) return rows;
    const targetIds = new Set(targetAllocationIds);
    return rows.filter((row) => typeof row.allocationId === 'number' && targetIds.has(row.allocationId));
  }, [rows, targetAllocationIds]);

  const clearHandoffFilter = () => {
    targetAllocationIdsRef.current = null;
    setTargetAllocationIds(null);
  };

  const toggleOrderStatus = (status: OrderStatus) => {
    setOrderStatuses((current) => {
      if (!current.includes(status)) return [...current, status];
      return current.length === 1 ? current : current.filter((candidate) => candidate !== status);
    });
  };

  const filteredRows = useMemo(() => {
    const customerQ = customerFilter.trim().toLowerCase();
    const productQ = productFilter.trim().toLowerCase();
    const supplierQ = supplierFilter.trim().toLowerCase();

    return handoffRows.filter((r) => {
      const supplierName = r.manualSupplierId ? supplierNameById.get(r.manualSupplierId) ?? `仕入先#${r.manualSupplierId}` : '';
      if (customerQ && !r.customerName.toLowerCase().includes(customerQ)) return false;
      if (productQ && !r.productName.toLowerCase().includes(productQ)) return false;
      if (supplierQ && !supplierName.toLowerCase().includes(supplierQ)) return false;
      return true;
    });
  }, [handoffRows, customerFilter, productFilter, supplierFilter, supplierNameById]);

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

  const onRowCheckboxChange = (orderItemId: EntityId, checked: boolean, shiftKey: boolean) => {
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

  const selectedCount = useMemo(() => handoffRows.filter((r) => editByItemId[r.orderItemId]?.selected).length, [handoffRows, editByItemId]);

  const saveBulk = async () => {
    const selectedRows = handoffRows.filter((r) => editByItemId[r.orderItemId]?.selected);
    if (selectedRows.length === 0) {
      setToast({ type: 'error', message: '保存対象がありません。行を選択してください。' });
      return;
    }

    const payload = selectedRows.map((r) => {
      const edit = editByItemId[r.orderItemId];
      const units = unitsByProductId[r.productId] ?? { orderUom: 'count', purchaseUom: 'count', invoiceUom: 'count', isCatchWeight: false, weightCaptureRequired: false };
      const actualQtyText = edit.actualQty.trim();
      const actualQty = actualQtyText === '' ? Number.NaN : Number(actualQtyText);
      const actualWeightKg = r.pricingBasis === 'uom_kg' ? actualQty : undefined;
      const unitCostText = edit.purchaseUnitCost.trim();
      const unitCost = unitCostText === '' ? undefined : Number(unitCostText);
      const expectedQty = Number(r.manualQty ?? 0);
      const shortage = Math.max(expectedQty - actualQty, 0);
      return {
        orderItemId: r.orderItemId,
        row: {
          allocationId: Number(r.allocationId),
          supplierId: r.manualSupplierId ?? undefined,
          purchasedQty: actualQty,
          purchasedUom: units.purchaseUom,
          unitCost,
          actualWeightKg,
          shortageQty: shortage > 0 ? shortage : undefined,
          resultStatus: actualQty < expectedQty ? ('partially_filled' as const) : ('filled' as const),
          invoiceableFlag: true,
        },
      };
    });

    const invalid = payload.filter((p) => {
      if (!Number.isFinite(p.row.purchasedQty) || p.row.purchasedQty < 0) return true;

      const unitCostRaw = editByItemId[p.orderItemId]?.purchaseUnitCost ?? '';
      if (unitCostRaw.trim() !== '') {
        const parsedUnitCost = Number(unitCostRaw);
        if (Number.isNaN(parsedUnitCost) || parsedUnitCost < 0) return true;
      }

      const actualQtyRaw = editByItemId[p.orderItemId]?.actualQty ?? '';
      const workItem = selectedRows.find((row) => row.orderItemId === p.orderItemId);
      if (!workItem || actualQtyRaw.trim() === '') return true;
      const parsed = Number(actualQtyRaw);
      if (Number.isNaN(parsed) || parsed < 0) return true;
      if (workItem.pricingBasis === 'uom_kg' && parsed <= 0) return true;
      return false;
    });
    if (invalid.length > 0) {
      setToast({ type: 'error', message: '実数量の数値入力を確認してください。' });
      return;
    }


    const changes = payload.flatMap(({ row, orderItemId }) => {
      const persisted = purchaseResultByAllocationId[row.allocationId];
      if (!persisted) return [];
      const lines: string[] = [];
      if (persisted.purchasedQty !== row.purchasedQty) lines.push(`実数量: ${persisted.purchasedQty} ${persisted.purchasedUom} → ${row.purchasedQty} ${row.purchasedUom}`);
      if ((persisted.actualWeightKg ?? undefined) !== row.actualWeightKg) lines.push(`請求重量同期値: ${persisted.actualWeightKg ?? '-'} KG → ${row.actualWeightKg ?? '-'} KG`);
      if ((persisted.unitCost ?? undefined) !== row.unitCost) lines.push(`仕入単価: ${persisted.unitCost ?? '-'} → ${row.unitCost ?? '-'}`);
      if (lines.length > 0 && persisted.invoiceQty != null) {
        return [{ orderItemId, locked: true, lines }];
      }
      return lines.length > 0 ? [{ orderItemId, locked: false, lines }] : [];
    });
    if (changes.some((change) => change.locked)) {
      setToast({ type: 'error', message: '請求ドラフトで使用済みのため変更できません。' });
      return;
    }
    const changeLines = changes.flatMap((change) => change.lines);
    if (changeLines.length > 0 && !window.confirm(`保存済みの仕入結果が変更されています。\n\n${changeLines.join('\n')}\n\n上書きして保存しますか？`)) return;

    setSaving(true);
    try {
      const upserted = await bulkUpsertPurchaseResults(payload.map((p) => p.row));
      setToast({ type: 'success', message: `納品確認を保存しました（${upserted.count}件）。完了した注文は請求ドラフト候補に移動します。` });
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

        {targetAllocationIds ? (
          <div className="filter-summary" role="status" style={{ marginBottom: 12 }}>
            <span>一括割当から選択した {targetAllocationIds.length} 件を表示中</span>
            <button type="button" className="secondary" onClick={clearHandoffFilter}>全件表示</button>
          </div>
        ) : null}

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            納品日
            <input type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} />
          </label>
          <fieldset className="status-filter-group">
            <legend>注文状態</legend>
            {(['allocated', 'purchased'] as OrderStatus[]).map((status) => (
              <label key={status}>
                <input type="checkbox" checked={orderStatuses.includes(status)} onChange={() => toggleOrderStatus(status)} />
                {status === 'allocated' ? 'Allocated' : 'Purchased'}
              </label>
            ))}
          </fieldset>
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
                  <th className="col-invoice">実数量</th>
                  <th className="col-unit-cost">仕入単価</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="subtle">
                      {handoffRows.length === 0 ? '一括割当で保存済み行が見つかりません。' : '条件に合う行がありません。'}
                    </td>
                  </tr>
                ) : sortedRows.map((r, rowIndex) => {
                  const units = unitsByProductId[r.productId] ?? { orderUom: 'count', purchaseUom: 'count', invoiceUom: 'count', isCatchWeight: false, weightCaptureRequired: false };
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
                          inputMode="decimal"
                          min={0}
                          step="0.001"
                          data-actual-qty-row={rowIndex}
                          aria-label={`${r.productName} 実数量`}
                          value={edit?.actualQty ?? ''}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], actualQty: e.target.value, rowError: undefined } }))}
                          onKeyDown={(e) => {
                            const native = e.nativeEvent as KeyboardEvent;
                            const isComposing = native.isComposing || native.keyCode === 229;
                            if (isComposing) return;

                            const moveDown =
                              e.key === 'ArrowDown' ||
                              (e.key === 'Tab' && !e.shiftKey) ||
                              e.key === 'Enter';
                            const moveUp = e.key === 'ArrowUp' || (e.key === 'Tab' && e.shiftKey);
                            if (!moveDown && !moveUp) return;

                            const targetRow = moveUp ? rowIndex - 1 : rowIndex;
                            const target = document.querySelector<HTMLInputElement>(`input[data-unitcost-row="${targetRow}"]`);
                            if (!target) return;

                            e.preventDefault();
                            target.focus();
                          }}
                          placeholder=""
                        /> <span className="subtle">{units.purchaseUom}</span>
                      </td>
                      <td className="col-unit-cost">
                        <input
                          type="number"
                          inputMode="decimal"
                          min={0}
                          step="0.01"
                          data-unitcost-row={rowIndex}
                          value={edit?.purchaseUnitCost ?? ''}
                          onChange={(e) => setEditByItemId((prev) => ({ ...prev, [r.orderItemId]: { ...prev[r.orderItemId], purchaseUnitCost: e.target.value, rowError: undefined } }))}
                          onKeyDown={(e) => {
                            const native = e.nativeEvent as KeyboardEvent;
                            const isComposing = native.isComposing || native.keyCode === 229;
                            if (isComposing) return;

                            const moveDown =
                              e.key === 'ArrowDown' ||
                              (e.key === 'Tab' && !e.shiftKey) ||
                              e.key === 'Enter';
                            const moveUp = e.key === 'ArrowUp' || (e.key === 'Tab' && e.shiftKey);
                            if (!moveDown && !moveUp) return;

                            const targetRow = moveDown ? rowIndex + 1 : rowIndex;
                            const target = document.querySelector<HTMLInputElement>(`input[data-actual-qty-row="${targetRow}"]`);
                            if (!target) return;

                            e.preventDefault();
                            target.focus();
                          }}
                          placeholder=""
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
        </div>
      </div>
    </section>
  );
};
