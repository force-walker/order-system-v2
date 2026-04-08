import { useNavigate } from 'react-router-dom';
import { CustomerForm } from 'features/customers/components/CustomerForm';
import { createCustomer } from 'features/customers/services/customersService';

export const CustomerCreatePage = () => {
  const navigate = useNavigate();

  const handleSubmit = async (payload: Parameters<typeof createCustomer>[0]) => {
    const created = await createCustomer(payload);
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `顧客を作成しました（ID: ${created.id} / CODE: ${created.customerCode}）` }));
    navigate('/customers');
  };

  return (
    <section>
      <CustomerForm submitLabel="顧客を作成" onSubmit={handleSubmit} />
    </section>
  );
};
