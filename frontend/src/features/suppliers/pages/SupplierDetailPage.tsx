import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveSupplier, deleteSupplier, getSupplier, unarchiveSupplier } from 'features/suppliers/services/suppliersService';
import type { Supplier } from 'features/suppliers/types/supplier';
import { toUserMessage } from 'shared/error';

export const SupplierDetailPage = () => {
  const { supplierId } = useParams();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState<Supplier | null | undefined>(undefined);
  const [error, setError] = useState('');

  const load = async () => {
    const id = Number(supplierId);
    if (!id) {
      setError('不正な仕入先IDです');
      return;
    }
    setError('');
    try {
      const row = await getSupplier(id);
      setSupplier(row);
    } catch (e) {
      setError(toUserMessage(e, '仕入先詳細の取得に失敗しました'));
    }
  };

  useEffect(() => {
    load();
  }, [supplierId]);

  const runAndBack = async (fn: () => Promise<unknown>, success: string) => {
    try {
      await fn();
      sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: success }));
      navigate('/suppliers');
    } catch (e) {
      setError(toUserMessage(e, '操作に失敗しました'));
    }
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (supplier === undefined) return <LoadingState title="仕入先詳細を読み込み中" />;
  if (supplier === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h2>仕入先詳細</h2>
      </div>
      <dl className="kv-list">
        <div><dt>ID</dt><dd>{supplier.id}</dd></div>
        <div><dt>仕入先コード</dt><dd>{supplier.supplierCode}</dd></div>
        <div><dt>仕入先名</dt><dd>{supplier.name}</dd></div>
        <div><dt>状態</dt><dd>{supplier.active ? '有効' : '無効'}</dd></div>
      </dl>
      <div className="detail-actions">
        <Link to="/suppliers" className="order-link">仕入先一覧へ戻る</Link>
        <Link to={`/suppliers/${supplier.id}/edit`} className="order-link">仕入先を編集</Link>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            const confirmed = window.confirm(`${supplier.name} を${supplier.active ? 'アーカイブ' : '復元'}しますか？`);
            if (!confirmed) return;
            void runAndBack(
              () => (supplier.active ? archiveSupplier(supplier.id) : unarchiveSupplier(supplier.id)),
              supplier.active ? '仕入先をアーカイブしました' : '仕入先を復元しました',
            );
          }}
        >
          {supplier.active ? 'アーカイブ' : '復元'}
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => {
            const confirmed = window.confirm(`${supplier.name} を削除しますか？（参照がある場合は削除できません）`);
            if (!confirmed) return;
            void runAndBack(() => deleteSupplier(supplier.id), '仕入先を削除しました');
          }}
        >
          削除
        </button>
      </div>
    </section>
  );
};
