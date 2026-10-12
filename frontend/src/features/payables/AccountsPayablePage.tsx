import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { listSuppliers } from 'features/suppliers/services/suppliersService';
import { createBill, exportBills, listBills, listCandidates, type Bill, type Candidate } from './payablesService';
import { toActionableMessage } from 'shared/error';
import { hongKongDatePreset, hongKongToday } from 'shared/hongKongDate';

const money = (currency: string, value: number) => new Intl.NumberFormat('ja-JP', { style: 'currency', currency }).format(value);
const sortable = [['bill_date','Bill Date'],['due_date','Due Date'],['bill_no','AP Bill No'],['supplier_invoice_no','Supplier Invoice No'],['supplier','Supplier'],['status','Status'],['total','Total']] as const;

export const AccountsPayablePage = () => {
  const [params, setParams] = useSearchParams(); const navigate = useNavigate();
  const [tab, setTab] = useState<'bills'|'candidates'>('bills'); const [bills, setBills] = useState<Bill[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]); const [suppliers, setSuppliers] = useState<Array<{id:number;name:string}>>([]);
  const [selected, setSelected] = useState<number[]>([]); const [total, setTotal] = useState(0); const [error, setError] = useState('');
  const [invoiceNo, setInvoiceNo] = useState(''); const [billDate, setBillDate] = useState(hongKongToday());
  const query = params.toString(); const value = (key:string, fallback='') => params.get(key) ?? fallback;
  const set = (key:string, nextValue:string) => { const next=new URLSearchParams(params); nextValue?next.set(key,nextValue):next.delete(key); if(key!=='page')next.delete('page'); setParams(next); };
  const preset = (kind:'today'|'week'|'month'|'year') => { const range=hongKongDatePreset(kind); const next=new URLSearchParams(params); next.set('date_from',range.from);next.set('date_to',range.to);next.delete('page');setParams(next); };
  const sort = (key:string) => { const next=new URLSearchParams(params);const same=value('sort','document_seq')===key;next.set('sort',key);next.set('direction',same&&value('direction','desc')==='desc'?'asc':'desc');next.delete('page');setParams(next); };
  const load = () => Promise.all([listBills(query),listCandidates(),listSuppliers({active:'all',includeInactive:true,limit:500,offset:0})]).then(([b,c,s])=>{setBills(b.items);setTotal(b.total);setCandidates(c);setSuppliers(s.items)}).catch(e=>setError(toActionableMessage(e,'買掛金の取得に失敗しました')));
  useEffect(()=>{void load()},[query]);
  const create = async () => { try { setError(''); const rows=candidates.filter(x=>selected.includes(x.purchase_result_id)); if(new Set(rows.map(x=>x.supplier_id)).size!==1)throw new Error('同じ仕入先の仕入だけを選択してください'); const bill=await createBill({purchase_result_ids:selected,supplier_invoice_no:invoiceNo,bill_date:billDate,currency:'JPY'});navigate(`/payables/${bill.id}`); } catch(e){setError(toActionableMessage(e,'買掛Draftの作成に失敗しました'));} };
  const exportFile = async (kind:'headers'|'lines') => { try { setError(''); await exportBills(kind,query); } catch(e) { setError(toActionableMessage(e,'CSVの出力に失敗しました')); } };
  return <section className="card"><h2>買掛金 / Accounts Payable</h2>{error&&<p className="error">{error}</p>}
    <div className="form-actions"><button onClick={()=>setTab('bills')}>買掛一覧</button><button onClick={()=>setTab('candidates')}>未計上仕入</button></div>
    {tab==='bills'?<><div className="list-controls">
      <label>検索<input value={value('search')} onChange={e=>set('search',e.target.value)} placeholder="AP番号・仕入先請求番号・仕入先・SKU・商品"/></label>
      <button onClick={()=>preset('today')}>今日</button><button onClick={()=>preset('week')}>今週</button><button onClick={()=>preset('month')}>今月</button><button onClick={()=>preset('year')}>今年</button>
      <label>開始日<input type="date" value={value('date_from')} onChange={e=>set('date_from',e.target.value)}/></label><label>終了日<input type="date" value={value('date_to')} onChange={e=>set('date_to',e.target.value)}/></label>
      <label>仕入先<select value={value('supplier_id')} onChange={e=>set('supplier_id',e.target.value)}><option value="">全仕入先</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>Bill Status<select value={value('bill_status')} onChange={e=>set('bill_status',e.target.value)}><option value="">全Status</option><option>draft</option><option>finalized</option><option>cancelled</option></select></label>
      <label>支払Status<select value={value('payment_status')} onChange={e=>set('payment_status',e.target.value)}><option value="">全Status</option><option>unpaid</option><option>partially_paid</option><option>paid</option></select></label>
      <label>期限超過のみ<input type="checkbox" checked={value('overdue')==='true'} onChange={e=>set('overdue',e.target.checked?'true':'')}/></label>
      <button onClick={()=>void exportFile('headers')}>Header CSV</button><button onClick={()=>void exportFile('lines')}>Line CSV</button></div>
      <div className="table-wrap"><table><thead><tr>{sortable.map(([key,label])=><th key={key}><button className="invoice-history-sort" onClick={()=>sort(key)}>{label}</button></th>)}<th>Payment</th><th>Paid</th><th>Outstanding</th><th></th></tr></thead><tbody>{bills.map(x=><tr key={x.id}><td>{x.bill_date}</td><td>{x.due_date??'-'}</td><td>{x.bill_no}</td><td>{x.supplier_invoice_no}</td><td>{x.supplier_name}</td><td>{x.status}</td><td>{money(x.currency,x.total_amount)}</td><td>{x.payment_status??'-'}{x.overdue?' / 期限超過':''}</td><td>{money(x.currency,x.paid_amount)}</td><td>{money(x.currency,x.outstanding_amount)}</td><td><Link to={`/payables/${x.id}?history=1&${query}`}>詳細</Link></td></tr>)}</tbody></table></div>
      <div className="form-actions"><button disabled={Number(value('page','1'))<=1} onClick={()=>set('page',String(Number(value('page','1'))-1))}>← 前へ</button><span>{total}件</span><button disabled={Number(value('page','1'))*50>=total} onClick={()=>set('page',String(Number(value('page','1'))+1))}>次へ →</button></div></>:
      <><div className="form-grid"><label>仕入先請求番号<input value={invoiceNo} onChange={e=>setInvoiceNo(e.target.value)}/></label><label>Bill Date<input type="date" value={billDate} onChange={e=>setBillDate(e.target.value)}/></label><button disabled={!selected.length||!invoiceNo.trim()} onClick={()=>void create()}>Draft作成</button></div>
      <div className="table-wrap"><table><thead><tr><th></th><th>Purchase Date</th><th>Supplier</th><th>Order</th><th>SKU</th><th>Product</th><th>実数量</th><th>UOM</th><th>仕入単価</th><th>金額</th></tr></thead><tbody>{candidates.map(x=><tr key={x.purchase_result_id}><td><input aria-label={`${x.sku}を選択`} type="checkbox" checked={selected.includes(x.purchase_result_id)} onChange={e=>setSelected(s=>e.target.checked?[...s,x.purchase_result_id]:s.filter(i=>i!==x.purchase_result_id))}/></td><td>{x.purchase_date}</td><td>{x.supplier_name}</td><td>{x.order_no}</td><td>{x.sku}</td><td>{x.product_name}</td><td>{x.quantity}</td><td>{x.uom}</td><td>{x.unit_cost??'仕入単価未入力'}</td><td>{x.amount??'金額未確定'}</td></tr>)}</tbody></table></div></>}
  </section>;
};
