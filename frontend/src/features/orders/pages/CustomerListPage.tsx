import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listCustomers } from 'features/orders/services/ordersService';
import type { CustomerOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const CustomerListPage = () => {
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    listCustomers()
      .then(setCustomers)
      .catch((e) => setError(toUserMessage(e, '顧客一覧の取得に失敗しました')));
  }, []);

  if (error) return <ErrorState title="顧客一覧の取得に失敗" description={error} />;
  if (!customers) return <LoadingState title="顧客一覧を読み込み中" />;
  if (customers.length === 0) return <EmptyState title="顧客データがありません" />;

  return (
    <section className="card">
      <div className="list-header">
        <div>
          <h2>顧客マスタ</h2>
          <p className="subtle">参照用（読み取り専用）</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>表示名</th>
              <th>詳細</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td>{c.label}</td>
                <td><Link to={`/customers/${c.id}`} className="order-link">詳細</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
