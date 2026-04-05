import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import { OrderCreatePage } from 'features/orders/pages/OrderCreatePage';
import { OrderListPage } from 'features/orders/pages/OrderListPage';
import { OrderItemDetailPage } from 'features/orders/pages/OrderItemDetailPage';
import { OrderEditPage } from 'features/orders/pages/OrderEditPage';
import { ProductListPage } from 'features/orders/pages/ProductListPage';
import { ProductDetailPage } from 'features/orders/pages/ProductDetailPage';
import { ProductCreatePage } from 'features/orders/pages/ProductCreatePage';
import { ProductEditPage } from 'features/orders/pages/ProductEditPage';
import { CustomerListPage } from 'features/orders/pages/CustomerListPage';
import { CustomerDetailPage } from 'features/orders/pages/CustomerDetailPage';
import { CustomerCreatePage } from 'features/orders/pages/CustomerCreatePage';
import { CustomerEditPage } from 'features/orders/pages/CustomerEditPage';
import { DevUiStatesPage } from 'features/orders/pages/DevUiStatesPage';

export const App = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/orders/new" replace />} />
      <Route element={<AppLayout />}>
        <Route path="/orders" element={<OrderListPage />} />
        <Route path="/orders/new" element={<OrderCreatePage />} />
        <Route path="/orders/:orderId/items/:itemId" element={<OrderItemDetailPage />} />
        <Route path="/orders/:orderId/edit" element={<OrderEditPage />} />
        <Route path="/products" element={<ProductListPage />} />
        <Route path="/products/new" element={<ProductCreatePage />} />
        <Route path="/products/:productId" element={<ProductDetailPage />} />
        <Route path="/products/:productId/edit" element={<ProductEditPage />} />
        <Route path="/customers" element={<CustomerListPage />} />
        <Route path="/customers/new" element={<CustomerCreatePage />} />
        <Route path="/customers/:customerId" element={<CustomerDetailPage />} />
        <Route path="/customers/:customerId/edit" element={<CustomerEditPage />} />
        <Route path="/dev/ui-states" element={<DevUiStatesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/orders/new" replace />} />
    </Routes>
  );
};
