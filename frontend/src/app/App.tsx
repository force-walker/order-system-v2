import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import { OrderCreatePage } from 'features/orders/pages/OrderCreatePage';
import { OrderListPage } from 'features/orders/pages/OrderListPage';
import { OrderItemDetailPage } from 'features/orders/pages/OrderItemDetailPage';
import { OrderEditPage } from 'features/orders/pages/OrderEditPage';
import { ProductListPage } from 'features/products/pages/ProductListPage';
import { ProductDetailPage } from 'features/products/pages/ProductDetailPage';
import { ProductCreatePage } from 'features/products/pages/ProductCreatePage';
import { ProductEditPage } from 'features/products/pages/ProductEditPage';
import { CustomerListPage } from 'features/customers/pages/CustomerListPage';
import { CustomerDetailPage } from 'features/customers/pages/CustomerDetailPage';
import { CustomerCreatePage } from 'features/customers/pages/CustomerCreatePage';
import { CustomerEditPage } from 'features/customers/pages/CustomerEditPage';
import { SupplierListPage } from 'features/suppliers/pages/SupplierListPage';
import { SupplierCreatePage } from 'features/suppliers/pages/SupplierCreatePage';
import { SupplierEditPage } from 'features/suppliers/pages/SupplierEditPage';

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
        <Route path="/suppliers" element={<SupplierListPage />} />
        <Route path="/suppliers/new" element={<SupplierCreatePage />} />
        <Route path="/suppliers/:supplierId/edit" element={<SupplierEditPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/orders/new" replace />} />
    </Routes>
  );
};
