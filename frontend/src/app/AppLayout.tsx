import { NavLink, Outlet, useLocation } from 'react-router-dom';

const branchName = import.meta.env.VITE_APP_BRANCH ?? 'local';
const commitSha = import.meta.env.VITE_APP_COMMIT_SHA ?? 'dev';
const buildTime = import.meta.env.VITE_APP_BUILD_TIME ?? 'local-build';

export const AppLayout = () => {
  const location = useLocation();
  const isWidePage = location.pathname === '/orders/item-allocations' || location.pathname === '/purchases';

  return (
    <div className={`page ${isWidePage ? 'page-wide' : ''}`}>
      <header className="header">
        <div>
          <h1>Order System v2 (Mockup)</h1>
          <p className="branch-badge">branch: {branchName}</p>
        </div>
        <nav className="nav">
          <NavLink to="/orders/new" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>注文作成</NavLink>
          <NavLink to="/orders" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>注文一覧</NavLink>
          <NavLink to="/orders/item-allocations" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>一括割当</NavLink>
          <NavLink to="/purchases" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>納品確認</NavLink>
          <NavLink to="/reports/shipping" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>帳票</NavLink>
          <NavLink to="/invoices/drafts" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>請求ドラフト</NavLink>
          <NavLink to="/products" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>商品</NavLink>
          <NavLink to="/customers" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>顧客</NavLink>
          <NavLink to="/suppliers" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>仕入先</NavLink>
        </nav>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="footer-meta">
        <small>commit: {commitSha}</small>
        <small>build: {buildTime}</small>
      </footer>
    </div>
  );
};
