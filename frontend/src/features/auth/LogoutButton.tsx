import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { signOut } from 'shared/authSession';

export const LogoutButton = () => {
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const logout = async () => {
    setBusy(true);
    let message = 'ログアウトしました。';
    try { await signOut(); } catch {
      message = 'この端末の認証情報は削除しましたが、通信エラーでサーバー側の失効を確認できませんでした。管理者へ連絡してください。';
    }
    navigate('/login', { replace: true, state: { message } });
  };
  return <button type="button" className="secondary" onClick={logout} disabled={busy}>{busy ? 'ログアウト中…' : 'ログアウト'}</button>;
};
