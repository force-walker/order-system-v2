import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getOrderItem } from 'features/orders/services/ordersService';
import type { OrderDetail, OrderItem } from 'features/orders/types/order';

type DetailState = {
  order: OrderDetail;
  item: OrderItem;
};

export const OrderItemDetailPage = () => {
  const { orderId, itemId } = useParams();
  const [detail, setDetail] = useState<DetailState | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const oid = Number(orderId);
    const iid = Number(itemId);

    if (!oid || !iid) {
      setError('不正なIDです');
      return;
    }

    setLoaded(false);
    getOrderItem(oid, iid)
      .then((result) => {
        if (!result) {
          setDetail(null);
          return;
        }
        setDetail(result);
      })
      .catch(() => setError('アイテム詳細の取得に失敗しました'))
      .finally(() => setLoaded(true));
  }, [orderId, itemId]);

  if (error) {
    return <ErrorState title="アイテム詳細を表示できません" description={error} />;
  }

  if (!loaded) {
    return <LoadingState title="アイテム詳細を読み込み中" description="しばらくお待ちください" />;
  }

  if (!detail) {
    return <EmptyState title="対象データがありません" description="一覧から再度選択してください" />;
  }

  return (
    <section className="card">
      <h2>注文アイテム詳細</h2>
      <p>
        <strong>注文番号:</strong> {detail.order.orderNo}
      </p>
      <p>
        <strong>顧客名:</strong> {detail.order.customerName}
      </p>
      <p>
        <strong>商品名:</strong> {detail.item.productName}
      </p>
      <p>
        <strong>数量:</strong> {detail.item.quantity} {detail.item.unit}
      </p>
      <p>
        <strong>備考:</strong> {detail.item.note ?? '-'}
      </p>
      <Link to="/orders">一覧へ戻る</Link>
    </section>
  );
};
