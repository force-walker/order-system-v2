import { useState, type FormEvent } from 'react';
import type { CreateOrderRequest } from 'features/orders/types/order';

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

const initialState: FormState = {
  orderNo: '',
  customerName: '',
  deliveryDate: '',
  note: '',
  productName: '',
  quantity: '',
  unit: 'kg',
};

export const OrderForm = ({ onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (key: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();

    if (!form.orderNo || !form.customerName || !form.deliveryDate || !form.productName || !form.quantity || !form.unit) {
      setError('必須項目を入力してください');
      return;
    }

    if (Number(form.quantity) <= 0) {
      setError('数量は1以上を入力してください');
      return;
    }

    setError('');
    setSubmitting(true);
    try {
      await onSubmit({
        orderNo: form.orderNo,
        customerName: form.customerName,
        deliveryDate: form.deliveryDate,
        note: form.note || undefined,
        items: [
          {
            productName: form.productName,
            quantity: Number(form.quantity),
            unit: form.unit,
          },
        ],
      });
      setForm(initialState);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="card form-grid">
      <h2>注文作成</h2>
      {error ? <p className="form-error">{error}</p> : null}

      <label>
        注文番号 *
        <input value={form.orderNo} onChange={(e) => handleChange('orderNo', e.target.value)} />
      </label>

      <label>
        顧客名 *
        <input value={form.customerName} onChange={(e) => handleChange('customerName', e.target.value)} />
      </label>

      <label>
        納品日 *
        <input type="date" value={form.deliveryDate} onChange={(e) => handleChange('deliveryDate', e.target.value)} />
      </label>

      <label>
        商品名 *
        <input value={form.productName} onChange={(e) => handleChange('productName', e.target.value)} />
      </label>

      <label>
        数量 *
        <input type="number" min={1} value={form.quantity} onChange={(e) => handleChange('quantity', e.target.value)} />
      </label>

      <label>
        単位 *
        <select value={form.unit} onChange={(e) => handleChange('unit', e.target.value)}>
          <option value="kg">kg</option>
          <option value="case">case</option>
          <option value="piece">piece</option>
        </select>
      </label>

      <label>
        備考
        <textarea value={form.note} onChange={(e) => handleChange('note', e.target.value)} rows={3} />
      </label>

      <button type="submit" disabled={submitting}>
        {submitting ? '作成中...' : '注文を作成'}
      </button>
    </form>
  );
};
