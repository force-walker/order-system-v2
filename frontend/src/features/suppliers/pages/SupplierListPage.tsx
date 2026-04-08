import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listSuppliers } from 'features/suppliers/services/suppliersService';
import type { Supplier } from 'features/suppliers/types/supplier';
import { toUserMessage } from 'shared/error';

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
  const [active, setActive] = useState<'all' | 'true' | 'false'>('all');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);

  const load = async (params: { active: 'all' | 'true' | 'false'; limit: number; offset: number }) => {
    setLoading(true);
    setError('');

    try {
      const result = await listSuppliers(params);
      setItems(result.items);
      setHasNext(result.hasNext);
    } catch (e) {
      setError(toUserMessage(e, '仕入先一覧の取得に失敗しました'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load({ active, limit, offset });
  }, [active, limit, offset]);

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

  const onPrev = () => {
    setOffset((prev) => Math.max(0, prev - limit));
  };

  const onNext = () => {
    setOffset((prev) => prev + limit);
  };

  if (error) return <ErrorState title="仕入先一覧の取得に失敗しました" description={error} actionLabel="再試行" onAction={() => load({ active, limit, offset })} />;
  if (loading) return <LoadingState title="仕入先一覧を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>仕入先一覧</h2>
            <p className="subtle">検索(q)・activeフィルタ・ページングに対応</p>
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
            active
            <select
              value={active}
              onChange={(e) => {
                setActive(e.target.value as 'all' | 'true' | 'false');
                setOffset(0);
              }}
            >
              <option value="all">all</option>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
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

        {filteredItems.length === 0 ? (
          <EmptyState
            title="データがありません"
            description="条件に合う仕入先がありません。検索条件を見直してください。"
            actionLabel="条件クリア"
            onAction={() => {
              setQ('');
              setActive('all');
              setLimit(20);
              setOffset(0);
            }}
          />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>supplier_code</th>
                  <th>name</th>
                  <th>active</th>
                  <th>updated_at</th>
                  <th>編集</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.supplierCode}</td>
                    <td>{row.name}</td>
                    <td>{row.active ? 'true' : 'false'}</td>
                    <td>{new Date(row.updatedAt).toLocaleString('ja-JP')}</td>
                    <td><Link to={`/suppliers/${row.id}/edit`} className="order-link">編集</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="list-controls" style={{ marginTop: 12 }}>
          <button type="button" className="secondary" onClick={onPrev} disabled={offset === 0}>前へ</button>
          <span className="subtle">offset: {offset}</span>
          <button type="button" className="secondary" onClick={onNext} disabled={!hasNext}>次へ</button>
        </div>
      </div>
    </section>
  );
};
