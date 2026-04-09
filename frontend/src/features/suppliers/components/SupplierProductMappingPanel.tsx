import { useEffect, useMemo, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listProducts } from 'features/products/services/productsService';
import {
  createSupplierProductMapping,
  deleteSupplierProductMapping,
  listSupplierProductMappings,
  updateSupplierProductMapping,
} from 'features/suppliers/services/suppliersService';
import type { SupplierProductMapping } from 'features/suppliers/types/supplier';
import type { ProductOption } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

type Props = {
  supplierId: number;
};

type MappingFormState = {
  productId: number;
  priority: number;
  isPreferred: boolean;
  defaultUnitCost: string;
  leadTimeDays: string;
  note: string;
};

const initialFormState: MappingFormState = {
  productId: 0,
  priority: 100,
  isPreferred: false,
  defaultUnitCost: '',
  leadTimeDays: '',
  note: '',
};

const toCreatePayload = (state: MappingFormState) => ({
  productId: state.productId,
  priority: state.priority,
  isPreferred: state.isPreferred,
  defaultUnitCost: state.defaultUnitCost === '' ? null : Number(state.defaultUnitCost),
  leadTimeDays: state.leadTimeDays === '' ? null : Number(state.leadTimeDays),
  note: state.note.trim() ? state.note.trim() : null,
});

export const SupplierProductMappingPanel = ({ supplierId }: Props) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mappings, setMappings] = useState<SupplierProductMapping[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [toast, setToast] = useState<string>('');
  const [submitError, setSubmitError] = useState('');
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [form, setForm] = useState<MappingFormState>(initialFormState);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [rows, productOptions] = await Promise.all([
        listSupplierProductMappings(supplierId),
        listProducts(true),
      ]);
      setMappings(rows);
      setProducts(productOptions);
    } catch (e) {
      setError(toActionableMessage(e, '仕入先×商品マッピングの取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [supplierId]);

  const mappedIds = useMemo(() => new Set(mappings.map((m) => m.productId)), [mappings]);
  const creatableProducts = useMemo(
    () => products.filter((p) => !mappedIds.has(p.id)),
    [products, mappedIds],
  );

  const resetForm = () => {
    setForm(initialFormState);
    setEditingProductId(null);
    setSubmitError('');
  };

  const submitCreate = async () => {
    setSubmitError('');
    setToast('');
    try {
      await createSupplierProductMapping(supplierId, toCreatePayload(form));
      setToast('マッピングを追加しました。');
      resetForm();
      await load();
    } catch (e) {
      setSubmitError(toActionableMessage(e, 'マッピング追加に失敗しました。'));
    }
  };

  const submitUpdate = async () => {
    if (!editingProductId) return;
    setSubmitError('');
    setToast('');
    try {
      await updateSupplierProductMapping(supplierId, editingProductId, toCreatePayload(form));
      setToast('マッピングを更新しました。');
      resetForm();
      await load();
    } catch (e) {
      setSubmitError(toActionableMessage(e, 'マッピング更新に失敗しました。'));
    }
  };

  const removeMapping = async (productId: number, productName: string) => {
    if (!window.confirm(`「${productName}」のマッピングを解除しますか？`)) return;
    setToast('');
    setSubmitError('');
    try {
      await deleteSupplierProductMapping(supplierId, productId);
      setToast('マッピングを解除しました。');
      if (editingProductId === productId) resetForm();
      await load();
    } catch (e) {
      setSubmitError(toActionableMessage(e, 'マッピング解除に失敗しました。'));
    }
  };

  const startEdit = (row: SupplierProductMapping) => {
    setEditingProductId(row.productId);
    setForm({
      productId: row.productId,
      priority: row.priority,
      isPreferred: row.isPreferred,
      defaultUnitCost: row.defaultUnitCost == null ? '' : String(row.defaultUnitCost),
      leadTimeDays: row.leadTimeDays == null ? '' : String(row.leadTimeDays),
      note: row.note ?? '',
    });
    setSubmitError('');
  };

  if (error) {
    return <ErrorState title="マッピング取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  }
  if (loading) {
    return <LoadingState title="マッピングを読み込み中" description="仕入先に紐づく商品を取得しています。" />;
  }

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h3>仕入先×商品マッピング</h3>
      </div>

      {toast ? <div className="toast success">{toast}</div> : null}
      {submitError ? <div className="toast error">{submitError}</div> : null}

      <div className="table-wrap">
        {mappings.length === 0 ? (
          <EmptyState title="マッピングがありません" description="下のフォームから商品を追加してください。" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>product_id</th>
                <th>priority</th>
                <th>preferred</th>
                <th>default_unit_cost</th>
                <th>lead_time_days</th>
                <th>note</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((row) => {
                const product = products.find((p) => p.id === row.productId);
                return (
                  <tr key={row.id}>
                    <td>{row.productId} {product ? `(${product.name})` : ''}</td>
                    <td>{row.priority}</td>
                    <td>{row.isPreferred ? 'true' : 'false'}</td>
                    <td>{row.defaultUnitCost ?? '-'}</td>
                    <td>{row.leadTimeDays ?? '-'}</td>
                    <td>{row.note ?? '-'}</td>
                    <td>
                      <button type="button" className="secondary" onClick={() => startEdit(row)}>更新</button>
                      {' / '}
                      <button
                        type="button"
                        className="danger"
                        onClick={() => removeMapping(row.productId, product?.name ?? `商品#${row.productId}`)}
                      >
                        解除
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="form-section">
        <h3>{editingProductId ? 'マッピング更新' : 'マッピング追加'}</h3>
        <div className="form-grid three-col">
          <label>
            商品
            <select
              value={form.productId}
              disabled={Boolean(editingProductId)}
              onChange={(e) => setForm((prev) => ({ ...prev, productId: Number(e.target.value) }))}
            >
              <option value={0}>選択してください</option>
              {(editingProductId ? products : creatableProducts).map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </label>
          <label>
            priority
            <input
              type="number"
              min={1}
              max={9999}
              value={form.priority}
              onChange={(e) => setForm((prev) => ({ ...prev, priority: Number(e.target.value) }))}
            />
          </label>
          <label>
            lead_time_days
            <input
              type="number"
              min={0}
              value={form.leadTimeDays}
              onChange={(e) => setForm((prev) => ({ ...prev, leadTimeDays: e.target.value }))}
            />
          </label>
          <label>
            default_unit_cost
            <input
              type="number"
              min={0}
              step="0.01"
              value={form.defaultUnitCost}
              onChange={(e) => setForm((prev) => ({ ...prev, defaultUnitCost: e.target.value }))}
            />
          </label>
          <label>
            note
            <input value={form.note} onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))} />
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={form.isPreferred}
              onChange={(e) => setForm((prev) => ({ ...prev, isPreferred: e.target.checked }))}
            />
            preferred
          </label>
        </div>

        <div className="form-actions" style={{ marginTop: 12 }}>
          {editingProductId ? (
            <>
              <button type="button" className="secondary" onClick={resetForm}>キャンセル</button>
              <button type="button" onClick={() => void submitUpdate()} disabled={!form.productId}>更新する</button>
            </>
          ) : (
            <button type="button" onClick={() => void submitCreate()} disabled={!form.productId}>追加する</button>
          )}
        </div>
      </div>
    </section>
  );
};
