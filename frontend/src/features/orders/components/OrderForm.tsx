import { useMemo, useState, type FormEvent } from 'react';
import type { CreateOrderRequest, CustomerOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

type Props = {
  onSubmit: (payload: CreateOrderRequest) => Promise<void>;
  customers: CustomerOption[];
};

type ItemForm = {
  productName: string;
  quantity: string;
  unit: string;
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
  productName: '',
  quantity: '',
  unit: 'kg',
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
  if (trim(form.customerName).length > 255) errors.customerName = '顧客名は255文字以内で入力してください';
  if (!form.deliveryDate) errors.deliveryDate = '納品日は必須です';
  if (form.note.length > 1000) errors.note = '備考は1000文字以内で入力してください';

  if (form.items.length === 0) {
    errors.items = '明細は最低1行必要です';
  }

  form.items.forEach((item, idx) => {
    const rowError: Partial<Record<keyof ItemForm, string>> = {};
    if (!trim(item.productName)) rowError.productName = '商品名は必須です';

    const quantity = Number(item.quantity);
    if (!item.quantity) {
      rowError.quantity = '数量は必須です';
    } else if (!Number.isFinite(quantity) || !Number.isInteger(quantity)) {
      rowError.quantity = '数量は整数で入力してください';
    } else if (quantity <= 0) {
      rowError.quantity = '数量は1以上で入力してください';
    }

    if (!trim(item.unit)) rowError.unit = '単位は必須です';

    errors.itemRows![idx] = rowError;
  });

  return errors;
};

const hasAnyError = (errors: FieldErrors) => {
  if (errors.customerId || errors.customerName || errors.deliveryDate || errors.note || errors.items) return true;
  return (errors.itemRows ?? []).some((row) => Object.keys(row).length > 0);
};

export const OrderForm = ({ onSubmit, customers }: Props) => {
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

    setErrors((prev) => {
      const nextRows = [...(prev.itemRows ?? [])];
      const row = { ...(nextRows[index] ?? {}) };
      delete row[key];
      nextRows[index] = row;
      return { ...prev, items: undefined, itemRows: nextRows };
    });
    setSubmitError('');
  };

  const addItemRow = () => {
    setForm((prev) => ({ ...prev, items: [...prev.items, newItem()] }));
    setErrors((prev) => ({ ...prev, items: undefined, itemRows: [...(prev.itemRows ?? []), {}] }));
  };

  const removeItemRow = (index: number) => {
    setForm((prev) => {
      if (prev.items.length <= 1) return prev;
      const next = prev.items.filter((_, i) => i !== index);
      return { ...prev, items: next };
    });
    setErrors((prev) => {
      const nextRows = (prev.itemRows ?? []).filter((_, i) => i !== index);
      return { ...prev, itemRows: nextRows };
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
          productName: trim(row.productName),
          quantity: Number(row.quantity),
          unit: trim(row.unit),
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
        <p>上段で注文ヘッダーを入力し、下段で明細行を追加してください。</p>
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
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            {errors.customerId ? <small className="field-error">{errors.customerId}</small> : null}
          </label>

          <label>
            顧客名 *
            <input value={form.customerName} onChange={(e) => handleHeaderChange('customerName', e.target.value)} placeholder="顧客選択で自動入力" />
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
          <button type="button" className="secondary" onClick={addItemRow}>
            + 明細行を追加
          </button>
        </div>
        {errors.items ? <p className="form-error">{errors.items}</p> : null}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>商品名 *</th>
                <th>数量 *</th>
                <th>単位 *</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {form.items.map((row, idx) => {
                const rowError = errors.itemRows?.[idx] ?? {};
                return (
                  <tr key={`item-row-${idx}`}>
                    <td>{idx + 1}</td>
                    <td>
                      <input
                        value={row.productName}
                        onChange={(e) => handleItemChange(idx, 'productName', e.target.value)}
                        placeholder="例: 鶏もも肉"
                      />
                      {rowError.productName ? <small className="field-error">{rowError.productName}</small> : null}
                    </td>
                    <td>
                      <input type="number" min={1} step={1} value={row.quantity} onChange={(e) => handleItemChange(idx, 'quantity', e.target.value)} />
                      {rowError.quantity ? <small className="field-error">{rowError.quantity}</small> : null}
                    </td>
                    <td>
                      <select value={row.unit} onChange={(e) => handleItemChange(idx, 'unit', e.target.value)}>
                        <option value="kg">kg</option>
                        <option value="case">case</option>
                        <option value="piece">piece</option>
                      </select>
                      {rowError.unit ? <small className="field-error">{rowError.unit}</small> : null}
                    </td>
                    <td>
                      <button type="button" className="danger" onClick={() => removeItemRow(idx)} disabled={form.items.length <= 1}>
                        行削除
                      </button>
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
        <label>
          備考
          <textarea value={form.note} onChange={(e) => handleHeaderChange('note', e.target.value)} rows={3} placeholder="任意入力" />
          {errors.note ? <small className="field-error">{errors.note}</small> : null}
        </label>
      </section>

      <div className="form-actions">
        <button type="submit" disabled={submitting || hasErrors}>
          {submitting ? '作成中...' : '注文を作成'}
        </button>
      </div>
    </form>
  );
};
