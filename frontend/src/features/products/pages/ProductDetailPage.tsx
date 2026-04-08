import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getProductDetail } from 'features/products/services/productsService';
import type { ProductDetail } from 'features/products/types/product';
import { toUserMessage } from 'shared/error';

export const ProductDetailPage = () => {
  const { productId } = useParams();
  const [product, setProduct] = useState<ProductDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    const id = Number(productId);
    if (!id) {
      setError('不正な商品IDです');
      return;
    }
    getProductDetail(id)
      .then(setProduct)
      .catch((e) => setError(toUserMessage(e, '商品詳細の取得に失敗しました')));
  }, [productId]);

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (product === undefined) return <LoadingState title="商品詳細を読み込み中" />;
  if (product === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h2>商品詳細</h2>
      </div>
      <dl className="kv-list">
        <div><dt>ID</dt><dd>{product.id}</dd></div>
        <div><dt>SKU</dt><dd>{product.sku}</dd></div>
        <div><dt>商品名</dt><dd>{product.name}</dd></div>
        <div><dt>注文単位</dt><dd>{product.orderUom}</dd></div>
        <div><dt>仕入単位</dt><dd>{product.purchaseUom}</dd></div>
        <div><dt>請求単位</dt><dd>{product.invoiceUom}</dd></div>
        <div><dt>課金基準</dt><dd>{product.pricingBasisDefault}</dd></div>
        <div><dt>有効</dt><dd>{product.active ? '有効' : '無効'}</dd></div>
      </dl>
      <div className="detail-actions">
        <Link to="/products" className="order-link">商品一覧へ戻る</Link>
        <Link to={`/products/${product.id}/edit`} className="order-link">商品を編集</Link>
      </div>
    </section>
  );
};
