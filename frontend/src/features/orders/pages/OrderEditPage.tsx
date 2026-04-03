import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { OrderForm } from 'features/orders/components/OrderForm';
import { getOrder, listCustomers, listProducts, updateOrder } from 'features/orders/services/ordersService';
import type { CreateOrderRequest, CustomerOption, ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

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
          })),
        });
      })
      .catch((e) => setError(toUserMessage(e, '注文編集情報の取得に失敗しました')));
  }, [orderIdNum]);

  const handleSubmit = async (payload: CreateOrderRequest) => {
    const updated = await updateOrder(orderIdNum, payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `注文を更新しました（ID: ${updated.id}）` }));
    navigate('/orders');
  };

  if (error) return <ErrorState title="注文編集を開始できません" description={error} />;
  if (!customers || !products) return <LoadingState title="注文編集フォームを準備中" description="データを読み込んでいます" />;
  if (!initialValue) return <EmptyState title="注文データが見つかりません" description="一覧から再度選択してください" />;

  return (
    <section>
      <OrderForm onSubmit={handleSubmit} customers={customers} products={products} initialValue={initialValue} submitLabel="注文を保存" />
    </section>
  );
};
