import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listOrders } from 'features/orders/services/ordersService';
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

export const OrderListPage = () => {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | OrderStatus>('all');
  const [keyword, setKeyword] = useState('');
  const [sortMode, setSortMode] = useState<'newest' | 'deliveryAsc' | 'deliveryDesc'>('newest');
  const [toast, setToast] = useState<ToastPayload | null>(null);

  useEffect(() => {
    listOrders()
      .then((data) => {
        const sorted = [...data].sort((a, b) => b.id - a.id);
        setOrders(sorted);
      })
      .catch((e) => setError(toActionableMessage(e, '一覧取得に失敗しました')));

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
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3500);
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
        </div>
      </div>

      {filteredOrders.length === 0 ? (
        <EmptyState title="データがありません" description="条件に合うデータがありません。検索・フィルタ条件を見直してください。" actionLabel="条件をリセット" onAction={() => { setKeyword(''); setStatusFilter('all'); setSortMode('newest'); }} />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
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
