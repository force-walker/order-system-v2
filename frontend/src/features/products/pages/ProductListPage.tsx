import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { buildDetailHref, compareText, SelectionHeaderCheckbox, SortableHeader, type SortDirection, useVisibleRowSelection } from 'components/common/MasterTableControls';
import { archiveProduct, deleteProduct, listProducts, unarchiveProduct } from 'features/products/services/productsService';
import type { ProductOption } from 'features/products/types/product';
import { toActionableMessage } from 'shared/error';
import { useFocusNavigation } from 'shared/useFocusNavigation';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

type SortColumn = 'id' | 'sku' | 'name' | 'orderUom' | 'pricingBasisDefault' | 'createdAt' | 'updatedAt';

const toTs = (iso?: string) => (iso ? Date.parse(iso) : 0);

export const ProductListPage = () => {
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const keyword = searchParams.get('q') ?? '';
  const showArchived = searchParams.get('archived') === '1';
  const pricingFilter = (searchParams.get('pricing') as 'uom_count' | 'uom_kg' | null) ?? 'all';
  const sortColumn = (searchParams.get('sort') as SortColumn | null) ?? 'id';
  const sortDirection = (searchParams.get('dir') as SortDirection | null) ?? 'asc';
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();

  const load = async () => {
    setError('');
    try {
      const data = await listProducts(showArchived);
      setProducts(data);
    } catch (e) {
      setError(toActionableMessage(e, '商品一覧の取得に失敗しました'));
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

  const filteredProducts = useMemo(() => {
    if (!products) return [];
    const q = keyword.trim().toLowerCase();
    const byKeyword = q.length === 0 ? products : products.filter((p) => `${p.sku ?? ''} ${p.name} ${p.label}`.toLowerCase().includes(q));
    const byPricing = pricingFilter === 'all' ? byKeyword : byKeyword.filter((p) => p.pricingBasisDefault === pricingFilter);
    const sorted = [...byPricing];

    sorted.sort((a, b) => {
      let result = 0;
      if (sortColumn === 'id') result = a.id - b.id;
      else if (sortColumn === 'sku') result = compareText(a.sku, b.sku);
      else if (sortColumn === 'name') result = compareText(a.name, b.name);
      else if (sortColumn === 'orderUom') result = compareText(a.orderUom, b.orderUom);
      else if (sortColumn === 'pricingBasisDefault') result = compareText(a.pricingBasisDefault, b.pricingBasisDefault);
      else if (sortColumn === 'createdAt') result = toTs(a.createdAt) - toTs(b.createdAt);
      else result = toTs(a.updatedAt) - toTs(b.updatedAt);
      if (result === 0) result = a.id - b.id;
      return sortDirection === 'asc' ? result : -result;
    });

    return sorted;
  }, [products, keyword, pricingFilter, sortColumn, sortDirection]);

  const visibleIds = filteredProducts.map((row) => row.id);
  const selection = useVisibleRowSelection(visibleIds);

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (!products) return <LoadingState title="商品一覧を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div ref={focusNavRef as any} onKeyDownCapture={onFocusNavKeyDownCapture} className="card">
        <div className="list-header">
          <div>
            <h2>商品マスタ</h2>
            <p className="subtle">作成・編集・アーカイブ・削除対応</p>
          </div>
          <div className="list-controls">
            <label className="filter-label">
              検索
              <input value={keyword} onChange={(e) => setParam('q', e.target.value)} placeholder="商品名 / SKU" />
            </label>
            <label className="filter-label">
              課金基準
              <select value={pricingFilter} onChange={(e) => setParam('pricing', e.target.value, 'all')}>
                <option value="all">すべて</option>
                <option value="uom_count">uom_count</option>
                <option value="uom_kg">uom_kg</option>
              </select>
            </label>
            <label className="filter-label">
              <input type="checkbox" checked={showArchived} onChange={(e) => setParam('archived', e.target.checked ? '1' : '', '')} /> アーカイブを表示
            </label>
            <Link to="/products/import" className="order-link">IMPORT</Link>
            <Link to="/products/new" className="order-link">+ 商品を作成</Link>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th><SelectionHeaderCheckbox checked={selection.allSelected} indeterminate={selection.partiallySelected} onChange={selection.toggleAll} label="表示中の商品をすべて選択" /></th>
                <SortableHeader column="id" label="ID" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="sku" label="SKU" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="name" label="商品名" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="orderUom" label="注文単位" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="pricingBasisDefault" label="課金基準" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="createdAt" label="作成日時" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <SortableHeader column="updatedAt" label="更新日時" activeColumn={sortColumn} direction={sortDirection} onSort={onSort} />
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={9} className="subtle">条件に合うデータがありません。検索・フィルタ条件を見直してください。</td>
                </tr>
              ) : filteredProducts.map((p) => (
                <tr key={p.id}>
                  <td><input type="checkbox" checked={selection.selectedIds.has(p.id)} onChange={() => selection.toggle(p.id)} aria-label={`${p.name}を選択`} /></td>
                  <td>{p.id}</td>
                  <td>{p.sku ?? '-'}</td>
                  <td>{p.name}</td>
                  <td>{p.orderUom}</td>
                  <td>{p.pricingBasisDefault}</td>
                  <td>{p.createdAt ?? '-'}</td>
                  <td>{p.updatedAt ?? '-'}</td>
                  <td>
                    <Link to={buildDetailHref('/products', p.id, visibleIds, searchParams.toString())} className="order-link">詳細</Link>
                    {' / '}
                    <Link to={`/products/${p.id}/edit`} className="order-link">編集</Link>
                    {' / '}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => {
                        const confirmed = window.confirm(`${p.name} を${p.active ? 'アーカイブ' : '復元'}しますか？`);
                        if (!confirmed) return;
                        void runAction(
                          () => (p.active ? archiveProduct(p.id) : unarchiveProduct(p.id)),
                          p.active ? '商品をアーカイブしました' : '商品を復元しました',
                        );
                      }}
                    >
                      {p.active ? 'アーカイブ' : '復元'}
                    </button>
                    {' / '}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        const confirmed = window.confirm(`${p.name} を削除しますか？（参照がある場合は削除できません）`);
                        if (!confirmed) return;
                        void runAction(() => deleteProduct(p.id), '商品を削除しました');
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
