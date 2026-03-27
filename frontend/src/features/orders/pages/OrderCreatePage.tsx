import { useNavigate } from 'react-router-dom';
import { OrderForm } from 'features/orders/components/OrderForm';
import { createOrder } from 'features/orders/services/ordersService';

export const OrderCreatePage = () => {
  const navigate = useNavigate();

  const handleSubmit = async (payload: Parameters<typeof createOrder>[0]) => {
    await createOrder(payload);
    navigate('/orders');
  };

  return (
    <section>
      <OrderForm onSubmit={handleSubmit} />
    </section>
  );
};
