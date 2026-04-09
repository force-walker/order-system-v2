import { useEffect, useMemo, useState, type FormEvent } from 'react';
import type { CreateOrderRequest, CustomerOption, ProductOption } from 'features/orders/types/order';
import { toActionableMessage } from 'shared/error';

type Props = {
  onSubmit: (payload: CreateOrderRequest) => Promise<void>;
  customers: CustomerOption[];
  products: ProductOption[];
  initialValue?: CreateOrderRequest;
  submitLabel?: string;
  onDiscard?: () => void;
};

type ItemForm = {
  clientKey: string;
  id?: number;
  productId: string;
  productName: string;
  quantity: string;
  unit: string;
  unitPrice: string;
  pricingBasis: 'uom_count' | 'uom_kg';
  estimatedWeightKg: string;
  targetPrice: string;
  priceCeiling: string;
  stockoutPolicy: 'backorder' | 'substitute' | 'cancel' | 'split';
  comment: string;
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

let rowSeq = 0;
const nextRowKey = () => `row-${Date.now()}-${rowSeq++}`;

const getTomorrowDate = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
};

const newItem = (): ItemForm => ({
  clientKey: nextRowKey(),
  productId: '',
  productName: '',
  quantity: '',
  unit: 'kg',
  unitPrice: '',
  pricingBasis: 'uom_count',
  estimatedWeightKg: '',
  targetPrice: '',
  priceCeiling: '',
  stockoutPolicy: 'cancel',
  comment: '',
});

const trim = (v: string) => v.trim();

const toInitialForm = (initialValue?: CreateOrderRequest): FormState => {
  if (!initialValue) {
    return {
      customerId: '',
      customerName: '',
      deliveryDate: getTomorrowDate(),
      note: '',
      items: [newItem()],
    };
  }

  return {
    customerId: String(initialValue.customerId),
    customerName: initialValue.customerName,
    deliveryDate: initialValue.deliveryDate,
    note: initialValue.note ?? '',
    items:
      initialValue.items.length > 0
        ? initialValue.items.map((i) => ({
            clientKey: i.id ? `existing-${i.id}` : nextRowKey(),
            id: i.id,
            productId: i.productId ? String(i.productId) : '',
            productName: i.productName,
            quantity: String(i.quantity),
            unit: i.unit,
            unitPrice: String(i.unitPrice),
            pricingBasis: i.pricingBasis,
            estimatedWeightKg: i.estimatedWeightKg !== undefined ? String(i.estimatedWeightKg) : '',
            targetPrice: i.targetPrice !== undefined ? String(i.targetPrice) : '',
            priceCeiling: i.priceCeiling !== undefined ? String(i.priceCeiling) : '',
            stockoutPolicy: i.stockoutPolicy ?? 'cancel',
            comment: i.comment ?? '',
          }))
        : [newItem()],
  };
};

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

    const p = Number(item.unitPrice || '0');
    if (item.unitPrice && (!Number.isFinite(p) || p < 0)) rowError.unitPrice = '単価は0以上で入力してください';

    if (!item.unit) rowError.unit = '単位は必須です';

    if (item.estimatedWeightKg) {
      const ew = Number(item.estimatedWeightKg);
      if (!Number.isFinite(ew) || ew <= 0) rowError.estimatedWeightKg = '推定重量は0より大きい値で入力してください';
    }

    if (item.targetPrice) {
      const tp = Number(item.targetPrice);
      if (!Number.isFinite(tp) || tp < 0) rowError.targetPrice = '目標単価は0以上で入力してください';
    }

    if (item.priceCeiling) {
      const pc = Number(item.priceCeiling);
      if (!Number.isFinite(pc) || pc < 0) rowError.priceCeiling = '価格上限は0以上で入力してください';
    }

    if (item.targetPrice && item.priceCeiling && Number(item.targetPrice) > Number(item.priceCeiling)) {
      rowError.priceCeiling = '価格上限は目標単価以上で入力してください';
    }

    errors.itemRows![idx] = rowError;
  });

  return errors;
};

