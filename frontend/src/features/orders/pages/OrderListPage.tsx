import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listOrders } from 'features/orders/services/ordersService';
import type { OrderStatus, OrderSummary } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

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
  const [toast, setToast] = useState<ToastPayload | null>(null);

  useEffect(() => {
    listOrders()
      .then((data) => {
        const sorted = [...data].sort((a, b) => b.id - a.id);
        setOrders(sorted);
      })
      .catch((e) => setError(toUserMessage(e, '一覧取得に失敗しました')));

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
    if (statusFilter === 'all') return orders;
    return orders.filter((order) => order.status === statusFilter);
  }, [orders, statusFilter]);

  if (error) {
    return <ErrorState title="注文一覧の取得に失敗" description={error} />;
  }

  if (!orders) {
    return <LoadingState title="注文一覧を読み込み中" description="しばらくお待ちください" />;
  }

  if (orders.length === 0) {
    return <EmptyState title="注文データがありません" description="まずは注文作成画面から登録してください" />;
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
      </div>

      {filteredOrders.length === 0 ? (
        <EmptyState title="条件に合う注文がありません" description="フィルタ条件を変更してください" />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>注文番号</th>
                <th>顧客</th>
                <th>納品日</th>
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
