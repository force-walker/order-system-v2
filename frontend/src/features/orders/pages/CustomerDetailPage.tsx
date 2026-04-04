import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getCustomerDetail } from 'features/orders/services/ordersService';
import type { CustomerDetail } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const CustomerDetailPage = () => {
  const { customerId } = useParams();
  const [customer, setCustomer] = useState<CustomerDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    const id = Number(customerId);
    if (!id) {
      setError('不正な顧客IDです');
      return;
    }
    getCustomerDetail(id)
      .then(setCustomer)
      .catch((e) => setError(toUserMessage(e, '顧客詳細の取得に失敗しました')));
  }, [customerId]);

  if (error) return <ErrorState title="顧客詳細の取得に失敗" description={error} />;
  if (customer === undefined) return <LoadingState title="顧客詳細を読み込み中" />;
  if (customer === null) return <EmptyState title="顧客が見つかりません" />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h2>顧客詳細</h2>
      </div>
      <dl className="kv-list">
        <div><dt>ID</dt><dd>{customer.id}</dd></div>
        <div><dt>顧客コード</dt><dd>{customer.customerCode}</dd></div>
        <div><dt>顧客名</dt><dd>{customer.name}</dd></div>
        <div><dt>状態</dt><dd>{customer.active ? '有効' : '無効'}</dd></div>
      </dl>
      <div className="detail-actions">
        <Link to="/customers" className="order-link">顧客一覧へ戻る</Link>
        <Link to={`/customers/${customer.id}/edit`} className="order-link">顧客を編集</Link>
      </div>
    </section>
  );
};
