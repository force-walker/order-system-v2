import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { archiveCustomer, deleteCustomer, getCustomerDetail, unarchiveCustomer } from 'features/customers/services/customersService';
import type { CustomerDetail } from 'features/customers/types/customer';
import { toUserMessage } from 'shared/error';

export const CustomerDetailPage = () => {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<CustomerDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  const load = async () => {
    const id = Number(customerId);
    if (!id) {
      setError('不正な顧客IDです');
      return;
    }
    setError('');
    try {
      const row = await getCustomerDetail(id);
      setCustomer(row);
    } catch (e) {
      setError(toUserMessage(e, '顧客詳細の取得に失敗しました'));
    }
  };

  useEffect(() => {
    load();
  }, [customerId]);

  const runAndBack = async (fn: () => Promise<unknown>, success: string) => {
    try {
      await fn();
      sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: success }));
      navigate('/customers');
    } catch (e) {
      setError(toUserMessage(e, '操作に失敗しました'));
    }
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (customer === undefined) return <LoadingState title="顧客詳細を読み込み中" />;
  if (customer === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h2>顧客詳細</h2>
      </div>
      <dl className="kv-list">
        <div><dt>ID</dt><dd>{customer.id}</dd></div>
        <div><dt>顧客コード</dt><dd>{customer.customerCode}</dd></div>
        <div><dt>顧客名</dt><dd>{customer.name}</dd></div>
        <div><dt>状態</dt><dd>{customer.active ? '有効' : '無効'}</dd></div>
      </dl>
      <div className="detail-actions">
        <Link to="/customers" className="order-link">顧客一覧へ戻る</Link>
        <Link to={`/customers/${customer.id}/edit`} className="order-link">顧客を編集</Link>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            const confirmed = window.confirm(`${customer.name} を${customer.active ? 'アーカイブ' : '復元'}しますか？`);
            if (!confirmed) return;
            void runAndBack(
              () => (customer.active ? archiveCustomer(customer.id) : unarchiveCustomer(customer.id)),
              customer.active ? '顧客をアーカイブしました' : '顧客を復元しました',
            );
          }}
        >
          {customer.active ? 'アーカイブ' : '復元'}
        </button>
        <button
          type="button"
          className="danger"
          onClick={() => {
            const confirmed = window.confirm(`${customer.name} を削除しますか？（参照がある場合は削除できません）`);
            if (!confirmed) return;
            void runAndBack(() => deleteCustomer(customer.id), '顧客を削除しました');
          }}
        >
          削除
        </button>
      </div>
    </section>
  );
};
