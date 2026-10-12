import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getRelatedDocuments, type RelatedDocument, type RelatedDocumentType, type RelatedDocumentsResponse } from './relatedDocumentsService';
import { toActionableMessage } from 'shared/error';

const route = (row: RelatedDocument) => {
  if (row.type === 'order') return `/orders/${row.id}/edit`;
  if (row.type === 'invoice') return row.status === 'draft' ? `/invoices/drafts/${row.id}` : `/invoices/${row.id}`;
  return `/payables/${row.id}`;
};

const groups: Array<[keyof RelatedDocumentsResponse, string]> = [
  ['orders', '受注'],
  ['invoices', '請求'],
  ['supplier_bills', '仕入請求'],
];

export const RelatedDocuments = ({ type, id }: { type: RelatedDocumentType; id: string }) => {
  const [data, setData] = useState<RelatedDocumentsResponse>();
  const [error, setError] = useState('');

  useEffect(() => {
    setData(undefined);
    setError('');
    getRelatedDocuments(type, id).then(setData).catch((e) => setError(toActionableMessage(e, '関連データの取得に失敗しました')));
  }, [type, id]);

  if (error) return <span className="related-document-error">{error}</span>;
  if (!data) return null;

  const visibleGroups = groups
    .map(([key, label]) => [key, label, data[key].filter((row) => !(row.type === type && row.id === id))] as const)
    .filter(([, , rows]) => rows.length > 0);
  if (visibleGroups.length === 0) return null;

  return <nav className="related-document-buttons" aria-label="関連データ">
    {visibleGroups.map(([key, label, rows]) => rows.length === 1 ? (
      <Link className="related-document-button" key={key} to={route(rows[0])}><span>{label}</span><strong>{rows.length}</strong></Link>
    ) : (
      <details className="related-document-menu" key={key}>
        <summary className="related-document-button"><span>{label}</span><strong>{rows.length}</strong></summary>
        <div className="related-document-menu-items">
          {rows.map((row) => <Link key={row.id} to={route(row)}>{row.number}{row.status ? ` / ${row.status}` : ''}</Link>)}
        </div>
      </details>
    ))}
  </nav>;
};
