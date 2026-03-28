import { useEffect, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { OrderForm } from 'features/orders/components/OrderForm';
import { createOrder, listCustomers } from 'features/orders/services/ordersService';
import type { CustomerOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';
import { useNavigate } from 'react-router-dom';

export const OrderCreatePage = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    listCustomers()
      .then((rows) => setCustomers(rows))
      .catch((e) => setError(toUserMessage(e, '顧客一覧の取得に失敗しました')));
  }, []);

  const handleSubmit = async (payload: Parameters<typeof createOrder>[0]) => {
    await createOrder(payload);
    navigate('/orders');
  };

  if (error) {
    return <ErrorState title="注文作成を開始できません" description={error} />;
  }

  if (!customers) {
    return <LoadingState title="注文作成フォームを準備中" description="顧客マスタを読み込んでいます" />;
  }

  if (customers.length === 0) {
    return <EmptyState title="顧客データがありません" description="顧客マスタ登録後に再度お試しください" />;
  }

  return (
    <section>
      <OrderForm onSubmit={handleSubmit} customers={customers} />
    </section>
  );
};
