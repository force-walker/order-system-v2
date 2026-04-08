import { useEffect, useState, type FormEvent } from 'react';
import type { Supplier, SupplierCreateRequest } from 'features/suppliers/types/supplier';
import { toUserMessage } from 'shared/error';

type Props = {
  initialValue?: Supplier;
  submitLabel: string;
  onSubmit: (payload: SupplierCreateRequest) => Promise<void>;
};

type FormState = {
  name: string;
  active: boolean;
};

const toInitialState = (initial?: Supplier): FormState => ({
  name: initial?.name ?? '',
  active: initial?.active ?? true,
});

export const SupplierForm = ({ initialValue, submitLabel, onSubmit }: Props) => {
  const [form, setForm] = useState<FormState>(toInitialState(initialValue));
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

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
      await onSubmit({ name: form.name.trim(), active: form.active });
    } catch (e) {
      setError(toUserMessage(e, '仕入先の保存に失敗しました'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="card form-grid two-col">
      <h2>{submitLabel}</h2>
      {error ? <p className="form-error">{error}</p> : null}

      <label>
        仕入先コード
        <input value={initialValue?.supplierCode ?? '作成後に自動採番'} readOnly />
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

      <div className="form-actions" style={{ gridColumn: '1 / -1' }}>
        <button type="submit" disabled={submitting}>{submitting ? '保存中...' : submitLabel}</button>
      </div>
    </form>
  );
};
