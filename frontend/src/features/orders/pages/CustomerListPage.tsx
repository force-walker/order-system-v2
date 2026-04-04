import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listCustomers } from 'features/orders/services/ordersService';
import type { CustomerOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

export const CustomerListPage = () => {
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [keyword, setKeyword] = useState('');
  const [sortMode, setSortMode] = useState<'idAsc' | 'idDesc'>('idAsc');

  useEffect(() => {
    listCustomers()
      .then(setCustomers)
      .catch((e) => setError(toUserMessage(e, '顧客一覧の取得に失敗しました')));

    const raw = sessionStorage.getItem('osv2_toast');
    if (raw) {
      try {
        setToast(JSON.parse(raw) as ToastPayload);
      } catch {
        // noop
      } finally {
        sessionStorage.removeItem('osv2_toast');
      }
    }
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(t);
  }, [toast]);

  const filteredCustomers = useMemo(() => {
    if (!customers) return [];
    const q = keyword.trim().toLowerCase();
    const byKeyword = q.length === 0 ? customers : customers.filter((c) => c.label.toLowerCase().includes(q));
    const sorted = [...byKeyword];
    if (sortMode === 'idDesc') sorted.sort((a, b) => b.id - a.id);
    else sorted.sort((a, b) => a.id - b.id);
    return sorted;
  }, [customers, keyword, sortMode]);

  if (error) return <ErrorState title="顧客一覧の取得に失敗" description={error} />;
  if (!customers) return <LoadingState title="顧客一覧を読み込み中" />;
  if (customers.length === 0) return <EmptyState title="顧客データがありません" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>顧客マスタ</h2>
            <p className="subtle">作成・編集対応</p>
          </div>
          <div className="list-controls">
            <label className="filter-label">
              検索
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="顧客名 / コード" />
            </label>
            <label className="filter-label">
              並び順
              <select value={sortMode} onChange={(e) => setSortMode(e.target.value as 'idAsc' | 'idDesc')}>
                <option value="idAsc">ID 昇順</option>
                <option value="idDesc">ID 降順</option>
              </select>
            </label>
            <Link to="/customers/new" className="order-link">+ 顧客を作成</Link>
          </div>
        </div>

        {filteredCustomers.length === 0 ? (
          <EmptyState title="条件に合う顧客がありません" description="検索条件を見直してください" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>表示名</th>
                  <th>詳細</th>
                </tr>
              </thead>
              <tbody>
                {filteredCustomers.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td>{c.label}</td>
                    <td>
                      <Link to={`/customers/${c.id}`} className="order-link">詳細</Link>
                      {' / '}
                      <Link to={`/customers/${c.id}/edit`} className="order-link">編集</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
