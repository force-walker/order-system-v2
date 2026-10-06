import { useEffect, useState, type FormEvent } from 'react';
import type { Supplier, SupplierCreateRequest } from 'features/suppliers/types/supplier';
import { toActionableMessage } from 'shared/error';
import { useFocusNavigation } from 'shared/useFocusNavigation';

type Props = {
  initialValue?: Supplier;
  submitLabel: string;
  onSubmit: (payload: SupplierCreateRequest) => Promise<void>;
};

type FormState = {
  name: string;
  active: boolean;
  paymentTermsType: string;
  paymentTermsDays: string;
};

const toInitialState = (initial?: Supplier): FormState => ({
  name: initial?.name ?? '',
  active: initial?.active ?? true,
  paymentTermsType: initial?.paymentTermsType ?? '',
  paymentTermsDays: initial?.paymentTermsDays == null ? '' : String(initial.paymentTermsDays),
});

export const SupplierForm = ({ initialValue, submitLabel, onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(toInitialState(initialValue));
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const { focusNavRef, onFocusNavKeyDownCapture } = useFocusNavigation();

  useEffect(() => {
    setForm(toInitialState(initialValue));
    setError('');
  }, [initialValue]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();

    if (!form.name.trim()) {
      setError('仕入先名は必須です');
      return;
    }

    setError('');
    setSubmitting(true);
    try {
      await onSubmit({ name: form.name.trim(), active: form.active,
        paymentTermsType: form.paymentTermsType ? form.paymentTermsType as any : null,
        paymentTermsDays: form.paymentTermsType === 'days_after_issue' ? Number(form.paymentTermsDays) : null });
    } catch (e) {
      setError(toActionableMessage(e, '仕入先の保存に失敗しました'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form ref={focusNavRef as any} onKeyDownCapture={onFocusNavKeyDownCapture} onSubmit={submit} className="card form-grid two-col">
      <h2>{submitLabel}</h2>
      {error ? <p className="form-error">{error}</p> : null}

      <label>
        仕入先コード
        <input value={initialValue?.supplierCode ?? 'SUP-自動採番'} readOnly />
        <small className="subtle">コードはシステム自動採番です</small>
      </label>

      <label>
        仕入先名 *
        <input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
      </label>

      <label>
        有効
        <select value={form.active ? 'true' : 'false'} onChange={(e) => setForm((p) => ({ ...p, active: e.target.value === 'true' }))}>
          <option value="true">有効</option>
          <option value="false">無効</option>
        </select>
      </label>
      <label>支払条件
        <select value={form.paymentTermsType} onChange={(e) => setForm((p) => ({ ...p, paymentTermsType: e.target.value }))}>
          <option value="">未設定</option><option value="days_after_issue">発行日から○日後</option>
          <option value="end_of_issue_month">当月末</option><option value="end_of_next_month">翌月末</option>
          <option value="end_of_second_month">翌々月末</option><option value="half_month_15_eom">15日締め・月末/翌15日払い</option>
        </select>
      </label>
      {form.paymentTermsType === 'days_after_issue' ? <label>支払サイト（日）
        <input type="number" min="0" inputMode="numeric" required value={form.paymentTermsDays}
          onChange={(e) => setForm((p) => ({ ...p, paymentTermsDays: e.target.value }))} />
      </label> : null}

      <div className="form-actions" style={{ gridColumn: '1 / -1' }}>
        <button type="submit" disabled={submitting}>{submitting ? '保存中...' : submitLabel}</button>
      </div>
    </form>
  );
};
