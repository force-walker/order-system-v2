import { useEffect,useState } from 'react';
import { useParams } from 'react-router-dom';
import { RelatedDocuments } from 'components/common/RelatedDocuments';
import { apiRequestWithAuth } from 'shared/authenticatedApiClient';
import { toActionableMessage } from 'shared/error';

type Delivery={id:string;delivery_no:string;delivery_date:string;shipped_date:string;order_id:string};
export const DeliveryDetailPage=()=>{const{id=''}=useParams();const[data,setData]=useState<Delivery>();const[error,setError]=useState('');
  useEffect(()=>{apiRequestWithAuth(`/api/v1/deliveries/${id}`).then(async r=>{if(!r.ok)throw new Error('Deliveryの取得に失敗しました');setData(await r.json())}).catch(e=>setError(toActionableMessage(e,'Deliveryの取得に失敗しました')))},[id]);
  if(error)return <section className="card"><p className="error">{error}</p></section>;if(!data)return <section className="card">読み込み中...</section>;
  return <section><div className="card"><h2>{data.delivery_no}</h2><p>納品日: {data.delivery_date}</p><p>出荷日: {data.shipped_date}</p></div><RelatedDocuments type="delivery" id={data.id}/></section>};
