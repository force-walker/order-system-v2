import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { bulkCancelOrders, listOrders } from 'features/orders/services/ordersService';
import type { OrderStatus, OrderSummary } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

const STATUS_LABEL: Record<OrderStatus, string> = {
  new: '新規',
  confirmed: '確定',
  allocated: '引当済',
  purchased: '仕入済',
  shipped: '出荷済',
  invoiced: '請求済',
  cancelled: '取消',
};

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

type RowSelect = Record<number, boolean>;

export const OrderListPage = () => {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | OrderStatus>('all');
  const [keyword, setKeyword] = useState('');
  const [sortMode, setSortMode] = useState<'newest' | 'deliveryAsc' | 'deliveryDesc'>('newest');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [staleOnly, setStaleOnly] = useState(false);
  const [selectedByOrderId, setSelectedByOrderId] = useState<RowSelect>({});
  const [lastSelectedOrderId, setLastSelectedOrderId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      const data = await listOrders(staleOnly);
      const sorted = [...data].sort((a, b) => b.id - a.id);
      setOrders(sorted);
      setSelectedByOrderId((prev) => Object.fromEntries(sorted.map((o) => [o.id, prev[o.id] ?? false])));
    } catch (e) {
      setError(toActionableMessage(e, '一覧取得に失敗しました'));
    }
  };

  useEffect(() => {
    void load();

    const raw = sessionStorage.getItem('osv2_toast');
    if (raw) {
      try {
        setToast(JSON.parse(raw) as ToastPayload);
      } catch {
        // noop
      } finally {
        sessionStorage.removeItem('osv2_toast');
      }
    }
  }, [staleOnly]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(t);
  }, [toast]);

  const filteredOrders = useMemo(() => {
    if (!orders) return [];

    const normalizedKeyword = keyword.trim().toLowerCase();

    const byStatus = statusFilter === 'all' ? orders : orders.filter((order) => order.status === statusFilter);

    const byKeyword =
      normalizedKeyword.length === 0
        ? byStatus
        : byStatus.filter((order) => {
            const target = `${order.orderNo} ${order.customerName}`.toLowerCase();
            return target.includes(normalizedKeyword);
          });

    const sorted = [...byKeyword];
    if (sortMode === 'deliveryAsc') {
      sorted.sort((a, b) => a.deliveryDate.localeCompare(b.deliveryDate));
    } else if (sortMode === 'deliveryDesc') {
      sorted.sort((a, b) => b.deliveryDate.localeCompare(a.deliveryDate));
    } else {
      sorted.sort((a, b) => b.id - a.id);
    }
    return sorted;
  }, [orders, statusFilter, keyword, sortMode]);

  const visibleIds = useMemo(() => filteredOrders.map((o) => o.id), [filteredOrders]);

  const headerChecked = useMemo(
    () => visibleIds.length > 0 && visibleIds.every((id) => selectedByOrderId[id]),
    [visibleIds, selectedByOrderId],
  );

  const toggleVisible = (checked: boolean) => {
    setSelectedByOrderId((prev) => {
      const next = { ...prev };
      for (const id of visibleIds) next[id] = checked;
      return next;
    });
  };

  const onRowSelect = (orderId: number, checked: boolean, shiftKey: boolean) => {
    const idx = filteredOrders.findIndex((o) => o.id === orderId);
    setSelectedByOrderId((prev) => {
      const next = { ...prev };
      if (shiftKey && lastSelectedOrderId != null) {
        const prevIdx = filteredOrders.findIndex((o) => o.id === lastSelectedOrderId);
        if (prevIdx >= 0 && idx >= 0) {
          const [start, end] = prevIdx < idx ? [prevIdx, idx] : [idx, prevIdx];
          for (let i = start; i <= end; i += 1) next[filteredOrders[i].id] = checked;
        }
      } else {
        next[orderId] = checked;
      }
      return next;
    });
    setLastSelectedOrderId(orderId);
  };

  const executeBulkCancel = async () => {
    const targetIds = visibleIds.filter((id) => selectedByOrderId[id]);
    if (targetIds.length === 0) {
      setToast({ type: 'error', message: '対象が選択されていません。' });
      return;
    }

    const confirmed = window.confirm(`選択した ${targetIds.length} 件を一括Cancelします。よろしいですか？`);
    if (!confirmed) return;

    setSubmitting(true);
    try {
      const result = await bulkCancelOrders(targetIds, 'stale_delivery');
      const reasonText = result.errors.slice(0, 3).map((e) => `#${e.orderId}: ${e.code}`).join(', ');
      setToast(
        result.failed > 0
          ? { type: 'error', message: `部分成功（成功 ${result.succeeded} / 失敗 ${result.failed}）。${reasonText}` }
          : { type: 'success', message: `${result.succeeded}件をCancelしました。` },
      );
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '一括Cancelに失敗しました。') });
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  }

  if (!orders) {
    return <LoadingState title="注文一覧を読み込み中" description="しばらくお待ちください" />;
  }

  if (orders.length === 0) {
    return <EmptyState title="データがありません" description="条件を見直すか、データ登録後に再度お試しください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;
  }

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
      <div className="list-header">
        <div>
          <h2>注文一覧</h2>
          <p className="subtle">新しい注文順で表示しています。</p>
        </div>
        <div className="list-controls">
          <button type="button" className="danger" onClick={() => void executeBulkCancel()} disabled={submitting}>
            {submitting ? 'Cancel実行中...' : '選択注文を一括Cancel'}
          </button>
        </div>
      </div>

      <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            検索
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="注文番号 / 顧客名"
            />
          </label>

          <label className="filter-label">
            状態フィルタ
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as 'all' | OrderStatus)}>
              <option value="all">すべて</option>
              <option value="new">新規</option>
              <option value="confirmed">確定</option>
              <option value="allocated">引当済</option>
              <option value="purchased">仕入済</option>
              <option value="shipped">出荷済</option>
              <option value="invoiced">請求済</option>
              <option value="cancelled">取消</option>
            </select>
          </label>

          <label className="filter-label">
            並び順
            <select value={sortMode} onChange={(e) => setSortMode(e.target.value as 'newest' | 'deliveryAsc' | 'deliveryDesc')}>
              <option value="newest">新しい注文順</option>
              <option value="deliveryAsc">納品日（顧客納品日） 昇順</option>
              <option value="deliveryDesc">納品日（顧客納品日） 降順</option>
            </select>
          </label>

          <label className="filter-label">
            <input type="checkbox" checked={staleOnly} onChange={(e) => setStaleOnly(e.target.checked)} />
            最新納品日より古い注文のみ表示
          </label>
        </div>

      {filteredOrders.length === 0 ? (
        <EmptyState title="データがありません" description="条件に合うデータがありません。検索・フィルタ条件を見直してください。" actionLabel="条件をリセット" onAction={() => { setKeyword(''); setStatusFilter('all'); setSortMode('newest'); setStaleOnly(false); }} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input type="checkbox" checked={headerChecked} onChange={(e) => toggleVisible(e.target.checked)} />
                </th>
                <th>ID</th>
                <th>注文番号</th>
                <th>顧客</th>
                <th>納品日（顧客納品日）</th>
                <th>状態</th>
                <th>アイテム数</th>
                <th>詳細</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map((order) => {
                const firstItem = order.items[0];
                return (
                  <tr key={order.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={Boolean(selectedByOrderId[order.id])}
                        onClick={(e) => onRowSelect(order.id, !Boolean(selectedByOrderId[order.id]), e.shiftKey)}
                        readOnly
                      />
                    </td>
                    <td>{order.id}</td>
                    <td>
                      <Link to={`/orders/${order.id}/edit`} className="order-link">{order.orderNo}</Link>
                    </td>
                    <td>{order.customerName}</td>
                    <td>{order.deliveryDate}</td>
                    <td>
                      <span className={`status-badge status-${order.status}`}>{STATUS_LABEL[order.status]}</span>
                    </td>
                    <td>{order.items.length}</td>
                    <td>
                      {firstItem ? (
                        <Link to={`/orders/${order.id}/items/${firstItem.id}`}>先頭アイテム</Link>
                      ) : (
                        <span>-</span>
                      )}
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
