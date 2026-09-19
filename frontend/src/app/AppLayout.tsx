import { Link, matchPath, Outlet, useLocation } from 'react-router-dom';
import { LogoutButton } from 'features/auth/LogoutButton';
import { useAuth } from 'features/auth/AuthContext';

const branchName = import.meta.env.VITE_APP_BRANCH ?? 'local';
const commitSha = import.meta.env.VITE_APP_COMMIT_SHA ?? 'dev';
const buildTime = import.meta.env.VITE_APP_BUILD_TIME ?? 'local-build';

const navigation = [
  [
    "/orders/new",
    "注文作成"
  ],
  [
    "/orders",
    "注文一覧"
  ],
  [
    "/orders/item-allocations",
    "一括割当"
  ],
  [
    "/reports/shipping",
    "帳票"
  ],
  [
    "/purchases",
    "納品確認"
  ],
  [
    "/invoices/drafts",
    "請求ドラフト"
  ],
  [
    "/invoices",
    "請求書"
  ],
  [
    "/products",
    "商品"
  ],
  [
    "/customers",
    "顧客"
  ],
  [
    "/suppliers",
    "仕入先"
  ],
  [
    "/settings/system",
    "環境設定"
  ]
] as const;

export const AppLayout = () => {
  const { user } = useAuth();
  const location = useLocation();
  // Prefer the most specific section, including its detail/edit pages.
  const activePath = navigation.reduce<string | undefined>((selected, [path]) =>
    matchPath({ path, end: false }, location.pathname) && path.length > (selected?.length ?? 0)
      ? path : selected, undefined);
  const isWidePage = location.pathname === '/orders/item-allocations' || location.pathname === '/purchases';

  return (
    <div className={`page ${isWidePage ? 'page-wide' : ''}`}>
      <header className="header">
        <div>
          <h1>Order System v2 (Mockup)</h1>
          <p className="branch-badge">branch: {branchName}</p>
          <p>{user?.user_id}</p>
          <LogoutButton />
        </div>
        <nav className="nav">
          {navigation.map(([path, label]) => (
            <Link key={path} to={path}
              className={`nav-link ${activePath === path ? 'active' : ''}`}
              aria-current={activePath === path ? 'page' : undefined}>
              {label}
            </Link>
          ))}
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
