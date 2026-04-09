import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveProduct, deleteProduct, getProductDetail, unarchiveProduct } from 'features/products/services/productsService';
import { ProductSupplierMappingPanel } from 'features/products/components/ProductSupplierMappingPanel';
import type { ProductDetail } from 'features/products/types/product';
import { toActionableMessage } from 'shared/error';

export const ProductDetailPage = () => {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState<ProductDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  const load = async () => {
    const id = Number(productId);
    if (!id) {
      setError('不正な商品IDです');
      return;
    }
    setError('');
    try {
      const row = await getProductDetail(id);
      setProduct(row);
    } catch (e) {
      setError(toActionableMessage(e, '商品詳細の取得に失敗しました'));
    }
  };

  useEffect(() => {
    load();
  }, [productId]);

  const runAndBack = async (fn: () => Promise<unknown>, success: string) => {
    try {
      await fn();
      sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: success }));
      navigate('/products');
    } catch (e) {
      setError(toActionableMessage(e, '操作に失敗しました'));
    }
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (product === undefined) return <LoadingState title="商品詳細を読み込み中" />;
  if (product === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <div className="detail-layout">
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
          <button
            type="button"
            className="secondary"
            onClick={() => {
              const confirmed = window.confirm(`${product.name} を${product.active ? 'アーカイブ' : '復元'}しますか？`);
              if (!confirmed) return;
              void runAndBack(
                () => (product.active ? archiveProduct(product.id) : unarchiveProduct(product.id)),
                product.active ? '商品をアーカイブしました' : '商品を復元しました',
              );
            }}
          >
            {product.active ? 'アーカイブ' : '復元'}
          </button>
          <button
            type="button"
            className="danger"
            onClick={() => {
              const confirmed = window.confirm(`${product.name} を削除しますか？（参照がある場合は削除できません）`);
              if (!confirmed) return;
              void runAndBack(() => deleteProduct(product.id), '商品を削除しました');
            }}
          >
            削除
          </button>
        </div>
      </section>

      <ProductSupplierMappingPanel productId={product.id} />
    </div>
  );
};
