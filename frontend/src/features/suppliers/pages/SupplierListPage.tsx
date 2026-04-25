import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveSupplier, deleteSupplier, listSuppliers, unarchiveSupplier } from 'features/suppliers/services/suppliersService';
import type { Supplier } from 'features/suppliers/types/supplier';
import { toActionableMessage } from 'shared/error';

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

export const SupplierListPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [items, setItems] = useState<Supplier[]>([]);
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [q, setQ] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');

    try {
      const result = await listSuppliers({ active: 'all', includeInactive: showArchived, limit, offset });
      setItems(result.items);
      setHasNext(result.hasNext);
    } catch (e) {
      setError(toActionableMessage(e, '仕入先一覧の取得に失敗しました'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [showArchived, limit, offset]);

  useEffect(() => {
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

  const filteredItems = useMemo(() => {
    const keyword = q.trim().toLowerCase();
    if (!keyword) return items;

    return items.filter((row) => {
      const target = `${row.supplierCode} ${row.name}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [items, q]);

  const runAction = async (fn: () => Promise<unknown>, successMessage: string) => {
    try {
      await fn();
      setToast({ type: 'success', message: successMessage });
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '操作に失敗しました') });
    }
  };

  const onPrev = () => setOffset((prev) => Math.max(0, prev - limit));
  const onNext = () => setOffset((prev) => prev + limit);

  if (error) return <ErrorState title="仕入先一覧の取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  if (loading) return <LoadingState title="仕入先一覧を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>仕入先一覧</h2>
            <p className="subtle">検索・アーカイブ・削除・ページング対応</p>
          </div>
          <div className="list-controls">
            <Link to="/suppliers/new" className="order-link">+ 仕入先を作成</Link>
          </div>
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            検索(q)
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="supplier_code / name" />
          </label>

          <label className="filter-label">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => {
                setShowArchived(e.target.checked);
                setOffset(0);
              }}
            />
            アーカイブを表示
          </label>

          <label className="filter-label">
            limit
            <select
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setOffset(0);
              }}
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>supplier_code</th>
                <th>name</th>
                <th>active</th>
                <th>updated_at</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="subtle">条件に合う仕入先がありません。検索条件を見直してください。</td>
                </tr>
              ) : filteredItems.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.supplierCode}</td>
                    <td>{row.name}</td>
                    <td>{row.active ? 'true' : 'false'}</td>
                    <td>{new Date(row.updatedAt).toLocaleString('ja-JP')}</td>
                    <td>
                      <Link to={`/suppliers/${row.id}`} className="order-link">詳細</Link>
                      {' / '}
                      <Link to={`/suppliers/${row.id}/edit`} className="order-link">編集</Link>
                      {' / '}
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          const confirmed = window.confirm(`${row.name} を${row.active ? 'アーカイブ' : '復元'}しますか？`);
                          if (!confirmed) return;
                          void runAction(
                            () => (row.active ? archiveSupplier(row.id) : unarchiveSupplier(row.id)),
                            row.active ? '仕入先をアーカイブしました' : '仕入先を復元しました',
                          );
                        }}
                      >
                        {row.active ? 'アーカイブ' : '復元'}
                      </button>
                      {' / '}
                      <button
                        type="button"
                        className="danger"
                        onClick={() => {
                          const confirmed = window.confirm(`${row.name} を削除しますか？（参照がある場合は削除できません）`);
                          if (!confirmed) return;
                          void runAction(() => deleteSupplier(row.id), '仕入先を削除しました');
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

        <div className="list-controls" style={{ marginTop: 12 }}>
          <button type="button" className="secondary" onClick={onPrev} disabled={offset === 0}>前へ</button>
          <span className="subtle">offset: {offset}</span>
          <button type="button" className="secondary" onClick={onNext} disabled={!hasNext}>次へ</button>
        </div>
      </div>
    </section>
  );
};
