import { useEffect, useMemo, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  createSupplierProductMappingGlobal,
  deleteSupplierProductMappingById,
  listProductSupplierMappings,
  listSuppliers,
  updateSupplierProductMappingById,
} from 'features/suppliers/services/suppliersService';
import type { Supplier, SupplierProductMapping } from 'features/suppliers/types/supplier';
import { toActionableMessage } from 'shared/error';

type Props = {
  productId: number;
};

type FormState = {
  supplierId: number;
  priority: number;
  isPreferred: boolean;
  defaultUnitCost: string;
  leadTimeDays: string;
  note: string;
};

const initialForm: FormState = {
  supplierId: 0,
  priority: 100,
  isPreferred: false,
  defaultUnitCost: '',
  leadTimeDays: '',
  note: '',
};

const toPayload = (f: FormState) => ({
  supplierId: f.supplierId,
  productId: 0,
  priority: f.priority,
  isPreferred: f.isPreferred,
  defaultUnitCost: f.defaultUnitCost === '' ? null : Number(f.defaultUnitCost),
  leadTimeDays: f.leadTimeDays === '' ? null : Number(f.leadTimeDays),
  note: f.note.trim() ? f.note.trim() : null,
});

export const ProductSupplierMappingPanel = ({ productId }: Props) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [mappings, setMappings] = useState<SupplierProductMapping[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(initialForm);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [rows, supplierResult] = await Promise.all([
        listProductSupplierMappings(productId),
        listSuppliers({ active: 'all', includeInactive: true, limit: 200, offset: 0 }),
      ]);
      setMappings(rows);
      setSuppliers(supplierResult.items);
    } catch (e) {
      setError(toActionableMessage(e, '取扱仕入先マッピングの取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [productId]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  const mappedSupplierIds = useMemo(() => new Set(mappings.map((m) => m.supplierId)), [mappings]);
  const selectableSuppliers = useMemo(
    () => (editingId ? suppliers : suppliers.filter((s) => !mappedSupplierIds.has(s.id))),
    [suppliers, editingId, mappedSupplierIds],
  );

  const resetForm = () => {
    setEditingId(null);
    setForm(initialForm);
  };

  const onCreate = async () => {
    try {
      await createSupplierProductMappingGlobal({ ...toPayload(form), productId });
      setToast({ type: 'success', message: 'マッピングを追加しました。' });
      resetForm();
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, 'マッピング追加に失敗しました。') });
    }
  };

  const onUpdate = async () => {
    if (!editingId) return;
    try {
      await updateSupplierProductMappingById(editingId, {
        priority: form.priority,
        isPreferred: form.isPreferred,
        defaultUnitCost: form.defaultUnitCost === '' ? null : Number(form.defaultUnitCost),
        leadTimeDays: form.leadTimeDays === '' ? null : Number(form.leadTimeDays),
        note: form.note.trim() ? form.note.trim() : null,
      });
      setToast({ type: 'success', message: 'マッピングを更新しました。' });
      resetForm();
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, 'マッピング更新に失敗しました。') });
    }
  };

  const onDelete = async (mapping: SupplierProductMapping) => {
    const supplierName = suppliers.find((s) => s.id === mapping.supplierId)?.name ?? `仕入先#${mapping.supplierId}`;
    if (!window.confirm(`「${supplierName}」のマッピングを解除しますか？`)) return;

    try {
      await deleteSupplierProductMappingById(mapping.id);
      setToast({ type: 'success', message: 'マッピングを解除しました。' });
      if (editingId === mapping.id) resetForm();
      await load();
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, 'マッピング解除に失敗しました。') });
    }
  };

  const startEdit = (m: SupplierProductMapping) => {
    setEditingId(m.id);
    setForm({
      supplierId: m.supplierId,
      priority: m.priority,
      isPreferred: m.isPreferred,
      defaultUnitCost: m.defaultUnitCost == null ? '' : String(m.defaultUnitCost),
      leadTimeDays: m.leadTimeDays == null ? '' : String(m.leadTimeDays),
      note: m.note ?? '',
    });
  };

  if (error) return <ErrorState title="取扱仕入先マッピング取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />;
  if (loading) return <LoadingState title="取扱仕入先マッピングを読み込み中" />;

  return (
    <section className="card detail-layout">
      <div className="detail-header">
        <h3>取扱仕入先マッピング</h3>
      </div>

      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}

      {mappings.length === 0 ? (
        <EmptyState title="マッピングがありません" description="下のフォームから仕入先を追加してください。" />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>supplier_id</th>
                <th>priority</th>
                <th>preferred</th>
                <th>default_unit_cost</th>
                <th>lead_time_days</th>
                <th>note</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((m) => {
                const supplier = suppliers.find((s) => s.id === m.supplierId);
                return (
                  <tr key={m.id}>
                    <td>{m.supplierId} {supplier ? `(${supplier.name})` : ''}</td>
                    <td>{m.priority}</td>
                    <td>{m.isPreferred ? 'true' : 'false'}</td>
                    <td>{m.defaultUnitCost ?? '-'}</td>
                    <td>{m.leadTimeDays ?? '-'}</td>
                    <td>{m.note ?? '-'}</td>
                    <td>
                      <button type="button" className="secondary" onClick={() => startEdit(m)}>更新</button>
                      {' / '}
                      <button type="button" className="danger" onClick={() => void onDelete(m)}>解除</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="form-section">
        <h3>{editingId ? 'マッピング更新' : 'マッピング追加'}</h3>
        <div className="form-grid three-col">
          <label>
            仕入先
            <select
              value={form.supplierId}
              disabled={Boolean(editingId)}
              onChange={(e) => setForm((prev) => ({ ...prev, supplierId: Number(e.target.value) }))}
            >
              <option value={0}>選択してください</option>
              {selectableSuppliers.map((s) => <option key={s.id} value={s.id}>{`${s.id}: ${s.name}`}</option>)}
            </select>
          </label>

          <label>
            priority
            <input type="number" min={1} max={9999} value={form.priority} onChange={(e) => setForm((prev) => ({ ...prev, priority: Number(e.target.value) }))} />
          </label>

          <label>
            lead_time_days
            <input type="number" min={0} value={form.leadTimeDays} onChange={(e) => setForm((prev) => ({ ...prev, leadTimeDays: e.target.value }))} />
          </label>

          <label>
            default_unit_cost
            <input type="number" min={0} step="0.01" value={form.defaultUnitCost} onChange={(e) => setForm((prev) => ({ ...prev, defaultUnitCost: e.target.value }))} />
          </label>

          <label>
            note
            <input value={form.note} onChange={(e) => setForm((prev) => ({ ...prev, note: e.target.value }))} />
          </label>

          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={form.isPreferred} onChange={(e) => setForm((prev) => ({ ...prev, isPreferred: e.target.checked }))} />
            preferred
          </label>
        </div>

        <div className="form-actions" style={{ marginTop: 12 }}>
          {editingId ? (
            <>
              <button type="button" className="secondary" onClick={resetForm}>キャンセル</button>
              <button type="button" onClick={() => void onUpdate()} disabled={!form.supplierId}>更新する</button>
            </>
          ) : (
            <button type="button" onClick={() => void onCreate()} disabled={!form.supplierId}>追加する</button>
          )}
        </div>
      </div>
    </section>
  );
};
