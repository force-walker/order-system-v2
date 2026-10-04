import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { buildDetailHref, compareText, SelectionHeaderCheckbox, SortableHeader, type SortDirection, useVisibleRowSelection } from 'components/common/MasterTableControls';
import { archiveSupplier, deleteSupplier, listSuppliers, unarchiveSupplier } from 'features/suppliers/services/suppliersService';
import type { Supplier } from 'features/suppliers/types/supplier';
import { toActionableMessage } from 'shared/error';
import { useFocusNavigation } from 'shared/useFocusNavigation';

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};
type SortColumn = 'id' | 'supplierCode' | 'name' | 'active' | 'updatedAt';

export const SupplierListPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [items, setItems] = useState<Supplier[]>([]);
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get('q') ?? '';
  const showArchived = searchParams.get('archived') === '1';
  const limit = Number(searchParams.get('limit')) || 20;
  const offset = Number(searchParams.get('offset')) || 0;
  const sortColumn = (searchParams.get('sort') as SortColumn | null) ?? 'id';
  const sortDirection = (searchParams.get('dir') as SortDirection | null) ?? 'asc';
  const [hasNext, setHasNext] = useState(false);
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();

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

  const setParams = (updates: Record<string, string>, defaults: Record<string, string> = {}) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === (defaults[key] ?? '')) next.delete(key); else next.set(key, value);
    });
    setSearchParams(next, { replace: true });
  };
  const onSort = (column: SortColumn) => {
    const direction: SortDirection = sortColumn === column && sortDirection === 'asc' ? 'desc' : 'asc';
    setParams({ sort: column === 'id' ? '' : column, dir: direction === 'asc' ? '' : direction });
  };

  const filteredItems = useMemo(() => {
    const keyword = q.trim().toLowerCase();
    const filtered = !keyword ? items : items.filter((row) => {
      const target = `${row.supplierCode} ${row.name}`.toLowerCase();
      return target.includes(keyword);
    });
    return [...filtered].sort((a, b) => {
      let result = 0;
      if (sortColumn === 'id') result = a.id - b.id;
      else if (sortColumn === 'supplierCode') result = compareText(a.supplierCode, b.supplierCode);
      else if (sortColumn === 'name') result = compareText(a.name, b.name);
      else if (sortColumn === 'active') result = Number(a.active) - Number(b.active);
      else result = Date.parse(a.updatedAt) - Date.parse(b.updatedAt);
      if (result === 0) result = a.id - b.id;
      return sortDirection === 'asc' ? result : -result;
    });
  }, [items, q, sortColumn, sortDirection]);
  const visibleIds = filteredItems.map((row) => row.id);
  const selection = useVisibleRowSelection(visibleIds);

  const runAction = async (fn: () => Promise<unknown>, successMessage: string) => {
    try {
      await fn();
      setToast({ type: 'success', message: successMessage });
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '操作に失敗しました') });
    }
  };

  const onPrev = () => setParams({ offset: String(Math.max(0, offset - limit)) }, { offset: '0' });
  const onNext = () => setParams({ offset: String(offset + limit) }, { offset: '0' });

  if (error) return <ErrorState title="仕入先一覧の取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  if (loading) return <LoadingState title="仕入先一覧を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div ref={focusNavRef as any} onKeyDownCapture={onFocusNavKeyDownCapture} className="card">
        <div className="list-header">
          <div>
            <h2>仕入先一覧</h2>
            <p className="subtle">検索・アーカイブ・削除・ページング対応</p>
          </div>
          <div className="list-controls">
            <Link to="/suppliers/import" className="order-link">Import</Link>
            <Link to="/suppliers/new" className="order-link">+ 仕入先を作成</Link>
          </div>
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            検索(q)
            <input value={q} onChange={(e) => setParams({ q: e.target.value })} placeholder="supplier_code / name" />
          </label>

          <label className="filter-label">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => {
                setParams({ archived: e.target.checked ? '1' : '', offset: '' });
              }}
            />
            アーカイブを表示
          </label>

          <label className="filter-label">
            limit
            <select
              value={limit}
              onChange={(e) => {
                setParams({ limit: e.target.value, offset: '' }, { limit: '20' });
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
                <th><SelectionHeaderCheckbox checked={selection.allSelected} indeterminate={selection.partiallySelected} onChange={selection.toggleAll} label="表示中の仕入先をすべて選択" /></th>
                <SortableHeader column="id" label="ID" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="supplierCode" label="supplier_code" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="name" label="name" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="active" label="active" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="updatedAt" label="updated_at" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="subtle">条件に合う仕入先がありません。検索条件を見直してください。</td>
                </tr>
              ) : filteredItems.map((row) => (
                  <tr key={row.id}>
                    <td><input type="checkbox" checked={selection.selectedIds.has(row.id)} onChange={() => selection.toggle(row.id)} aria-label={`${row.name}を選択`} /></td>
                    <td>{row.id}</td>
                    <td>{row.supplierCode}</td>
                    <td>{row.name}</td>
                    <td>{row.active ? 'true' : 'false'}</td>
                    <td>{new Date(row.updatedAt).toLocaleString('ja-JP')}</td>
                    <td>
                      <Link to={buildDetailHref('/suppliers', row.id, visibleIds, searchParams.toString())} className="order-link">詳細</Link>
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
