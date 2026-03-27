import { NavLink, Outlet } from 'react-router-dom';

export const AppLayout = () => {
  return (
    <div className="page">
      <header className="header">
        <h1>Order System v2 (Mockup)</h1>
        <nav className="nav">
          <NavLink to="/orders/new">注文作成</NavLink>
          <NavLink to="/orders">注文一覧</NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
};
