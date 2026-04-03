import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

const branchName = import.meta.env.VITE_APP_BRANCH ?? 'local';
const commitSha = import.meta.env.VITE_APP_COMMIT_SHA ?? 'dev';
const buildTime = import.meta.env.VITE_APP_BUILD_TIME ?? 'local-build';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

export const AppLayout = () => {
  const location = useLocation();
  const [toast, setToast] = useState<ToastPayload | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem('osv2_toast');
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as ToastPayload;
      setToast(parsed);
    } catch {
      // noop
    } finally {
      sessionStorage.removeItem('osv2_toast');
    }
  }, [location.pathname]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(t);
  }, [toast]);

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Order System v2 (Mockup)</h1>
          <p className="branch-badge">branch: {branchName}</p>
        </div>
        <nav className="nav">
          <NavLink to="/orders/new" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>注文作成</NavLink>
          <NavLink to="/orders" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>注文一覧</NavLink>
          <NavLink to="/products" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>商品</NavLink>
          <NavLink to="/customers" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>顧客</NavLink>
        </nav>
      </header>

      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}

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
