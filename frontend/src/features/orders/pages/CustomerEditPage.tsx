import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { CustomerForm } from 'features/orders/components/CustomerForm';
import { getCustomerDetail, updateCustomer } from 'features/orders/services/ordersService';
import type { CustomerDetail } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const CustomerEditPage = () => {
  const { customerId } = useParams();
  const navigate = useNavigate();
  const [customer, setCustomer] = useState<CustomerDetail | null | undefined>(undefined);
  const [error, setError] = useState('');

  const customerIdNum = useMemo(() => Number(customerId), [customerId]);

  useEffect(() => {
    if (!customerIdNum) {
      setError('不正な顧客IDです');
      return;
    }

    getCustomerDetail(customerIdNum)
      .then(setCustomer)
      .catch((e) => setError(toUserMessage(e, '顧客情報の取得に失敗しました')));
  }, [customerIdNum]);

  const handleSubmit = async (payload: Parameters<typeof updateCustomer>[1]) => {
    const updated = await updateCustomer(customerIdNum, { name: payload.name, active: payload.active });
    sessionStorage.setItem('osv2_toast', JSON.stringify({ type: 'success', message: `顧客を更新しました（ID: ${updated.id}）` }));
    navigate('/customers');
  };

  if (error) return <ErrorState title="データの取得に失敗しました" description={error} actionLabel="再試行" onAction={() => window.location.reload()} />;
  if (customer === undefined) return <LoadingState title="顧客情報を読み込み中" />;
  if (customer === null) return <EmptyState title="データがありません" description="対象データが見つかりません。一覧から再度選択してください。" actionLabel="再読み込み" onAction={() => window.location.reload()} />;

  return (
    <section>
      <CustomerForm initialValue={customer} submitLabel="顧客を保存" onSubmit={handleSubmit} />
    </section>
  );
};
