import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  bulkSaveOrderItemAllocations,
  listOrderItemAllocationWorkItems,
  listSupplierFilterOptions,
  suggestOrderItemAllocations,
  type OrderItemAllocationWorkItem,
  type SupplierFilterOption,
} from 'features/orders/services/orderItemAllocationsService';
import { toActionableMessage } from 'shared/error';

type RowEdit = {
  selected: boolean;
  manualSupplierId: number | null;
  manualQty: string;
  rowError?: string;
};

type SortKey = 'orderNo' | 'deliveryDate' | 'customerName' | 'productName' | 'manualSupplierId' | 'orderedQty' | 'manualQty' | 'shortageQty';

type SortState = {
  key: SortKey;
  direction: 'asc' | 'desc';
};

export const OrderItemBulkAllocationPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const [items, setItems] = useState<OrderItemAllocationWorkItem[]>([]);
  const [editById, setEditById] = useState<Record<number, RowEdit>>({});
  const [suppliers, setSuppliers] = useState<SupplierFilterOption[]>([]);
  const [lastSelectedId, setLastSelectedId] = useState<number | null>(null);

  const [unallocatedOnly, setUnallocatedOnly] = useState(false);
  const [deliveryDate, setDeliveryDate] = useState('');
  const [supplierId, setSupplierId] = useState<number | ''>('');
  const [productFilter, setProductFilter] = useState('');
  const [customerFilter, setCustomerFilter] = useState('');
  const [bulkSupplierId, setBulkSupplierId] = useState<number | ''>('');
  const [bulkSupplierQuery, setBulkSupplierQuery] = useState('');
  const [selectVisibleChecked, setSelectVisibleChecked] = useState(false);
  const [sort, setSort] = useState<SortState>({ key: 'deliveryDate', direction: 'asc' });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [rows, supplierOptions] = await Promise.all([
        listOrderItemAllocationWorkItems({
          unallocatedOnly,
          deliveryDate: deliveryDate || undefined,
          supplierId: supplierId || undefined,
        }),
        listSupplierFilterOptions(),
      ]);
      setItems(rows);
      setSuppliers(supplierOptions);
      setEditById((prev) =>
        Object.fromEntries(
          rows.map((row) => {
            const old = prev[row.orderItemId];
            return [
              row.orderItemId,
              {
                selected: old?.selected ?? false,
                manualSupplierId: old?.manualSupplierId ?? row.manualSupplierId,
                manualQty: old?.manualQty ?? (row.manualQty == null ? '' : String(row.manualQty)),
                rowError: old?.rowError,
              },
            ];
          }),
        ),
      );
    } catch (e) {
      setError(toActionableMessage(e, '受注アイテム一覧の取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [unallocatedOnly, deliveryDate, supplierId]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const filteredItems = useMemo(() => {
    const product = productFilter.trim().toLowerCase();
    const customer = customerFilter.trim().toLowerCase();

    return items.filter((row) => {
      if (product && !row.productName.toLowerCase().includes(product)) return false;
      if (customer && !row.customerName.toLowerCase().includes(customer)) return false;
      return true;
    });
  }, [items, productFilter, customerFilter]);

  const sortedItems = useMemo(() => {
    const rows = [...filteredItems];
    const getShortage = (row: OrderItemAllocationWorkItem) => {
      const manualQty = Number(editById[row.orderItemId]?.manualQty ?? row.manualQty ?? 0);
      const shortage = Math.max(row.orderedQty - (Number.isFinite(manualQty) ? manualQty : 0), 0);
      return Number(shortage.toFixed(3));
    };

    rows.sort((a, b) => {
      const aManualQty = Number(editById[a.orderItemId]?.manualQty ?? a.manualQty ?? 0);
      const bManualQty = Number(editById[b.orderItemId]?.manualQty ?? b.manualQty ?? 0);
      const aManualSupplier = Number(editById[a.orderItemId]?.manualSupplierId ?? 0);
      const bManualSupplier = Number(editById[b.orderItemId]?.manualSupplierId ?? 0);

      const compareMap: Record<SortKey, number> = {
        orderNo: a.orderNo.localeCompare(b.orderNo),
        deliveryDate: a.deliveryDate.localeCompare(b.deliveryDate),
        customerName: a.customerName.localeCompare(b.customerName),
        productName: a.productName.localeCompare(b.productName),
        manualSupplierId: aManualSupplier - bManualSupplier,
        orderedQty: a.orderedQty - b.orderedQty,
        manualQty: aManualQty - bManualQty,
        shortageQty: getShortage(a) - getShortage(b),
      };

      const base = compareMap[sort.key];
      return sort.direction === 'asc' ? base : -base;
    });

    return rows;
  }, [filteredItems, editById, sort]);

  const visibleIds = useMemo(() => sortedItems.map((row) => row.orderItemId), [sortedItems]);

  const tomorrowDateStr = useMemo(() => {
    const now = new Date();
    now.setDate(now.getDate() + 1);
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }, []);

  useEffect(() => {
    if (visibleIds.length === 0) {
      setSelectVisibleChecked(false);
      return;
    }
    const allSelected = visibleIds.every((id) => editById[id]?.selected);
    setSelectVisibleChecked(allSelected);
  }, [visibleIds, editById]);

  const onSort = (key: SortKey) => {
    setSort((prev) => {
      if (prev.key !== key) return { key, direction: 'asc' };
      return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
    });
  };

  const sortLabel = (key: SortKey, label: string) => {
    if (sort.key !== key) return label;
    return `${label} ${sort.direction === 'asc' ? '↑' : '↓'}`;
  };

  const applySuggestion = async () => {
    const targetIds = sortedItems.map((row) => row.orderItemId);
    if (targetIds.length === 0) return;

    try {
      const suggestions = await suggestOrderItemAllocations(targetIds);
      const map = new Map(suggestions.map((s) => [s.orderItemId, s]));
      setEditById((prev) => {
        const next = { ...prev };
        for (const s of suggestions) {
          if (!next[s.orderItemId]) continue;
          next[s.orderItemId] = {
            ...next[s.orderItemId],
            manualSupplierId: s.suggestedSupplierId,
            manualQty: s.suggestedQty == null ? '' : String(s.suggestedQty),
            rowError: undefined,
          };
        }
        return next;
      });
      setToast({ type: 'success', message: `自動提案を反映しました（${map.size}件）。` });
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '自動提案に失敗しました。') });
    }
  };

  const toggleSelectVisible = (checked: boolean) => {
    setEditById((prev) => {
      const next = { ...prev };
      for (const id of visibleIds) {
        if (!next[id]) continue;
        next[id] = { ...next[id], selected: checked };
      }
      return next;
    });
  };

  const applyBulkSupplier = () => {
    const selectedSupplierId = bulkSupplierId === '' ? null : Number(bulkSupplierId);

    setEditById((prev) => {
      const next = { ...prev };
      for (const row of sortedItems) {
        const current = next[row.orderItemId];
        if (!current?.selected) continue;
        next[row.orderItemId] = {
          ...current,
          manualSupplierId: selectedSupplierId,
          manualQty: selectedSupplierId == null ? '' : String(row.orderedQty),
          rowError: undefined,
        };
      }
      return next;
    });
    setToast({ type: 'success', message: selectedSupplierId == null ? '未選択（未割当へ戻す）を一括適用しました。' : '一括割当を反映しました。' });
  };


  const resetFilters = () => {
    setUnallocatedOnly(false);
    setDeliveryDate('');
    setSupplierId('');
    setProductFilter('');
    setCustomerFilter('');
  };

  const saveBulk = async () => {
    const selectedRows = sortedItems.filter((row) => editById[row.orderItemId]?.selected);
    const payload = selectedRows.map((row) => {
      const edit = editById[row.orderItemId];
      const supplierId = edit.manualSupplierId == null ? null : Number(edit.manualSupplierId);
      const allocatedQty = supplierId == null ? null : Number(edit.manualQty);
      return {
        orderItemId: row.orderItemId,
        supplierId,
        allocatedQty: Number.isFinite(allocatedQty as number) ? allocatedQty : null,
      };
    });

    if (payload.length === 0) {
      setToast({ type: 'error', message: '保存対象がありません。表示中の行を選択してください。' });
      return;
    }

    try {
      const result = await bulkSaveOrderItemAllocations(payload);
      const errorById = new Map(result.errors.map((e) => [e.orderItemId, `${e.code}: ${e.message}`]));
      setEditById((prev) => {
        const next = { ...prev };
        Object.entries(next).forEach(([id, row]) => {
          next[Number(id)] = { ...row, rowError: errorById.get(Number(id)) };
        });
        return next;
      });

      setToast(
        result.failed > 0
          ? { type: 'error', message: `一括保存は部分成功です（成功 ${result.succeeded} / 失敗 ${result.failed}）。` }
          : { type: 'success', message: `一括保存に成功しました（${result.succeeded}件）。` },
      );

      await load();
    } catch (e) {
      const base = toActionableMessage(e, '一括保存に失敗しました。');
      const extra = base.includes('422') || base.includes('validation')
        ? '未選択（割当解除）の保存に未対応のAPIの可能性があります。backendの一括解除対応を確認してください。'
        : '';
      setToast({ type: 'error', message: `${base}${extra ? ` ${extra}` : ''}`.trim() });
    }
  };

  const moveToPurchaseResult = () => {
    const selectedAllocationIds = sortedItems
      .filter((row) => editById[row.orderItemId]?.selected)
      .map((row) => row.allocationId)
      .filter((v): v is number => typeof v === 'number');

    sessionStorage.setItem('osv2_purchase_target_allocations', JSON.stringify(selectedAllocationIds));
    navigate('/purchases');
  };

  const onRowCheckboxChange = (orderItemId: number, checked: boolean, shiftKey: boolean) => {
    const targetIndex = sortedItems.findIndex((row) => row.orderItemId === orderItemId);

    setEditById((prev) => {
      const next = { ...prev };
      if (shiftKey && lastSelectedId != null) {
        const lastIndex = sortedItems.findIndex((row) => row.orderItemId === lastSelectedId);
        if (lastIndex >= 0 && targetIndex >= 0) {
          const [start, end] = lastIndex < targetIndex ? [lastIndex, targetIndex] : [targetIndex, lastIndex];
          for (let i = start; i <= end; i += 1) {
            const id = sortedItems[i].orderItemId;
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

  if (error) return <ErrorState title="受注アイテム一覧の取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  if (loading) return <LoadingState title="受注アイテム一括割当を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      {toast ? <div className={`toast toast-overlay ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>受注アイテム一括割当</h2>
            <p className="subtle">自動提案 → 手動修正 → 一括保存</p>
          </div>
          <div className="list-controls">
            <button type="button" className="secondary" onClick={() => void applySuggestion()}>自動提案を実行</button>
            <button type="button" onClick={() => void saveBulk()}>選択行を一括保存</button>
            <button type="button" className="secondary" onClick={moveToPurchaseResult}>保存済み行を納品確認へ進める</button>
          </div>
        </div>

        <div className="list-controls" style={{ marginBottom: 6 }}>
          <label className="filter-label">
            納品日
            <input type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
          </label>
          <label className="filter-label">
            仕入先
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">すべて</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </label>
          <label className="filter-label">
            <input type="checkbox" checked={unallocatedOnly} onChange={(e) => setUnallocatedOnly(e.target.checked)} />
            未割当てのみ表示
          </label>
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            商品名フィルター
            <input value={productFilter} onChange={(e) => setProductFilter(e.target.value)} placeholder="例: 鶏もも" />
          </label>
          <label className="filter-label">
            取引先フィルター
            <input value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)} placeholder="例: テスト商事" />
          </label>
          <button type="button" className="secondary" onClick={resetFilters}>フィルター解除</button>
          <div className="filter-gap" />
          <label className="filter-label">
            選択行へ一括仕入先適用（未選択=未割当へ戻す）
            <input
              list="supplier-bulk-options"
              value={bulkSupplierQuery}
              placeholder="仕入先を検索 / 未選択"
              onChange={(e) => {
                const q = e.target.value;
                setBulkSupplierQuery(q);
                if (q === '未選択') {
                  setBulkSupplierId('');
                  return;
                }
                const matched = suppliers.find((s) => s.label === q || q.startsWith(`${s.id}:`));
                setBulkSupplierId(matched ? matched.id : '');
              }}
            />
            <datalist id="supplier-bulk-options">
              <option value="未選択" />
              {suppliers.map((s) => <option key={s.id} value={s.label} />)}
            </datalist>
          </label>
          <button type="button" className="secondary" onClick={applyBulkSupplier}>一括割当</button>
        </div>

        <p className="subtle" style={{ marginBottom: 12 }}>※ ヘッダークリックで昇順/降順を切替。選択操作は表示中の行のみ対象。</p>

        {sortedItems.length === 0 ? (
          <EmptyState title="データがありません" description="条件に合う受注アイテムがありません。" actionLabel="再読み込み" onAction={load} />
        ) : (
          <div className="table-wrap">
            <table className="bulk-allocation-table">
              <thead>
                <tr>
                  <th>
                    <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input type="checkbox" checked={selectVisibleChecked} onChange={(e) => toggleSelectVisible(e.target.checked)} />
                      選択
                    </label>
                  </th>
                  <th className="col-order-no" onClick={() => onSort('orderNo')} style={{ cursor: 'pointer' }}>{sortLabel('orderNo', '注文番号')}</th>
                  <th className="col-delivery-date" onClick={() => onSort('deliveryDate')} style={{ cursor: 'pointer' }}>{sortLabel('deliveryDate', '納品日')}</th>
                  <th className="col-customer" onClick={() => onSort('customerName')} style={{ cursor: 'pointer' }}>{sortLabel('customerName', '顧客')}</th>
                  <th className="col-product" onClick={() => onSort('productName')} style={{ cursor: 'pointer' }}>{sortLabel('productName', '商品')}</th>
                  <th onClick={() => onSort('manualSupplierId')} style={{ cursor: 'pointer' }}>{sortLabel('manualSupplierId', '手動仕入先')}</th>
                  <th className="col-ordered-qty" onClick={() => onSort('orderedQty')} style={{ cursor: 'pointer' }}>{sortLabel('orderedQty', '受注数量')}</th>
                  <th className="col-allocated-qty" onClick={() => onSort('manualQty')} style={{ cursor: 'pointer' }}>{sortLabel('manualQty', '割当数')}</th>
                  <th className="col-shortage-qty" onClick={() => onSort('shortageQty')} style={{ cursor: 'pointer' }}>{sortLabel('shortageQty', '不足数')}</th>
                </tr>
              </thead>
              <tbody>
                {sortedItems.map((row) => {
                  const edit = editById[row.orderItemId];
                  const manualQtyNum = Number(edit?.manualQty ?? row.manualQty ?? 0);
                  const allocatedQty = Number.isFinite(manualQtyNum) ? manualQtyNum : 0;
                  const shortageQty = Number(Math.max(row.orderedQty - allocatedQty, 0).toFixed(3));

                  const hasManualSupplier = (edit?.manualSupplierId ?? row.manualSupplierId) != null;
                  const isNonTomorrow = row.deliveryDate !== tomorrowDateStr;

                  return (
                    <tr key={row.orderItemId} className={hasManualSupplier ? 'row-allocated' : 'row-unallocated'}>
                      <td>
                        <input
                          type="checkbox"
                          checked={Boolean(edit?.selected)}
                          onClick={(e) => {
                            const checked = !Boolean(edit?.selected);
                            onRowCheckboxChange(row.orderItemId, checked, e.shiftKey);
                          }}
                          readOnly
                        />
                      </td>
                      <td className="cell-order-no" title={row.orderNo}>
                        {row.orderId ? (
                          <Link to={`/orders/${row.orderId}/edit`} className="order-link text-ellipsis-inline" title={row.orderNo}>
                            {row.orderNo}
                          </Link>
                        ) : (
                          <span className="text-ellipsis-inline" title={row.orderNo}>{row.orderNo}</span>
                        )}
                      </td>
                      <td className={`col-delivery-date ${isNonTomorrow ? 'delivery-warning' : ''}`}>{row.deliveryDate}</td>
                      <td className="col-customer">{row.customerName}</td>
                      <td className="col-product">{row.productName}</td>
                      <td className={hasManualSupplier ? 'manual-supplier-marked' : ''}>
                        <select
                          value={edit?.manualSupplierId ?? ''}
                          onChange={(e) =>
                            setEditById((prev) => ({
                              ...prev,
                              [row.orderItemId]: {
                                ...prev[row.orderItemId],
                                manualSupplierId: e.target.value ? Number(e.target.value) : null,
                                rowError: undefined,
                              },
                            }))
                          }
                        >
                          <option value="">未選択（未割当）</option>
                          {suppliers.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                        </select>
                      </td>
                      <td className="col-ordered-qty">{row.orderedQty}</td>
                      <td className="col-allocated-qty">
                        <input
                          type="number"
                          min={0}
                          step="1"
                          value={edit?.manualQty ?? ''}
                          onChange={(e) =>
                            setEditById((prev) => ({
                              ...prev,
                              [row.orderItemId]: { ...prev[row.orderItemId], manualQty: e.target.value, rowError: undefined },
                            }))
                          }
                        />
                      </td>
                      <td className="col-shortage-qty">
                        {shortageQty > 0 ? <span className="field-error">{shortageQty}</span> : <span className="subtle">-</span>}
                        {edit?.rowError ? <div className="field-error">{edit.rowError}</div> : null}
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
