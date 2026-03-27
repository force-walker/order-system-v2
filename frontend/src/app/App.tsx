import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import { OrderCreatePage } from 'features/orders/pages/OrderCreatePage';
import { OrderListPage } from 'features/orders/pages/OrderListPage';
import { OrderItemDetailPage } from 'features/orders/pages/OrderItemDetailPage';

export const App = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/orders/new" replace />} />
      <Route element={<AppLayout />}>
        <Route path="/orders" element={<OrderListPage />} />
        <Route path="/orders/new" element={<OrderCreatePage />} />
        <Route path="/orders/:orderId/items/:itemId" element={<OrderItemDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/orders/new" replace />} />
    </Routes>
  );
};
