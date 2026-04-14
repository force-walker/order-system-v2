import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getOrderItem } from 'features/orders/services/ordersService';
import type { OrderDetail, OrderItem, OrderStatus } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

type DetailState = {
  order: OrderDetail;
  item: OrderItem;
};

const STATUS_LABEL: Record<OrderStatus, string> = {
  new: '新規',
  confirmed: '確定',
  allocated: '引当済',
  purchased: '仕入済',
  shipped: '出荷済',
  invoiced: '請求済',
  cancelled: '取消',
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
      .catch((e) => setError(toActionableMessage(e, 'アイテム詳細の取得に失敗しました')))
      .finally(() => setLoaded(true));
  }, [orderId, itemId]);

  const itemCount = useMemo(() => detail?.order.items.length ?? 0, [detail]);

  if (error) {
    return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  }

  if (!loaded) {
    return <LoadingState title="アイテム詳細を読み込み中" description="しばらくお待ちください" />;
  }

  if (!detail) {
    return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;
  }

  return (
    <section className="detail-layout">
      <div className="card">
        <div className="detail-header">
          <h2>注文アイテム詳細</h2>
          <span className={`status-badge status-${detail.order.status}`}>{STATUS_LABEL[detail.order.status]}</span>
        </div>

        <div className="detail-grid two-col">
          <div>
            <h3>注文情報</h3>
            <dl className="kv-list">
              <div>
                <dt>注文ID</dt>
                <dd>{detail.order.id}</dd>
              </div>
              <div>
                <dt>注文番号</dt>
                <dd>{detail.order.orderNo}</dd>
              </div>
              <div>
                <dt>顧客名</dt>
                <dd>{detail.order.customerName}</dd>
              </div>
              <div>
                <dt>受注日（システム日時）</dt>
                <dd>{detail.order.orderDatetime ? new Date(detail.order.orderDatetime).toLocaleString('ja-JP') : '-'}</dd>
              </div>
              <div>
                <dt>納品日（顧客納品日）</dt>
                <dd>{detail.order.deliveryDate}</dd>
              </div>
              <div>
                <dt>出荷日（仕入商品の出荷日）</dt>
                <dd>{detail.order.shippedDate ?? '-'}</dd>
              </div>
              <div>
                <dt>アイテム数</dt>
                <dd>{itemCount}</dd>
              </div>
            </dl>
          </div>

          <div>
            <h3>選択アイテム情報</h3>
            <dl className="kv-list">
              <div>
                <dt>アイテムID</dt>
                <dd>{detail.item.id}</dd>
              </div>
              <div>
                <dt>商品名</dt>
                <dd>{detail.item.productName}</dd>
              </div>
              <div>
                <dt>数量</dt>
                <dd>
                  {detail.item.quantity} {detail.item.unit}
                </dd>
              </div>
              <div>
                <dt>推定重量(kg)</dt>
                <dd>{detail.item.estimatedWeightKg ?? '-'}</dd>
              </div>
              <div>
                <dt>目標単価</dt>
                <dd>{detail.item.targetPrice ?? '-'}</dd>
              </div>
              <div>
                <dt>価格上限</dt>
                <dd>{detail.item.priceCeiling ?? '-'}</dd>
              </div>
              <div>
                <dt>代替指示</dt>
                <dd>{detail.item.stockoutPolicy ?? '-'}</dd>
              </div>
              <div>
                <dt>コメント</dt>
                <dd>{detail.item.comment ?? '-'}</dd>
              </div>
              <div>
                <dt>備考</dt>
                <dd>{detail.item.note ?? '-'}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="detail-actions">
          <Link to="/orders">一覧へ戻る</Link>
          <Link to="/orders/new">新規作成へ</Link>
        </div>
      </div>
    </section>
  );
};
