import { useNavigate } from 'react-router-dom';
import { SupplierForm } from 'features/suppliers/components/SupplierForm';
import { createSupplier } from 'features/suppliers/services/suppliersService';

export const SupplierCreatePage = () => {
  const navigate = useNavigate();

  const handleSubmit = async (payload: Parameters<typeof createSupplier>[0]) => {
    const created = await createSupplier(payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `仕入先を作成しました（ID: ${created.id}）` }));
    navigate('/suppliers');
  };

  return (
    <section>
      <SupplierForm submitLabel="仕入先を作成" onSubmit={handleSubmit} />
    </section>
  );
};
