import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { buildDetailHref, compareText, SelectionHeaderCheckbox, SortableHeader, type SortDirection, useVisibleRowSelection } from 'components/common/MasterTableControls';
import { archiveCustomer, deleteCustomer, listCustomers, unarchiveCustomer } from 'features/customers/services/customersService';
import type { CustomerOption } from 'features/customers/types/customer';
import { toActionableMessage } from 'shared/error';
import { useFocusNavigation } from 'shared/useFocusNavigation';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

const toTs = (iso?: string) => (iso ? Date.parse(iso) : 0);
type SortColumn = 'id' | 'customerCode' | 'label' | 'createdAt' | 'updatedAt';

export const CustomerListPage = () => {
  const [customers, setCustomers] = useState<CustomerOption[] | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const keyword = searchParams.get('q') ?? '';
  const showArchived = searchParams.get('archived') === '1';
  const sortColumn = (searchParams.get('sort') as SortColumn | null) ?? 'id';
  const sortDirection = (searchParams.get('dir') as SortDirection | null) ?? 'asc';
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();

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

  const setParam = (key: string, value: string, defaultValue = '') => {
    const next = new URLSearchParams(searchParams);
    if (value === defaultValue) next.delete(key); else next.set(key, value);
    setSearchParams(next, { replace: true });
  };
  const onSort = (column: SortColumn) => {
    const next = new URLSearchParams(searchParams);
    const direction: SortDirection = sortColumn === column && sortDirection === 'asc' ? 'desc' : 'asc';
    if (column === 'id') next.delete('sort'); else next.set('sort', column);
    if (direction === 'asc') next.delete('dir'); else next.set('dir', direction);
    setSearchParams(next, { replace: true });
  };

  const filteredCustomers = useMemo(() => {
    if (!customers) return [];
    const q = keyword.trim().toLowerCase();
    const byKeyword = q.length === 0 ? customers : customers.filter((c) => `${c.customerCode ?? ''} ${c.label}`.toLowerCase().includes(q));
    const sorted = [...byKeyword];

    sorted.sort((a, b) => {
      let result = 0;
      if (sortColumn === 'id') result = a.id - b.id;
      else if (sortColumn === 'customerCode') result = compareText(a.customerCode, b.customerCode);
      else if (sortColumn === 'label') result = compareText(a.label, b.label);
      else if (sortColumn === 'createdAt') result = toTs(a.createdAt) - toTs(b.createdAt);
      else result = toTs(a.updatedAt) - toTs(b.updatedAt);
      if (result === 0) result = a.id - b.id;
      return sortDirection === 'asc' ? result : -result;
    });

    return sorted;
  }, [customers, keyword, sortColumn, sortDirection]);
  const visibleIds = filteredCustomers.map((row) => row.id);
  const selection = useVisibleRowSelection(visibleIds);

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (!customers) return <LoadingState title="顧客一覧を読み込み中" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div ref={focusNavRef as any} onKeyDownCapture={onFocusNavKeyDownCapture} className="card">
        <div className="list-header">
          <div>
            <h2>顧客マスタ</h2>
            <p className="subtle">作成・編集・アーカイブ・削除対応</p>
          </div>
          <div className="list-controls">
            <label className="filter-label">
              検索
              <input value={keyword} onChange={(e) => setParam('q', e.target.value)} placeholder="顧客名 / コード" />
            </label>
            <label className="filter-label">
              <input type="checkbox" checked={showArchived} onChange={(e) => setParam('archived', e.target.checked ? '1' : '', '')} /> アーカイブを表示
            </label>
            <Link to="/customers/import" className="order-link">Import</Link>
            <Link to="/customers/new" className="order-link">+ 顧客を作成</Link>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th><SelectionHeaderCheckbox checked={selection.allSelected} indeterminate={selection.partiallySelected} onChange={selection.toggleAll} label="表示中の顧客をすべて選択" /></th>
                <SortableHeader column="id" label="ID" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="customerCode" label="コード" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="label" label="表示名" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="createdAt" label="作成日時" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="updatedAt" label="更新日時" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="subtle">条件に合うデータがありません。検索条件を見直してください。</td>
                </tr>
              ) : filteredCustomers.map((c) => (
                  <tr key={c.id}>
                    <td><input type="checkbox" checked={selection.selectedIds.has(c.id)} onChange={() => selection.toggle(c.id)} aria-label={`${c.label}を選択`} /></td>
                    <td>{c.id}</td>
                    <td>{c.customerCode ?? '-'}</td>
                    <td>{c.label}</td>
                    <td>{c.createdAt ?? '-'}</td>
                    <td>{c.updatedAt ?? '-'}</td>
                    <td>
                      <Link to={buildDetailHref('/customers', c.id, visibleIds, searchParams.toString())} className="order-link">詳細</Link>
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
