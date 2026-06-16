import { useEffect, useState, type FormEvent } from 'react';
import type { ProductCreateRequest, ProductDetail } from 'features/products/types/product';
import { toActionableMessage } from 'shared/error';
import { useFocusNavigation } from 'shared/useFocusNavigation';

type Props = {
  initialValue?: ProductDetail;
  submitLabel: string;
  onSubmit: (payload: ProductCreateRequest) => Promise<void>;
};

type FormState = ProductCreateRequest & { active: boolean };

const toInitial = (initial?: ProductDetail): FormState => ({
  name: initial?.name ?? '',
  orderUom: initial?.orderUom ?? 'kg',
  purchaseUom: initial?.purchaseUom ?? 'kg',
  invoiceUom: initial?.invoiceUom ?? 'kg',
  freightWeight: initial?.freightWeight ?? 0,
  pricingBasisDefault: initial?.pricingBasisDefault ?? 'uom_count',
  isCatchWeight: initial?.isCatchWeight ?? false,
  weightCaptureRequired: initial?.weightCaptureRequired ?? false,
  active: initial?.active ?? true,
});

export const ProductForm = ({ initialValue, submitLabel, onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(toInitial(initialValue));
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();

  useEffect(() => {
    setForm(toInitial(initialValue));
    setError('');
  }, [initialValue]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return setError('商品名は必須です');

    setError('');
    setSubmitting(true);
    try {
      await onSubmit({
        name: form.name.trim(),
        orderUom: form.orderUom.trim(),
        purchaseUom: form.purchaseUom.trim(),
        invoiceUom: form.invoiceUom.trim(),
        freightWeight: form.freightWeight,
        pricingBasisDefault: form.pricingBasisDefault,
        isCatchWeight: form.isCatchWeight,
        weightCaptureRequired: form.weightCaptureRequired,
      });
    } catch (e) {
      setError(toActionableMessage(e, '商品の保存に失敗しました'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form ref={focusNavRef as any} onKeyDownCapture={onFocusNavKeyDownCapture} onSubmit={submit} className="card form-grid two-col">
      <h2>{submitLabel}</h2>
      {error ? <p className="form-error">{error}</p> : null}

      <label>
        SKU
        <input value={initialValue?.sku ?? 'PRD-自動採番'} readOnly />
        <small className="subtle">コードはシステム自動採番です</small>
      </label>
      <label>
        商品名 *
        <input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
      </label>
      <label>
        注文単位
        <input value={form.orderUom} onChange={(e) => setForm((p) => ({ ...p, orderUom: e.target.value }))} />
      </label>
      <label>
        仕入単位
        <input value={form.purchaseUom} onChange={(e) => setForm((p) => ({ ...p, purchaseUom: e.target.value }))} />
      </label>
      <label>
        請求単位
        <input value={form.invoiceUom} onChange={(e) => setForm((p) => ({ ...p, invoiceUom: e.target.value }))} />
      </label>
      <label>
        運賃重量
        <input
          type="number"
          inputMode="decimal"
          min="0"
          step="0.001"
          value={form.freightWeight}
          onChange={(e) => setForm((p) => ({ ...p, freightWeight: Number(e.target.value) }))}
        />
      </label>
      <label>
        課金基準
        <select value={form.pricingBasisDefault} onChange={(e) => setForm((p) => ({ ...p, pricingBasisDefault: e.target.value as 'uom_count' | 'uom_kg' }))}>
          <option value="uom_count">uom_count</option>
          <option value="uom_kg">uom_kg</option>
        </select>
      </label>
      <label>
        キャッチウェイト
        <select value={form.isCatchWeight ? 'true' : 'false'} onChange={(e) => setForm((p) => ({ ...p, isCatchWeight: e.target.value === 'true' }))}>
          <option value="false">いいえ</option>
          <option value="true">はい</option>
        </select>
      </label>
      <label>
        重量入力必須
        <select value={form.weightCaptureRequired ? 'true' : 'false'} onChange={(e) => setForm((p) => ({ ...p, weightCaptureRequired: e.target.value === 'true' }))}>
          <option value="false">いいえ</option>
          <option value="true">はい</option>
        </select>
      </label>

      <div className="form-actions" style={{ gridColumn: '1 / -1' }}>
        <button type="submit" disabled={submitting}>{submitting ? '保存中...' : submitLabel}</button>
      </div>
    </form>
  );
};
