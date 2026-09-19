import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { registerUser, signIn } from 'shared/authSession';
import { toUserMessage } from 'shared/error';
import { useAuth } from './AuthContext';

export const AuthPage = ({ register = false }: { register?: boolean }) => {
  const { user, loading } = useAuth();
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  if (loading) return <p role="status">認証状態を確認しています…</p>;
  if (user) return <Navigate to="/orders/new" replace />;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (register && password !== confirmation) { setError('パスワードが一致しません。'); return; }
    setBusy(true);
    try {
      if (register) {
        await registerUser(userId, password);
        setPassword('');
        setConfirmation('');
        navigate('/login', { replace: true, state: { message: '登録しました。ユーザーIDとパスワードでログインしてください。' } });
      } else {
        await signIn(userId, password);
      }
    } catch (e) {
      setError(toUserMessage(e, '処理に失敗しました。接続を確認して再試行してください。'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="page" style={{ maxWidth: 480 }}>
      <h1>Order System v2</h1>
      <section className="card">
        <h2>{register ? '新規登録' : 'ログイン'}</h2>
        {location.state?.message && <p role="status">{String(location.state.message)}</p>}
        {error && <p role="alert">{error}</p>}
        <form onSubmit={submit}>
          <label htmlFor="auth-user-id">ユーザーID</label>
          <input id="auth-user-id" value={userId} onChange={(e) => setUserId(e.target.value)} required minLength={3} maxLength={128} pattern="[a-zA-Z0-9_.@+\-]+" autoComplete="username" />
          <p className="subtle">半角英数字と _ . @ + -、3〜128文字。大文字・小文字は区別しません。</p>
          <label htmlFor="auth-password">パスワード</label>
          <input id="auth-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={register ? 12 : 1} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'} />
          {register && <>
            <p className="subtle">12〜128文字で設定してください。</p>
            <label htmlFor="auth-confirm">パスワード（確認）</label>
            <input id="auth-confirm" type="password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} required autoComplete="new-password" />
          </>}
          <button type="submit" disabled={busy}>{busy ? '処理中…' : register ? '登録する' : 'ログイン'}</button>
        </form>
        <p><Link to={register ? '/login' : '/register'}>{register ? 'ログインへ戻る' : '初めての方：新規登録'}</Link></p>
      </section>
    </main>
  );
};
