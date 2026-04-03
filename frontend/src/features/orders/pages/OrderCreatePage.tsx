import { useEffect, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { OrderForm } from 'features/orders/components/OrderForm';
import { createOrder, listCustomers, listProducts } from 'features/orders/services/ordersService';
import type { CustomerOption, ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

type CheckResult = {
  health: string;
  customers: string;
};

export const OrderCreatePage = () => {
  const navigate = useNavigate();
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [error, setError] = useState('');
  const [checkResult, setCheckResult] = useState<CheckResult | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    Promise.all([listCustomers(), listProducts()])
      .then(([customerRows, productRows]) => {
        setCustomers(customerRows);
        setProducts(productRows);
      })
      .catch((e) => setError(toUserMessage(e, 'マスタ情報の取得に失敗しました')));
  }, []);

  const runConnectivityCheck = async () => {
    setChecking(true);
    try {
      const healthRes = await fetch(`${API_BASE_URL}/health`);
      const customerRes = await fetch(`${API_BASE_URL}/api/v1/customers`, { method: 'GET' });
      setCheckResult({
        health: `health: ${healthRes.status}`,
        customers: `customers: ${customerRes.status}`,
      });
    } catch {
      setCheckResult({
        health: 'health: fetch failed',
        customers: 'customers: fetch failed',
      });
    } finally {
      setChecking(false);
    }
  };

  const handleSubmit = async (payload: Parameters<typeof createOrder>[0]) => {
    const created = await createOrder(payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `注文を保存しました（ID: ${created.id}）` }));
    navigate('/orders');
  };

  if (error) return <ErrorState title="注文作成を開始できません" description={error} />;
  if (!customers || !products) return <LoadingState title="注文作成フォームを準備中" description="顧客・商品マスタを読み込んでいます" />;
  if (customers.length === 0) return <EmptyState title="顧客データがありません" description="顧客マスタ登録後に再度お試しください" />;
  if (products.length === 0) return <EmptyState title="商品データがありません" description="商品マスタ登録後に再度お試しください" />;

  return (
    <section>
      <div className="card" style={{ marginBottom: 12 }}>
        <button type="button" className="secondary" onClick={runConnectivityCheck} disabled={checking}>
          {checking ? '接続確認中...' : '接続確認'}
        </button>
        {checkResult ? (
          <p className="subtle">
            {checkResult.health} / {checkResult.customers}
          </p>
        ) : null}
      </div>
      <OrderForm onSubmit={handleSubmit} customers={customers} products={products} />
    </section>
  );
};
