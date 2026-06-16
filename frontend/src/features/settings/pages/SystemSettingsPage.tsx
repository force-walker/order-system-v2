import type { FormEvent } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { getSystemSettings, updateSystemSettings } from 'features/settings/services/systemSettingsService';
import type { SystemSettings, UpdateSystemSettingsRequest } from 'features/settings/types/systemSettings';
import { ServiceError, toActionableMessage } from 'shared/error';

type FormState = UpdateSystemSettingsRequest;
type ToastState = { type: 'success' | 'error'; message: string } | null;

const emptyForm: FormState = {
  exchangeRate: '',
  jpGrossMarginPct: '',
  hkGrossMarginPct: '',
  freightUnitPrice: '',
};

const toFormState = (settings: SystemSettings): FormState => ({
  exchangeRate: settings.exchangeRate,
  jpGrossMarginPct: settings.jpGrossMarginPct,
  hkGrossMarginPct: settings.hkGrossMarginPct,
  freightUnitPrice: settings.freightUnitPrice,
});

const formatUpdatedAt = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export const SystemSettingsPage = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [initialForm, setInitialForm] = useState<FormState>(emptyForm);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(initialForm), [form, initialForm]);

  useEffect(() => {
    const timer = !toast
      ? undefined
      : window.setTimeout(() => {
          setToast(null);
        }, 4000);

    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [toast]);

  useEffect(() => {
    if (!dirty) return undefined;

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };

    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  const load = async () => {
    setLoading(true);
    setError('');
    setMissing(false);
    try {
      const data = await getSystemSettings();
      const nextForm = toFormState(data);
      setSettings(data);
      setForm(nextForm);
      setInitialForm(nextForm);
    } catch (e) {
      if (e instanceof ServiceError && e.status === 404) {
        setMissing(true);
      } else {
        setError(toActionableMessage(e, '環境設定の取得に失敗しました。'));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const setField = (key: keyof FormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!dirty) return;

    setSaving(true);
    setToast(null);
    try {
      const updated = await updateSystemSettings(form);
      const nextForm = toFormState(updated);
      setSettings(updated);
      setForm(nextForm);
      setInitialForm(nextForm);
      setToast({ type: 'success', message: '環境設定を保存しました。' });
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '環境設定の保存に失敗しました。') });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState title="環境設定を読み込み中" description="しばらくお待ちください。" />;
  if (error) return <ErrorState title="環境設定の取得に失敗しました" description={error} actionLabel="再試行" onAction={() => void load()} />;
  if (missing) return <EmptyState title="環境設定がありません" description="環境設定の初期データが見つかりません。backend の初期投入状態を確認してください。" actionLabel="再試行" onAction={() => void load()} />;

  return (
    <section>
      <div className="card settings-card">
        <div className="list-header">
          <div>
            <h2>環境設定</h2>
            <p className="subtle">見積・請求関連で共通参照する基準値を更新します。</p>
          </div>
          <div className="settings-status">
            {dirty ? <span className="unsaved-badge">未保存変更あり</span> : <span className="saved-badge">保存済み</span>}
            <span className="subtle">最終更新: {settings ? formatUpdatedAt(settings.updatedAt) : '-'}</span>
          </div>
        </div>

        {toast ? <div className={`toast ${toast.type}`} role="status" aria-live="polite">{toast.message}</div> : null}

        <form className="form-grid settings-form" onSubmit={handleSubmit}>
          <label>
            為替レート（JPY→HKD）
            <input
              type="number"
              inputMode="decimal"
              step="0.0001"
              min="0"
              value={form.exchangeRate}
              onChange={(e) => setField('exchangeRate', e.target.value)}
              disabled={saving}
            />
          </label>

          <label>
            日本粗利（%）
            <input
              type="number"
              inputMode="decimal"
              step="0.001"
              min="0"
              value={form.jpGrossMarginPct}
              onChange={(e) => setField('jpGrossMarginPct', e.target.value)}
              disabled={saving}
            />
          </label>

          <label>
            香港基準粗利（%）
            <input
              type="number"
              inputMode="decimal"
              step="0.001"
              min="0"
              value={form.hkGrossMarginPct}
              onChange={(e) => setField('hkGrossMarginPct', e.target.value)}
              disabled={saving}
            />
          </label>

          <label>
            運賃単価
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={form.freightUnitPrice}
              onChange={(e) => setField('freightUnitPrice', e.target.value)}
              disabled={saving}
            />
          </label>

          <div className="settings-notes">
            <p className="subtle">確認事項: 粗利・運賃単価の参照画面と自動計算反映範囲は業務ルール確定後に別途連携してください。</p>
          </div>

          <div className="form-actions">
            <button type="submit" disabled={!dirty || saving}>{saving ? '保存中...' : '保存'}</button>
          </div>
        </form>
      </div>
    </section>
  );
};
