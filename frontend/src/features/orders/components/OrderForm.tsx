import { useMemo, useState, type FormEvent } from 'react';
import type { CreateOrderRequest, CustomerOption, ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

type Props = {
  onSubmit: (payload: CreateOrderRequest) => Promise<void>;
  customers: CustomerOption[];
  products: ProductOption[];
};

type ItemForm = {
  productId: string;
  productName: string;
  quantity: string;
  unit: string;
  unitPrice: string;
  pricingBasis: 'uom_count' | 'uom_kg';
};

type FormState = {
  customerId: string;
  customerName: string;
  deliveryDate: string;
  note: string;
  items: ItemForm[];
};

type FieldErrors = {
  customerId?: string;
  customerName?: string;
  deliveryDate?: string;
  note?: string;
  items?: string;
  itemRows?: Array<Partial<Record<keyof ItemForm, string>>>;
};

const newItem = (): ItemForm => ({
  productId: '',
  productName: '',
  quantity: '',
  unit: 'kg',
  unitPrice: '',
  pricingBasis: 'uom_count',
});

const initialState: FormState = {
  customerId: '',
  customerName: '',
  deliveryDate: '',
  note: '',
  items: [newItem()],
};

const trim = (v: string) => v.trim();

const validate = (form: FormState): FieldErrors => {
  const errors: FieldErrors = { itemRows: [] };

  if (!form.customerId || Number(form.customerId) <= 0) errors.customerId = '顧客IDは必須です';
  if (!trim(form.customerName)) errors.customerName = '顧客名は必須です';
  if (!form.deliveryDate) errors.deliveryDate = '納品日は必須です';
  if (form.note.length > 1000) errors.note = '備考は1000文字以内で入力してください';
  if (form.items.length === 0) errors.items = '明細は最低1行必要です';

  form.items.forEach((item, idx) => {
    const rowError: Partial<Record<keyof ItemForm, string>> = {};
    if (!item.productId) rowError.productId = '商品選択は必須です';
    const q = Number(item.quantity);
    if (!item.quantity) rowError.quantity = '数量は必須です';
    else if (!Number.isFinite(q) || q <= 0) rowError.quantity = '数量は1以上で入力してください';

    const p = Number(item.unitPrice);
    if (!item.unitPrice) rowError.unitPrice = '単価は必須です';
    else if (!Number.isFinite(p) || p < 0) rowError.unitPrice = '単価は0以上で入力してください';

    if (!item.unit) rowError.unit = '単位は必須です';
    errors.itemRows![idx] = rowError;
  });

  return errors;
};

const hasAnyError = (errors: FieldErrors) => {
  if (errors.customerId || errors.customerName || errors.deliveryDate || errors.note || errors.items) return true;
  return (errors.itemRows ?? []).some((row) => Object.keys(row).length > 0);
};

export const OrderForm = ({ onSubmit, customers, products }: Props) => {
  const [form, setForm] = useState<FormState>(initialState);
  const [errors, setErrors] = useState<FieldErrors>({ itemRows: [] });
  const [submitError, setSubmitError] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const hasErrors = useMemo(() => hasAnyError(errors), [errors]);

  const handleHeaderChange = (key: Exclude<keyof FormState, 'items'>, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
    setSubmitError('');
  };

  const handleCustomerSelect = (value: string) => {
    const selected = customers.find((c) => String(c.id) === value);
    handleHeaderChange('customerId', value);
    if (selected) {
      const name = selected.label.split(':')[1]?.split('(')[0]?.trim() ?? '';
      handleHeaderChange('customerName', name);
    }
  };

  const handleItemChange = (index: number, key: keyof ItemForm, value: string) => {
    setForm((prev) => {
      const next = [...prev.items];
      next[index] = { ...next[index], [key]: value };
      return { ...prev, items: next };
    });
    setSubmitError('');
  };

  const handleProductSelect = (index: number, productId: string) => {
    const p = products.find((x) => String(x.id) === productId);
    handleItemChange(index, 'productId', productId);
    if (p) {
      handleItemChange(index, 'productName', p.name);
      handleItemChange(index, 'unit', p.orderUom);
      handleItemChange(index, 'pricingBasis', p.pricingBasisDefault);
    }
  };

  const addItemRow = () => setForm((prev) => ({ ...prev, items: [...prev.items, newItem()] }));

  const removeItemRow = (index: number) => {
    setForm((prev) => {
      if (prev.items.length <= 1) return prev;
      return { ...prev, items: prev.items.filter((_, i) => i !== index) };
    });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (hasAnyError(nextErrors)) return;

    setSubmitting(true);
    try {
      await onSubmit({
        customerId: Number(form.customerId),
        customerName: trim(form.customerName),
        deliveryDate: form.deliveryDate,
        note: form.note ? trim(form.note) : undefined,
        items: form.items.map((row) => ({
          productId: Number(row.productId),
          productName: trim(row.productName),
          quantity: Number(row.quantity),
          unit: trim(row.unit),
          unitPrice: Number(row.unitPrice),
          pricingBasis: row.pricingBasis,
        })),
      });
      setForm(initialState);
      setErrors({ itemRows: [] });
      setSubmitError('');
    } catch (e) {
      setSubmitError(toUserMessage(e, '注文作成に失敗しました。時間をおいて再試行してください。'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="card order-form">
      <div className="form-header">
        <h2>注文作成（ヘッダー + 明細）</h2>
        <p>ヘッダー保存後に明細を一括登録します。</p>
      </div>

      {submitError ? <p className="form-error">{submitError}</p> : null}

      <section className="form-section">
        <h3>注文ヘッダー</h3>
        <div className="form-grid two-col">
          <label>
            顧客選択 *
            <select value={form.customerId} onChange={(e) => handleCustomerSelect(e.target.value)}>
              <option value="">選択してください</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
            {errors.customerId ? <small className="field-error">{errors.customerId}</small> : null}
          </label>

          <label>
            顧客名 *
            <input value={form.customerName} onChange={(e) => handleHeaderChange('customerName', e.target.value)} />
            {errors.customerName ? <small className="field-error">{errors.customerName}</small> : null}
          </label>

          <label>
            納品日 *
            <input type="date" value={form.deliveryDate} onChange={(e) => handleHeaderChange('deliveryDate', e.target.value)} />
            {errors.deliveryDate ? <small className="field-error">{errors.deliveryDate}</small> : null}
          </label>
        </div>
      </section>

      <section className="form-section">
        <div className="section-row">
          <h3>明細行</h3>
          <button type="button" className="secondary" onClick={addItemRow}>+ 明細行を追加</button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th>商品 *</th><th>数量 *</th><th>単位 *</th><th>単価 *</th><th>課金基準</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {form.items.map((row, idx) => {
                const e = errors.itemRows?.[idx] ?? {};
                return (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>
                      <select value={row.productId} onChange={(ev) => handleProductSelect(idx, ev.target.value)}>
                        <option value="">選択</option>
                        {products.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                      </select>
                      {e.productId ? <small className="field-error">{e.productId}</small> : null}
                    </td>
                    <td>
                      <input type="number" min={1} value={row.quantity} onChange={(ev) => handleItemChange(idx, 'quantity', ev.target.value)} />
                      {e.quantity ? <small className="field-error">{e.quantity}</small> : null}
                    </td>
                    <td>
                      <input value={row.unit} onChange={(ev) => handleItemChange(idx, 'unit', ev.target.value)} />
                      {e.unit ? <small className="field-error">{e.unit}</small> : null}
                    </td>
                    <td>
                      <input type="number" min={0} step="0.01" value={row.unitPrice} onChange={(ev) => handleItemChange(idx, 'unitPrice', ev.target.value)} />
                      {e.unitPrice ? <small className="field-error">{e.unitPrice}</small> : null}
                    </td>
                    <td>
                      <select value={row.pricingBasis} onChange={(ev) => handleItemChange(idx, 'pricingBasis', ev.target.value as 'uom_count' | 'uom_kg')}>
                        <option value="uom_count">uom_count</option>
                        <option value="uom_kg">uom_kg</option>
                      </select>
                    </td>
                    <td>
                      <button type="button" className="danger" onClick={() => removeItemRow(idx)} disabled={form.items.length <= 1}>行削除</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="form-section">
        <h3>備考</h3>
        <label>備考
          <textarea value={form.note} onChange={(e) => handleHeaderChange('note', e.target.value)} rows={3} placeholder="任意入力" />
          {errors.note ? <small className="field-error">{errors.note}</small> : null}
        </label>
      </section>

      <div className="form-actions">
        <button type="submit" disabled={submitting || hasErrors}>{submitting ? '作成中...' : '注文を作成'}</button>
      </div>
    </form>
  );
};
