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
const UOM_OPTIONS = ['piece', 'kg', 'case'] as const;

const toInitial = (initial?: ProductDetail): FormState => {
  const pricingBasisDefault = initial?.pricingBasisDefault ?? 'uom_count';
  const usesKgPricing = pricingBasisDefault === 'uom_kg';
  return {
    name: initial?.name ?? '',
    orderUom: initial?.orderUom ?? 'piece',
    purchaseUom: usesKgPricing ? 'kg' : (initial?.purchaseUom ?? 'piece'),
    invoiceUom: usesKgPricing ? 'kg' : (initial?.invoiceUom ?? 'piece'),
    freightWeight: usesKgPricing ? 1 : initial?.freightWeight,
    pricingBasisDefault,
    isCatchWeight: usesKgPricing || (initial?.isCatchWeight ?? false),
    weightCaptureRequired: usesKgPricing || (initial?.weightCaptureRequired ?? false),
    active: initial?.active ?? true,
  };
};

export const ProductForm = ({ initialValue, submitLabel, onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(toInitial(initialValue));
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();
  const usesKgPricing = form.pricingBasisDefault === 'uom_kg';

  useEffect(() => {
    setForm(toInitial(initialValue));
    setError('');
  }, [initialValue]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return setError('商品名は必須です');
    if (form.freightWeight == null || form.freightWeight <= 0) return setError('Freight Weight (KG) は0より大きい数値が必須です');

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
        <select value={form.orderUom} onChange={(e) => setForm((p) => ({ ...p, orderUom: e.target.value }))}>
          {UOM_OPTIONS.map((uom) => <option key={uom} value={uom} disabled={uom === 'kg' && !usesKgPricing}>{uom}</option>)}
        </select>
      </label>
      <label>
        仕入単位
        <select
          value={form.purchaseUom}
          disabled={usesKgPricing}
          onChange={(e) => setForm((p) => ({ ...p, purchaseUom: e.target.value, invoiceUom: e.target.value }))}
        >
          {UOM_OPTIONS.map((uom) => <option key={uom} value={uom}>{uom}</option>)}
        </select>
      </label>
      <label>
        請求単位
        <select value={form.invoiceUom} disabled>
          {UOM_OPTIONS.map((uom) => <option key={uom} value={uom}>{uom}</option>)}
        </select>
      </label>
      <label>
        {`運賃重量（KG / ${form.invoiceUom}）`}
        <input
          type="number"
          inputMode="decimal"
          min="0.001"
          step="0.001"
          value={form.freightWeight ?? ''}
          disabled={usesKgPricing}
          onChange={(e) => setForm((p) => ({ ...p, freightWeight: e.target.value === '' ? undefined : Number(e.target.value) }))}
        />
        {usesKgPricing ? <small className="subtle">KG請求では1 KG固定です</small> : null}
      </label>
      <label>
        課金基準
        <select value={form.pricingBasisDefault} onChange={(e) => setForm((p) => {
          const pricingBasisDefault = e.target.value as 'uom_count' | 'uom_kg';
          return pricingBasisDefault === 'uom_kg'
            ? { ...p, pricingBasisDefault, purchaseUom: 'kg', invoiceUom: 'kg', freightWeight: 1, isCatchWeight: true, weightCaptureRequired: true }
            : { ...p, pricingBasisDefault, orderUom: p.orderUom === 'kg' ? 'piece' : p.orderUom, freightWeight: undefined };
        })}>
          <option value="uom_count">uom_count</option>
          <option value="uom_kg">uom_kg</option>
        </select>
      </label>
      <label>
        キャッチウェイト
        <select disabled={usesKgPricing} value={form.isCatchWeight ? 'true' : 'false'} onChange={(e) => setForm((p) => ({ ...p, isCatchWeight: e.target.value === 'true' }))}>
          <option value="false">いいえ</option>
          <option value="true">はい</option>
        </select>
      </label>
      <label>
        重量入力必須
        <select disabled={usesKgPricing} value={form.weightCaptureRequired ? 'true' : 'false'} onChange={(e) => setForm((p) => ({ ...p, weightCaptureRequired: e.target.value === 'true' }))}>
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
