import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { SupplierForm } from 'features/suppliers/components/SupplierForm';
import { deactivateSupplier, getSupplier, updateSupplier } from 'features/suppliers/services/suppliersService';
import type { Supplier } from 'features/suppliers/types/supplier';
import { toUserMessage } from 'shared/error';

export const SupplierEditPage = () => {
  const { supplierId } = useParams();
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState<Supplier | null | undefined>(undefined);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);

  const supplierIdNum = useMemo(() => Number(supplierId), [supplierId]);

  useEffect(() => {
    if (!supplierIdNum) {
      setError('不正な仕入先IDです');
      return;
    }

    getSupplier(supplierIdNum)
      .then(setSupplier)
      .catch((e) => setError(toUserMessage(e, '仕入先情報の取得に失敗しました')));
  }, [supplierIdNum]);

  const handleSubmit = async (payload: { name: string; active: boolean }) => {
    const updated = await updateSupplier(supplierIdNum, { name: payload.name, active: payload.active });
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `仕入先を更新しました（ID: ${updated.id}）` }));
    navigate('/suppliers');
  };

  const handleDeactivate = async () => {
    if (!window.confirm('この仕入先を停止（active=false）します。よろしいですか？')) return;

    setDeleting(true);
    try {
      await deactivateSupplier(supplierIdNum);
      sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `仕入先を停止しました（ID: ${supplierIdNum}）` }));
      navigate('/suppliers');
    } catch (e) {
      setError(toUserMessage(e, '仕入先の停止に失敗しました'));
    } finally {
      setDeleting(false);
    }
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (supplier === undefined) return <LoadingState title="仕入先情報を読み込み中" />;
  if (supplier === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section>
      <SupplierForm initialValue={supplier} submitLabel="仕入先を保存" onSubmit={handleSubmit} />
      <div className="card" style={{ marginTop: 12 }}>
        <h3>停止（soft-delete）</h3>
        <p className="subtle">DELETE APIを呼び出し、active=false にします。</p>
        <button type="button" className="danger" onClick={handleDeactivate} disabled={deleting}>
          {deleting ? '停止中...' : 'この仕入先を停止'}
        </button>
      </div>
    </section>
  );
};
