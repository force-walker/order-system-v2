import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveCustomer, deleteCustomer, listCustomers, unarchiveCustomer } from 'features/customers/services/customersService';
import type { CustomerOption } from 'features/customers/types/customer';
import { toActionableMessage } from 'shared/error';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

const toTs = (iso?: string) => (iso ? Date.parse(iso) : 0);

export const CustomerListPage = () => {
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [keyword, setKeyword] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [sortMode, setSortMode] = useState<'idAsc' | 'idDesc' | 'createdAsc' | 'createdDesc' | 'updatedAsc' | 'updatedDesc'>('idAsc');

  const load = async () => {
    setError('');
    try {
      const data = await listCustomers(showArchived);
      setCustomers(data);
    } catch (e) {
      setError(toActionableMessage(e, '顧客一覧の取得に失敗しました'));
    }
  };

  useEffect(() => {
    load();

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
  }, [showArchived]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(t);
  }, [toast]);

  const runAction = async (fn: () => Promise<unknown>, successMessage: string) => {
    try {
      await fn();
      setToast({ type: 'success', message: successMessage });
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '操作に失敗しました') });
    }
  };

  const filteredCustomers = useMemo(() => {
    if (!customers) return [];
    const q = keyword.trim().toLowerCase();
    const byKeyword = q.length === 0 ? customers : customers.filter((c) => c.label.toLowerCase().includes(q));
    const sorted = [...byKeyword];

    if (sortMode === 'idDesc') sorted.sort((a, b) => b.id - a.id);
    else if (sortMode === 'createdAsc') sorted.sort((a, b) => toTs(a.createdAt) - toTs(b.createdAt));
    else if (sortMode === 'createdDesc') sorted.sort((a, b) => toTs(b.createdAt) - toTs(a.createdAt));
    else if (sortMode === 'updatedAsc') sorted.sort((a, b) => toTs(a.updatedAt) - toTs(b.updatedAt));
    else if (sortMode === 'updatedDesc') sorted.sort((a, b) => toTs(b.updatedAt) - toTs(a.updatedAt));
    else sorted.sort((a, b) => a.id - b.id);

    return sorted;
  }, [customers, keyword, sortMode]);

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (!customers) return <LoadingState title="顧客一覧を読み込み中" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>顧客マスタ</h2>
            <p className="subtle">作成・編集・アーカイブ・削除対応</p>
          </div>
          <div className="list-controls">
            <label className="filter-label">
              検索
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="顧客名 / コード" />
            </label>
            <label className="filter-label">
              並び順
              <select value={sortMode} onChange={(e) => setSortMode(e.target.value as any)}>
                <option value="idAsc">ID 昇順</option>
                <option value="idDesc">ID 降順</option>
                <option value="createdAsc">作成日時 昇順</option>
                <option value="createdDesc">作成日時 降順</option>
                <option value="updatedAsc">更新日時 昇順</option>
                <option value="updatedDesc">更新日時 降順</option>
              </select>
            </label>
            <label className="filter-label">
              <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> アーカイブを表示
            </label>
            <Link to="/customers/new" className="order-link">+ 顧客を作成</Link>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>コード</th>
                <th>表示名</th>
                <th>作成日時</th>
                <th>更新日時</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="subtle">条件に合うデータがありません。検索条件を見直してください。</td>
                </tr>
              ) : filteredCustomers.map((c) => (
                  <tr key={c.id}>
                    <td>{c.id}</td>
                    <td>{c.customerCode ?? '-'}</td>
                    <td>{c.label}</td>
                    <td>{c.createdAt ?? '-'}</td>
                    <td>{c.updatedAt ?? '-'}</td>
                    <td>
                      <Link to={`/customers/${c.id}`} className="order-link">詳細</Link>
                      {' / '}
                      <Link to={`/customers/${c.id}/edit`} className="order-link">編集</Link>
                      {' / '}
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          const label = c.label;
                          const confirmed = window.confirm(`${label} を${c.active ? 'アーカイブ' : '復元'}しますか？`);
                          if (!confirmed) return;
                          void runAction(
                            () => (c.active ? archiveCustomer(c.id) : unarchiveCustomer(c.id)),
                            c.active ? '顧客をアーカイブしました' : '顧客を復元しました',
                          );
                        }}
                      >
                        {c.active ? 'アーカイブ' : '復元'}
                      </button>
                      {' / '}
                      <button
                        type="button"
                        className="danger"
                        onClick={() => {
                          const label = c.label;
                          const confirmed = window.confirm(`${label} を削除しますか？（参照がある場合は削除できません）`);
                          if (!confirmed) return;
                          void runAction(() => deleteCustomer(c.id), '顧客を削除しました');
                        }}
                      >
                        削除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </div>
    </section>
  );
};
