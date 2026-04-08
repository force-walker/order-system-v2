import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { ProductForm } from 'features/orders/components/ProductForm';
import { getProductDetail, updateProduct } from 'features/orders/services/ordersService';
import type { ProductDetail } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const ProductEditPage = () => {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [product, setProduct] = useState<ProductDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  const productIdNum = useMemo(() => Number(productId), [productId]);

  useEffect(() => {
    if (!productIdNum) return setError('不正な商品IDです');
    getProductDetail(productIdNum)
      .then(setProduct)
      .catch((e) => setError(toUserMessage(e, '商品情報の取得に失敗しました')));
  }, [productIdNum]);

  const handleSubmit = async (payload: {
    name: string;
    orderUom: string;
    purchaseUom: string;
    invoiceUom: string;
    pricingBasisDefault: 'uom_count' | 'uom_kg';
    isCatchWeight: boolean;
    weightCaptureRequired: boolean;
  }) => {
    const updated = await updateProduct(productIdNum, {
      name: payload.name,
      orderUom: payload.orderUom,
      purchaseUom: payload.purchaseUom,
      invoiceUom: payload.invoiceUom,
      isCatchWeight: payload.isCatchWeight,
      weightCaptureRequired: payload.weightCaptureRequired,
    });
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `商品を更新しました（ID: ${updated.id}）` }));
    navigate('/products');
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (product === undefined) return <LoadingState title="商品情報を読み込み中" />;
  if (product === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section>
      <ProductForm initialValue={product} submitLabel="商品を保存" onSubmit={handleSubmit} />
    </section>
  );
};
