import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { AUTH_CHANGED, AUTH_STORAGE_KEY, clearSession, currentUser, readSession, type AuthUser } from 'shared/authSession';
import { ServiceError } from 'shared/error';
import { invalidateOrderCaches } from 'features/orders/services/ordersService';

type AuthState = { user: AuthUser | null; loading: boolean };
const AuthContext = createContext<AuthState>({ user: null, loading: true });
export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });
  useEffect(() => {
    let generation = 0;
    const validate = async () => {
      const version = ++generation;
      const token = readSession()?.access_token;
      invalidateOrderCaches();
      setState({ user: null, loading: Boolean(token) });
      if (!token) return;
      try {
        const user = await currentUser(token);
        if (generation === version && readSession()?.access_token === token) setState({ user, loading: false });
      } catch (error) {
        if (generation !== version) return;
        if (error instanceof ServiceError && (error.status === 401 || error.status === 403)) clearSession();
        setState({ user: null, loading: false });
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === AUTH_STORAGE_KEY || event.key === null) void validate();
    };
    const onRestore = (event: PageTransitionEvent) => { if (event.persisted) void validate(); };
    void validate();
    window.addEventListener(AUTH_CHANGED, validate);
    window.addEventListener('storage', onStorage);
    window.addEventListener('pageshow', onRestore);
    return () => {
      generation++;
      window.removeEventListener(AUTH_CHANGED, validate);
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('pageshow', onRestore);
    };
  }, []);
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
};

export const ProtectedRoute = () => {
  const { user, loading } = useAuth();
  if (loading) return <p role="status">認証状態を確認しています…</p>;
  return user && readSession() ? <Outlet /> : <Navigate to="/login" replace />;
};
