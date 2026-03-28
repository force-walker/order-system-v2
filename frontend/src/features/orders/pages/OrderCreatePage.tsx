import { useEffect, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { OrderForm } from 'features/orders/components/OrderForm';
import { createOrder, listCustomers, listProducts } from 'features/orders/services/ordersService';
import type { CustomerOption, ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';
import { useNavigate } from 'react-router-dom';

export const OrderCreatePage = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([listCustomers(), listProducts()])
      .then(([customerRows, productRows]) => {
        setCustomers(customerRows);
        setProducts(productRows);
      })
      .catch((e) => setError(toUserMessage(e, 'マスタ情報の取得に失敗しました')));
  }, []);

  const handleSubmit = async (payload: Parameters<typeof createOrder>[0]) => {
    await createOrder(payload);
    navigate('/orders');
  };

  if (error) return <ErrorState title="注文作成を開始できません" description={error} />;
  if (!customers || !products) return <LoadingState title="注文作成フォームを準備中" description="顧客・商品マスタを読み込んでいます" />;
  if (customers.length === 0) return <EmptyState title="顧客データがありません" description="顧客マスタ登録後に再度お試しください" />;
  if (products.length === 0) return <EmptyState title="商品データがありません" description="商品マスタ登録後に再度お試しください" />;

  return (
    <section>
      <OrderForm onSubmit={handleSubmit} customers={customers} products={products} />
    </section>
  );
};
