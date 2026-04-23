import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listInvoiceDrafts } from 'features/orders/services/invoiceService';
import { listCustomers } from 'features/orders/services/ordersService';
import type { CustomerOption, InvoiceDraftSummary, InvoiceStatus } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

export const InvoiceDraftPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftSummary[]>([]);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);

  const [customerFilter, setCustomerFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | ''>('draft');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const [drafts, customerOpts] = await Promise.all([listInvoiceDrafts(), listCustomers()]);
        setRows(drafts);
        setCustomers(customerOpts);
      } catch (e) {
        setError(toActionableMessage(e, '請求ドラフト一覧の取得に失敗しました。'));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const customerNameMap = useMemo(() => {
    const map = new Map<number, string>();
    customers.forEach((c) => map.set(c.id, c.label));
    return map;
  }, [customers]);

  const filtered = useMemo(() => {
    const cq = customerFilter.trim().toLowerCase();
    return rows.filter((r) => {
      const customerName = customerNameMap.get(r.customerId) ?? `顧客#${r.customerId}`;
      if (statusFilter && r.status !== statusFilter) return false;
      if (dateFilter && r.deliveryDate !== dateFilter) return false;
      if (cq && !customerName.toLowerCase().includes(cq)) return false;
      return true;
    });
  }, [rows, customerNameMap, customerFilter, dateFilter, statusFilter]);

  if (error) return <ErrorState title="請求ドラフト一覧の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求ドラフト一覧を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求ドラフト一覧</h2>
            <p className="subtle">draftのみを作業対象として表示します。</p>
          </div>
        </div>

        <div className="list-controls" style={{ marginBottom: 12 }}>
          <label className="filter-label">
            顧客
            <input value={customerFilter} onChange={(e) => setCustomerFilter(e.target.value)} placeholder="顧客名で検索" />
          </label>
          <label className="filter-label">
            対象日
            <input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} />
          </label>
          <label className="filter-label">
            ステータス
            <select value={statusFilter} onChange={(e) => setStatusFilter((e.target.value || '') as InvoiceStatus | '')}>
              <option value="">all</option>
              <option value="draft">draft</option>
              <option value="finalized">finalized</option>
              <option value="sent">sent</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
        </div>

        {filtered.length === 0 ? (
          <EmptyState title="表示対象がありません" description="条件に合う請求ドラフトがありません。" />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>顧客</th>
                  <th>対象日</th>
                  <th>明細件数</th>
                  <th>合計</th>
                  <th>status</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id}>
                    <td>{customerNameMap.get(row.customerId) ?? `顧客#${row.customerId}`}</td>
                    <td>{row.deliveryDate}</td>
                    <td>{row.itemCount}</td>
                    <td>{row.grandTotal}</td>
                    <td>{row.status}</td>
                    <td><Link to={`/invoices/drafts/${row.id}`}>詳細</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
};
