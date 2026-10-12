import { useEffect,useState } from 'react';
import { Link } from 'react-router-dom';
import { getRelatedDocuments,type RelatedDocument,type RelatedDocumentType,type RelatedDocumentsResponse } from './relatedDocumentsService';
import { toActionableMessage } from 'shared/error';

const route=(row:RelatedDocument)=>row.type==='order'?`/orders/${row.id}/edit`:row.type==='delivery'?`/deliveries/${row.id}`:row.type==='invoice'?(row.status==='draft'?`/invoices/drafts/${row.id}`:`/invoices/${row.id}`):`/payables/${row.id}`;
const groups:[keyof RelatedDocumentsResponse,string,RelatedDocumentType][]=[['orders','受注','order'],['deliveries','納品','delivery'],['invoices','請求','invoice'],['supplier_bills','仕入請求','supplier_bill']];

export const RelatedDocuments=({type,id}:{type:RelatedDocumentType;id:string})=>{
  const[data,setData]=useState<RelatedDocumentsResponse>();const[error,setError]=useState('');
  useEffect(()=>{setData(undefined);setError('');getRelatedDocuments(type,id).then(setData).catch(e=>setError(toActionableMessage(e,'関連伝票の取得に失敗しました')))},[type,id]);
  return <section className="card"><h3>関連伝票</h3>{error?<p className="error">{error}</p>:!data?<p className="subtle">読み込み中...</p>:groups.map(([key,label,documentType])=><div key={key}><strong>{label}</strong><ul>{data[key].length?data[key].map(row=><li key={row.id}>{row.type===type&&row.id===id?<span>{row.number}（現在）{row.status?` / ${row.status}`:''}</span>:<Link to={route(row)}>{row.number}{row.status?` / ${row.status}`:''}</Link>}</li>):<li className="subtle">未作成</li>}</ul></div>)}</section>;
};
