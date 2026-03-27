import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listOrders } from 'features/orders/services/ordersService';
import type { OrderSummary } from 'features/orders/types/order';

export const OrderListPage = () => {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    listOrders()
      .then((data) => setOrders(data))
      .catch(() => setError('一覧取得に失敗しました'));
  }, []);

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
    <section className="card">
      <h2>注文一覧</h2>
      <table>
        <thead>
          <tr>
            <th>注文番号</th>
            <th>顧客</th>
            <th>納品日</th>
            <th>状態</th>
            <th>アイテム詳細</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => {
            const firstItem = order.items[0];
            return (
              <tr key={order.id}>
                <td>{order.orderNo}</td>
                <td>{order.customerName}</td>
                <td>{order.deliveryDate}</td>
                <td>{order.status}</td>
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
    </section>
  );
};
