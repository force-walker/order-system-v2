import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveProduct, deleteProduct, listProducts, unarchiveProduct } from 'features/products/services/productsService';
import type { ProductOption } from 'features/products/types/product';
import { toActionableMessage } from 'shared/error';

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

const toTs = (iso?: string) => (iso ? Date.parse(iso) : 0);

export const ProductListPage = () => {
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const [keyword, setKeyword] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [pricingFilter, setPricingFilter] = useState<'all' | 'uom_count' | 'uom_kg'>('all');
  const [sortMode, setSortMode] = useState<'idAsc' | 'idDesc' | 'createdAsc' | 'createdDesc' | 'updatedAsc' | 'updatedDesc'>('idAsc');

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

  const filteredProducts = useMemo(() => {
    if (!products) return [];
    const q = keyword.trim().toLowerCase();
    const byKeyword = q.length === 0 ? products : products.filter((p) => `${p.name} ${p.label}`.toLowerCase().includes(q));
    const byPricing = pricingFilter === 'all' ? byKeyword : byKeyword.filter((p) => p.pricingBasisDefault === pricingFilter);
    const sorted = [...byPricing];

    if (sortMode === 'idDesc') sorted.sort((a, b) => b.id - a.id);
    else if (sortMode === 'createdAsc') sorted.sort((a, b) => toTs(a.createdAt) - toTs(b.createdAt));
    else if (sortMode === 'createdDesc') sorted.sort((a, b) => toTs(b.createdAt) - toTs(a.createdAt));
    else if (sortMode === 'updatedAsc') sorted.sort((a, b) => toTs(a.updatedAt) - toTs(b.updatedAt));
    else if (sortMode === 'updatedDesc') sorted.sort((a, b) => toTs(b.updatedAt) - toTs(a.updatedAt));
    else sorted.sort((a, b) => a.id - b.id);

    return sorted;
  }, [products, keyword, pricingFilter, sortMode]);

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (!products) return <LoadingState title="商品一覧を読み込み中" description="しばらくお待ちください" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="card">
        <div className="list-header">
          <div>
            <h2>商品マスタ</h2>
            <p className="subtle">作成・編集・アーカイブ・削除対応</p>
          </div>
          <div className="list-controls">
            <label className="filter-label">
              検索
              <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="商品名 / SKU" />
            </label>
            <label className="filter-label">
              課金基準
              <select value={pricingFilter} onChange={(e) => setPricingFilter(e.target.value as 'all' | 'uom_count' | 'uom_kg')}>
                <option value="all">すべて</option>
                <option value="uom_count">uom_count</option>
                <option value="uom_kg">uom_kg</option>
              </select>
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
            <Link to="/products/import" className="order-link">IMPORT</Link>
            <Link to="/products/new" className="order-link">+ 商品を作成</Link>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>SKU</th>
                <th>商品名</th>
                <th>注文単位</th>
                <th>課金基準</th>
                <th>作成日時</th>
                <th>更新日時</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="subtle">条件に合うデータがありません。検索・フィルタ条件を見直してください。</td>
                </tr>
              ) : filteredProducts.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.sku ?? '-'}</td>
                  <td>{p.name}</td>
                  <td>{p.orderUom}</td>
                  <td>{p.pricingBasisDefault}</td>
                  <td>{p.createdAt ?? '-'}</td>
                  <td>{p.updatedAt ?? '-'}</td>
                  <td>
                    <Link to={`/products/${p.id}`} className="order-link">詳細</Link>
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
