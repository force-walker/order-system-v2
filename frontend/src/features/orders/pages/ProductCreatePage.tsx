import { useNavigate } from 'react-router-dom';
import { ProductForm } from 'features/orders/components/ProductForm';
import { createProduct } from 'features/orders/services/ordersService';

export const ProductCreatePage = () => {
  const navigate = useNavigate();

  const handleSubmit = async (payload: Parameters<typeof createProduct>[0]) => {
    const created = await createProduct(payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `商品を作成しました（ID: ${created.id}）` }));
    navigate('/products');
  };

  return (
    <section>
      <ProductForm submitLabel="商品を作成" onSubmit={handleSubmit} />
    </section>
  );
};