const hasAnyError = (errors: FieldErrors) => {
  if (errors.customerId || errors.customerName || errors.deliveryDate || errors.note || errors.items) return true;
  return (errors.itemRows ?? []).some((row) => row != null && Object.keys(row).length > 0);
};

export const OrderForm = ({ onSubmit, customers, products, initialValue, submitLabel = '注文を作成', onDiscard }: Props) => {
  const [form, setForm] = useState<FormState>(toInitialForm(initialValue));
  const [errors, setErrors] = useState<FieldErrors>({ itemRows: [] });
  const [submitError, setSubmitError] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [openDetailByRowKey, setOpenDetailByRowKey] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setForm(toInitialForm(initialValue));
    setErrors({ itemRows: [] });
    setSubmitError('');
    setOpenDetailByRowKey({});
  }, [initialValue]);

  const hasErrors = useMemo(() => hasAnyError(errors), [errors]);

  const clearHeaderError = (key: keyof Omit<FormState, 'items'>) => {
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const clearItemError = (index: number, key: keyof ItemForm) => {
    setErrors((prev) => {
      const itemRows = [...(prev.itemRows ?? [])];
      const row = { ...(itemRows[index] ?? {}) };
      delete row[key];
      itemRows[index] = row;
      return { ...prev, itemRows, items: undefined };
    });
  };

  const handleHeaderChange = (key: Exclude<keyof FormState, 'items'>, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    clearHeaderError(key);
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
    clearItemError(index, key);
    setSubmitError('');
  };

  const handleProductSelect = (index: number, productId: string) => {
    const p = products.find((x) => String(x.id) === productId);
    handleItemChange(index, 'productId', productId);
    if (p) {
      const safeUnit = p.orderUom || 'kg';
      const safePricing = p.pricingBasisDefault === 'uom_kg' ? 'uom_kg' : 'uom_count';
      handleItemChange(index, 'productName', p.name || '');
      handleItemChange(index, 'unit', safeUnit);
      handleItemChange(index, 'pricingBasis', safePricing);
    }
  };

  const addItemRow = () => setForm((prev) => ({ ...prev, items: [...prev.items, newItem()] }));

  const removeItemRow = (index: number) => {
    setForm((prev) => {
      if (prev.items.length <= 1) return prev;
      return { ...prev, items: prev.items.filter((_, i) => i !== index) };
    });
    setErrors((prev) => ({ ...prev, itemRows: (prev.itemRows ?? []).filter((_, i) => i !== index) }));
  };

  const handleDiscard = () => {
    if (onDiscard) {
      onDiscard();
      return;
    }
    setForm(toInitialForm(initialValue));
    setErrors({ itemRows: [] });
    setSubmitError('');
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
          id: row.id,
          productId: Number(row.productId),
          productName: trim(row.productName),
          quantity: Number(row.quantity),
          unit: trim(row.unit),
          unitPrice: Number(row.unitPrice),
          pricingBasis: row.pricingBasis,
          estimatedWeightKg: row.estimatedWeightKg ? Number(row.estimatedWeightKg) : undefined,
          targetPrice: row.targetPrice ? Number(row.targetPrice) : undefined,
          priceCeiling: row.priceCeiling ? Number(row.priceCeiling) : undefined,
          stockoutPolicy: row.stockoutPolicy,
          comment: row.comment ? trim(row.comment) : undefined,
        })),
      });
      setSubmitError('');
    } catch (err) {
      setSubmitError(toActionableMessage(err, '注文保存に失敗しました。時間をおいて再試行してください。'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="card order-form">
      <div className="form-header">
        <h2>注文作成 / 編集（ヘッダー + 明細）</h2>
        <p>ヘッダー情報と明細行を同一画面で管理します。</p>
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

        <div className="item-cards">
          <div className="item-grid-row item-grid-row-primary item-row-header">
            <div>#</div>
            <div>商品</div>
            <div>数量</div>
            <div>単位</div>
            <div>コメント</div>
            <div>操作</div>
          </div>
          {form.items.map((row, idx) => {
            const e = errors.itemRows?.[idx] ?? {};
            return (
              <div key={row.clientKey} className="item-card item-card-flat">
                <div className="item-grid-row item-grid-row-primary item-row-flat">
                  <div className="item-index">{idx + 1}</div>
                  <label>
                    <select value={row.productId} onChange={(ev) => handleProductSelect(idx, ev.target.value)}>
                      <option value="">選択</option>
                      {products.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                    </select>
                    {e.productId ? <small className="field-error">{e.productId}</small> : null}
                  </label>

                  <label>
                    <input type="number" min={1} value={row.quantity} onChange={(ev) => handleItemChange(idx, 'quantity', ev.target.value)} />
                    {e.quantity ? <small className="field-error">{e.quantity}</small> : null}
                  </label>

                  <label>
                    <input value={row.unit} onChange={(ev) => handleItemChange(idx, 'unit', ev.target.value)} />
                    {e.unit ? <small className="field-error">{e.unit}</small> : null}
                  </label>

                  <label>
                    <input value={row.comment} onChange={(ev) => handleItemChange(idx, 'comment', ev.target.value)} placeholder="代替指示など" />
                  </label>

                  <div className="item-delete-cell item-action-cell">
                    <button
                      type="button"
                      className="secondary item-detail-toggle"
                      onClick={() => setOpenDetailByRowKey((prev) => ({ ...prev, [row.clientKey]: !prev[row.clientKey] }))}
                    >
                      詳細
                    </button>
                    <button type="button" className="danger" onClick={() => removeItemRow(idx)} disabled={form.items.length <= 1}>削除</button>
                  </div>
                </div>

                {openDetailByRowKey[row.clientKey] ? (
                  <div className="item-advanced">
                    <div className="item-grid-row item-grid-row-secondary">
                      <label>
                        推定重量kg
                        <input type="number" min={0} step="0.001" value={row.estimatedWeightKg} onChange={(ev) => handleItemChange(idx, 'estimatedWeightKg', ev.target.value)} />
                        {e.estimatedWeightKg ? <small className="field-error">{e.estimatedWeightKg}</small> : null}
                      </label>

                      <label>
                        目標単価
                        <input type="number" min={0} step="0.01" value={row.targetPrice} onChange={(ev) => handleItemChange(idx, 'targetPrice', ev.target.value)} />
                        {e.targetPrice ? <small className="field-error">{e.targetPrice}</small> : null}
                      </label>

                      <label>
                        価格上限
                        <input type="number" min={0} step="0.01" value={row.priceCeiling} onChange={(ev) => handleItemChange(idx, 'priceCeiling', ev.target.value)} />
                        {e.priceCeiling ? <small className="field-error">{e.priceCeiling}</small> : null}
                      </label>

                      <label>
                        代替指示
                        <select value={row.stockoutPolicy} onChange={(ev) => handleItemChange(idx, 'stockoutPolicy', ev.target.value as 'backorder' | 'substitute' | 'cancel' | 'split')}>
                          <option value="substitute">substitute</option>
                          <option value="backorder">backorder</option>
                          <option value="cancel">cancel</option>
                          <option value="split">split</option>
                        </select>
                      </label>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
        {errors.items ? <p className="form-error">{errors.items}</p> : null}
      </section>

      <section className="form-section">
        <h3>備考</h3>
        <label>備考
          <textarea value={form.note} onChange={(e) => handleHeaderChange('note', e.target.value)} rows={3} placeholder="任意入力" />
          {errors.note ? <small className="field-error">{errors.note}</small> : null}
        </label>
      </section>

      <div className="form-actions">
        <button type="button" className="secondary" onClick={handleDiscard}>変更を破棄</button>
        <button type="submit" disabled={submitting}>{submitting ? '保存中...' : submitLabel}</button>
      </div>
      {hasErrors ? <small className="subtle">入力エラーがあります。赤字項目を修正してください。</small> : null}
    </form>
  );
};
