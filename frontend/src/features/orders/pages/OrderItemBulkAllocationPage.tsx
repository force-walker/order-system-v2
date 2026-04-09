import { useEffect, useMemo, useState } from 'react';
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

const statusLabel = (v: string) => (v === 'allocated' ? '割当済' : '未割当');

export const OrderItemBulkAllocationPage = () => {
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
  const [selectVisibleChecked, setSelectVisibleChecked] = useState(false);

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

  const visibleIds = useMemo(() => filteredItems.map((row) => row.orderItemId), [filteredItems]);

  useEffect(() => {
    if (visibleIds.length === 0) {
      setSelectVisibleChecked(false);
      return;
    }
    const allSelected = visibleIds.every((id) => editById[id]?.selected);
    setSelectVisibleChecked(allSelected);
  }, [visibleIds, editById]);

  const applySuggestion = async () => {
    const targetIds = filteredItems.map((row) => row.orderItemId);
    if (targetIds.length === 0) return;

    try {
      const suggestions = await suggestOrderItemAllocations(targetIds);
      const map = new Map(suggestions.map((s) => [s.orderItemId, s]));

      setItems((prev) =>
        prev.map((row) => {
          const s = map.get(row.orderItemId);
          if (!s) return row;
          return {
            ...row,
            proposedSupplierId: s.suggestedSupplierId,
            proposedQty: s.suggestedQty,
            manualSupplierId: s.suggestedSupplierId,
            manualQty: s.suggestedQty,
          };
        }),
      );

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

      setToast({ type: 'success', message: '自動提案を反映しました。必要に応じて手動修正してください。' });
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
    if (!bulkSupplierId) return;
    setEditById((prev) => {
      const next = { ...prev };
      for (const row of filteredItems) {
        const current = next[row.orderItemId];
        if (!current?.selected) continue;
        next[row.orderItemId] = {
          ...current,
          manualSupplierId: Number(bulkSupplierId),
          manualQty: String(row.orderedQty),
          rowError: undefined,
        };
      }
      return next;
    });
    setToast({ type: 'success', message: '選択行に仕入先を適用し、数量を受注数量で自動セットしました（ローカル同期）。' });
  };

  const clearSelectedRows = () => {
    setEditById((prev) => {
      const next = { ...prev };
      for (const id of visibleIds) {
        const current = next[id];
        if (!current?.selected) continue;
        next[id] = {
          ...current,
          selected: false,
        };
      }
      return next;
    });
    setToast({ type: 'success', message: '表示中の選択行を解除しました。仕入先/数量の入力値は保持しています。' });
  };

  const resetFilters = () => {
    setUnallocatedOnly(false);
    setDeliveryDate('');
    setSupplierId('');
    setProductFilter('');
    setCustomerFilter('');
  };

  const saveBulk = async () => {
    const payload = filteredItems
      .filter((row) => editById[row.orderItemId]?.selected)
      .map((row) => {
        const edit = editById[row.orderItemId];
        return {
          orderItemId: row.orderItemId,
          supplierId: Number(edit.manualSupplierId),
          allocatedQty: Number(edit.manualQty),
        };
      })
      .filter((row) => Number.isFinite(row.supplierId) && row.supplierId > 0 && Number.isFinite(row.allocatedQty) && row.allocatedQty > 0);

    if (payload.length === 0) {
      setToast({ type: 'error', message: '保存対象がありません。表示中の行を選択し、仕入先/数量を入力してください。' });
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

      if (result.failed > 0) {
        setToast({
          type: 'error',
          message: `一括保存は部分成功です（成功 ${result.succeeded} / 失敗 ${result.failed}）。失敗行を修正してください。`,
        });
      } else {
        setToast({ type: 'success', message: `一括保存に成功しました（${result.succeeded}件）。` });
      }

      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '一括保存に失敗しました。') });
    }
  };

  const onRowCheckboxChange = (orderItemId: number, checked: boolean, shiftKey: boolean) => {
    const targetIndex = filteredItems.findIndex((row) => row.orderItemId === orderItemId);

    setEditById((prev) => {
      const next = { ...prev };

      if (shiftKey && lastSelectedId != null) {
        const lastIndex = filteredItems.findIndex((row) => row.orderItemId === lastSelectedId);
        if (lastIndex >= 0 && targetIndex >= 0) {
          const [start, end] = lastIndex < targetIndex ? [lastIndex, targetIndex] : [targetIndex, lastIndex];
          for (let i = start; i <= end; i += 1) {
            const id = filteredItems[i].orderItemId;
            if (!next[id]) continue;
            next[id] = { ...next[id], selected: checked };
          }
        }
      } else {
        if (next[orderItemId]) {
          next[orderItemId] = { ...next[orderItemId], selected: checked };
        }
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
            未割当てのみ（割当未設定行のみ表示）
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
          <button type="button" className="secondary" onClick={resetFilters}>全フィルター解除</button>
        </div>

        <p className="subtle" style={{ marginBottom: 12 }}>※ 一括選択/解除は「現在表示中の行」にのみ作用します。非表示行の選択状態は変更しません。</p>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            選択行へ一括仕入先適用
            <select value={bulkSupplierId} onChange={(e) => setBulkSupplierId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">選択してください</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </label>
          <button type="button" className="secondary" onClick={applyBulkSupplier} disabled={!bulkSupplierId}>選択行に仕入先を適用（数量は受注数量を自動セット）</button>
          <button type="button" className="secondary" onClick={clearSelectedRows}>選択解除</button>
        </div>

        {filteredItems.length === 0 ? (
          <EmptyState title="データがありません" description="条件に合う受注アイテムがありません。" actionLabel="再読み込み" onAction={load} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input
                        type="checkbox"
                        checked={selectVisibleChecked}
                        onChange={(e) => toggleSelectVisible(e.target.checked)}
                      />
                      選択
                    </label>
                  </th>
                  <th>注文番号</th>
                  <th>顧客</th>
                  <th>商品</th>
                  <th>受注数量</th>
                  <th>納品日</th>
                  <th>提案仕入先</th>
                  <th>提案数量</th>
                  <th>手動仕入先</th>
                  <th>手動数量</th>
                  <th>状態</th>
                  <th>失敗理由</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((row) => {
                  const edit = editById[row.orderItemId];
                  return (
                    <tr key={row.orderItemId}>
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
                      <td>{row.orderNo}</td>
                      <td>{row.customerName}</td>
                      <td>{row.productName}</td>
                      <td>{row.orderedQty}</td>
                      <td>{row.deliveryDate}</td>
                      <td>{row.proposedSupplierId ?? '-'}</td>
                      <td>{row.proposedQty ?? '-'}</td>
                      <td>
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
                          <option value="">選択</option>
                          {suppliers.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                        </select>
                      </td>
                      <td>
                        <input
                          type="number"
                          min={0}
                          step="0.001"
                          value={edit?.manualQty ?? ''}
                          onChange={(e) =>
                            setEditById((prev) => ({
                              ...prev,
                              [row.orderItemId]: { ...prev[row.orderItemId], manualQty: e.target.value, rowError: undefined },
                            }))
                          }
                        />
                      </td>
                      <td>{statusLabel(row.allocationStatus)}</td>
                      <td className="field-error">{edit?.rowError ?? '-'}</td>
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
