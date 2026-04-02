import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getProduct } from 'features/orders/services/ordersService';
import type { ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const ProductDetailPage = () => {
  const { productId } = useParams();
  const [product, setProduct] = useState<ProductOption | null | undefined>(undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    const id = Number(productId);
    if (!id) {
      setError('不正な商品IDです');
      return;
    }
    getProduct(id)
      .then(setProduct)
      .catch((e) => setError(toUserMessage(e, '商品詳細の取得に失敗しました')));
  }, [productId]);

  if (error) return <ErrorState title="商品詳細の取得に失敗" description={error} />;
  if (product === undefined) return <LoadingState title="商品詳細を読み込み中" />;
  if (product === null) return <EmptyState title="商品が見つかりません" />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h2>商品詳細</h2>
      </div>
      <dl className="kv-list">
        <div><dt>ID</dt><dd>{product.id}</dd></div>
        <div><dt>ラベル</dt><dd>{product.label}</dd></div>
        <div><dt>商品名</dt><dd>{product.name}</dd></div>
        <div><dt>注文単位</dt><dd>{product.orderUom}</dd></div>
        <div><dt>課金基準</dt><dd>{product.pricingBasisDefault}</dd></div>
      </dl>
      <div className="detail-actions">
        <Link to="/products" className="order-link">商品一覧へ戻る</Link>
      </div>
    </section>
  );
};
