import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { OrderForm } from 'features/orders/components/OrderForm';
import { getOrder, listCustomers, listProducts, updateOrder } from 'features/orders/services/ordersService';
import type { CreateOrderRequest, CustomerOption, ProductOption } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

export const OrderEditPage = () => {
  const { orderId } = useParams();
  const navigate = useNavigate();

  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [initialValue, setInitialValue] = useState<CreateOrderRequest | null>(null);
  const [error, setError] = useState('');

  const orderIdNum = useMemo(() => Number(orderId), [orderId]);

  useEffect(() => {
    if (!orderIdNum) {
      setError('不正な注文IDです');
      return;
    }

    Promise.all([listCustomers(), listProducts(), getOrder(orderIdNum)])
      .then(([customerRows, productRows, order]) => {
        setCustomers(customerRows);
        setProducts(productRows);

        if (!order) {
          setInitialValue(null);
          return;
        }

        setInitialValue({
          orderNo: order.orderNo,
          customerId: order.customerId ?? 0,
          customerName: order.customerName,
          deliveryDate: order.deliveryDate,
          note: order.note,
          items: order.items.map((i) => ({
            id: i.id,
            productId: i.productId,
            productName: i.productName,
            quantity: i.quantity,
            unit: i.unit,
            unitPrice: i.unitPrice ?? 0,
            pricingBasis: i.pricingBasis ?? 'uom_count',
            estimatedWeightKg: i.estimatedWeightKg,
            targetPrice: i.targetPrice,
            priceCeiling: i.priceCeiling,
            stockoutPolicy: i.stockoutPolicy,
            comment: i.comment,
          })),
        });
      })
      .catch((e) => setError(toActionableMessage(e, '注文編集情報の取得に失敗しました')));
  }, [orderIdNum]);

  const handleSubmit = async (payload: CreateOrderRequest) => {
    const updated = await updateOrder(orderIdNum, payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `注文を更新しました（ID: ${updated.id}）` }));
    navigate('/orders');
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (!customers || !products) return <LoadingState title="注文編集フォームを準備中" description="データを読み込んでいます" />;
  if (!initialValue) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section>
      <OrderForm
        onSubmit={handleSubmit}
        onDiscard={() => setInitialValue((prev) => (prev ? { ...prev } : prev))}
        customers={customers}
        products={products}
        initialValue={initialValue}
        submitLabel="注文を保存"
      />
    </section>
  );
};
