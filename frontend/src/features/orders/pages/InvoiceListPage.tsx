import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import { listCustomers } from 'features/customers/services/customersService';
import { exportInvoiceHistory, listInvoiceHistory, type InvoiceHistoryParams } from 'features/orders/services/invoiceService';
import type { CustomerOption, InvoiceHistoryRow } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';
import { hongKongDatePreset } from 'shared/hongKongDate';

const money = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'HKD' });
export const InvoiceListPage = () => {
  const [params, setParams] = useSearchParams();
  const [rows, setRows] = useState<InvoiceHistoryRow[]>([]); const [total, setTotal] = useState(0);
  const [customers, setCustomers] = useState<CustomerOption[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const value = (key: string, fallback = '') => params.get(key) ?? fallback;
  const query: InvoiceHistoryParams = { search: value('q'), dateFrom: value('from'), dateTo: value('to'), customerId: value('customer') ? Number(value('customer')) : undefined,
    invoiceStatus: params.has('status') ? (value('status') || 'all') : 'finalized', paymentStatus: value('payment'), overdue: value('overdue'), sort: value('sort', 'issue_date'), direction: value('dir', 'desc'), page: Number(value('page', '1')), pageSize: 50 };
  useEffect(() => { setLoading(true); setError(''); Promise.all([listInvoiceHistory(query), listCustomers()]).then(([result, customerRows]) => {
    setRows(result.items); setTotal(result.total); setCustomers(customerRows);
  }).catch((e) => setError(toActionableMessage(e, '請求履歴の取得に失敗しました'))).finally(() => setLoading(false)); }, [params.toString()]);
  const set = (key: string, nextValue: string) => { const next = new URLSearchParams(params); nextValue ? next.set(key, nextValue) : next.delete(key); if (key !== 'page') next.delete('page'); setParams(next); };
  const sort = (key: string) => { const next = new URLSearchParams(params); const same = value('sort', 'issue_date') === key; next.set('sort', key); next.set('dir', same && value('dir', 'desc') === 'desc' ? 'asc' : 'desc'); next.delete('page'); setParams(next); };
  const preset = (kind: 'today'|'week'|'month'|'year') => { const range = hongKongDatePreset(kind);
    const next = new URLSearchParams(params); next.set('from', range.from); next.set('to', range.to); next.delete('page'); setParams(next); };
  const detailContext = new URLSearchParams(params); detailContext.set('history', '1');
  if (error) return <ErrorState title="請求履歴の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求履歴を読み込み中" description="しばらくお待ちください。" />;
  return <section className="card"><h2>請求履歴 / Invoice History</h2><div className="list-controls">
    <label>検索<input value={value('q')} onChange={(e) => set('q', e.target.value)} placeholder="請求番号・取引先・SKU・商品名" /></label>
    <button onClick={() => preset('today')}>今日</button><button onClick={() => preset('week')}>今週</button><button onClick={() => preset('month')}>今月</button><button onClick={() => preset('year')}>今年</button>
    <label>開始日<input type="date" value={value('from')} onChange={(e) => set('from', e.target.value)} /></label><label>終了日<input type="date" value={value('to')} onChange={(e) => set('to', e.target.value)} /></label>
    <label>取引先<select value={value('customer')} onChange={(e) => set('customer', e.target.value)}><option value="">全取引先</option>{customers.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</select></label>
    <label>請求Status<select value={value('status', 'finalized')} onChange={(e) => set('status', e.target.value)}><option value="all">全Status</option>{['draft','finalized','sent','cancelled'].map(s => <option key={s}>{s}</option>)}</select></label>
    <label>回収Status<select value={value('payment')} onChange={(e) => set('payment', e.target.value)}><option value="">全Status</option>{['unpaid','partially_paid','paid'].map(s => <option key={s}>{s}</option>)}</select></label>
    <label>期限超過<select value={value('overdue')} onChange={(e) => set('overdue', e.target.value)}><option value="">すべて</option><option value="true">期限超過のみ</option><option value="false">期限内のみ</option></select></label>
    <button onClick={() => void exportInvoiceHistory('headers', query)}>Header CSV</button><button onClick={() => void exportInvoiceHistory('lines', query)}>Line CSV</button></div>
    <div className="table-wrap"><table><thead><tr>{[['issue_date','Issue Date'],['due_date','Due Date'],['invoice_no','Invoice No'],['customer','Customer'],['invoice_status','Invoice Status'],['payment_status','Payment Status']].map(([k,l]) => <th key={k}><button className="link-button" onClick={() => sort(k)}>{l}</button></th>)}<th>期限超過</th><th>行数</th><th>Subtotal</th><th>Tax</th><th><button className="link-button" onClick={() => sort('total')}>Total</button></th><th>詳細</th></tr></thead><tbody>
      {rows.map(r => <tr key={String(r.invoiceId)}><td>{r.issueDate}</td><td>{r.dueDate ?? '-'}</td><td>{r.invoiceNo}</td><td>{r.customerName}</td><td>{r.invoiceStatus}</td><td>{r.paymentStatus}</td><td>{r.overdue ? '期限超過' : ''}</td><td>{r.lineCount}</td><td>{money.format(r.subtotal)}</td><td>{money.format(r.tax)}</td><td>{money.format(r.total)}</td><td><Link to={`/invoices/${r.invoiceId}?${detailContext}`}>詳細</Link></td></tr>)}</tbody></table></div>
    {rows.length === 0 ? <p>条件に一致する請求書はありません。</p> : null}<div className="form-actions"><button disabled={query.page === 1} onClick={() => set('page', String((query.page ?? 1)-1))}>← 前へ</button><span>{query.page} / {Math.max(1, Math.ceil(total/50))}</span><button disabled={(query.page ?? 1)*50 >= total} onClick={() => set('page', String((query.page ?? 1)+1))}>次へ →</button></div>
  </section>;
};
