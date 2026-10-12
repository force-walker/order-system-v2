import { apiRequestWithAuth } from 'shared/authenticatedApiClient';
import { parseApiErrorPayload } from 'shared/error';

export type RelatedDocumentType = 'order'|'delivery'|'invoice'|'supplier_bill';
export type RelatedDocument = {type:RelatedDocumentType;id:string;number:string;status:string|null};
export type RelatedDocumentsResponse = {
  orders:RelatedDocument[]; deliveries:RelatedDocument[]; invoices:RelatedDocument[]; supplier_bills:RelatedDocument[];
};

export const getRelatedDocuments = async(type:RelatedDocumentType,id:string):Promise<RelatedDocumentsResponse> => {
  const response=await apiRequestWithAuth(`/api/v1/related-documents/${type}/${id}`);
  if(!response.ok)throw await parseApiErrorPayload(response);
  return response.json() as Promise<RelatedDocumentsResponse>;
};
