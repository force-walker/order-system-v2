import { useMemo, useState, type FormEvent } from 'react';
import type { CreateOrderRequest } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

type Props = {
  onSubmit: (payload: CreateOrderRequest) => Promise<void>;
};

type FormState = {
  orderNo: string;
  customerName: string;
  deliveryDate: string;
  note: string;
  productName: string;
  quantity: string;
  unit: string;
};

type FieldErrors = Partial<Record<keyof FormState, string>>;

const initialState: FormState = {
  orderNo: '',
  customerName: '',
  deliveryDate: '',
  note: '',
  productName: '',
  quantity: '',
  unit: 'kg',
};

const trim = (v: string) => v.trim();

const validate = (form: FormState): FieldErrors => {
  const errors: FieldErrors = {};

  if (!trim(form.orderNo)) errors.orderNo = '注文番号は必須です';
  if (trim(form.orderNo).length > 64) errors.orderNo = '注文番号は64文字以内で入力してください';

  if (!trim(form.customerName)) errors.customerName = '顧客名は必須です';
  if (trim(form.customerName).length > 255) errors.customerName = '顧客名は255文字以内で入力してください';

  if (!form.deliveryDate) {
    errors.deliveryDate = '納品日は必須です';
  }

  if (!trim(form.productName)) errors.productName = '商品名は必須です';

  const quantity = Number(form.quantity);
  if (!form.quantity) {
    errors.quantity = '数量は必須です';
  } else if (!Number.isFinite(quantity) || !Number.isInteger(quantity)) {
    errors.quantity = '数量は整数で入力してください';
  } else if (quantity <= 0) {
    errors.quantity = '数量は1以上で入力してください';
  }

  if (!trim(form.unit)) errors.unit = '単位は必須です';
  if (form.note.length > 1000) errors.note = '備考は1000文字以内で入力してください';

  return errors;
};

export const OrderForm = ({ onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(initialState);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const hasErrors = useMemo(() => Object.keys(errors).length > 0, [errors]);

  const handleChange = (key: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSubmitError('');
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();

    const nextErrors = validate(form);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await onSubmit({
        orderNo: trim(form.orderNo),
        customerName: trim(form.customerName),
        deliveryDate: form.deliveryDate,
        note: form.note ? trim(form.note) : undefined,
        items: [
          {
            productName: trim(form.productName),
            quantity: Number(form.quantity),
            unit: trim(form.unit),
          },
        ],
      });
      setForm(initialState);
      setErrors({});
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
        <h2>注文作成</h2>
        <p>必須項目を入力して注文を作成してください。</p>
      </div>

      {submitError ? <p className="form-error">{submitError}</p> : null}

      <section className="form-section">
        <h3>基本情報</h3>
        <div className="form-grid two-col">
          <label>
            注文番号 *
            <input
              value={form.orderNo}
              onChange={(e) => handleChange('orderNo', e.target.value)}
              placeholder="例: ORD-20260327-003"
            />
            {errors.orderNo ? <small className="field-error">{errors.orderNo}</small> : null}
          </label>

          <label>
            顧客名 *
            <input value={form.customerName} onChange={(e) => handleChange('customerName', e.target.value)} placeholder="例: サンプル商店" />
            {errors.customerName ? <small className="field-error">{errors.customerName}</small> : null}
          </label>

          <label>
            納品日 *
            <input type="date" value={form.deliveryDate} onChange={(e) => handleChange('deliveryDate', e.target.value)} />
            {errors.deliveryDate ? <small className="field-error">{errors.deliveryDate}</small> : null}
          </label>
        </div>
      </section>

      <section className="form-section">
        <h3>アイテム情報（先頭1件）</h3>
        <div className="form-grid three-col">
          <label>
            商品名 *
            <input value={form.productName} onChange={(e) => handleChange('productName', e.target.value)} placeholder="例: 鶏もも肉" />
            {errors.productName ? <small className="field-error">{errors.productName}</small> : null}
          </label>

          <label>
            数量 *
            <input type="number" min={1} step={1} value={form.quantity} onChange={(e) => handleChange('quantity', e.target.value)} />
            {errors.quantity ? <small className="field-error">{errors.quantity}</small> : null}
          </label>

          <label>
            単位 *
            <select value={form.unit} onChange={(e) => handleChange('unit', e.target.value)}>
              <option value="kg">kg</option>
              <option value="case">case</option>
              <option value="piece">piece</option>
            </select>
            {errors.unit ? <small className="field-error">{errors.unit}</small> : null}
          </label>
        </div>
      </section>

      <section className="form-section">
        <h3>備考</h3>
        <label>
          備考
          <textarea value={form.note} onChange={(e) => handleChange('note', e.target.value)} rows={3} placeholder="任意入力" />
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
