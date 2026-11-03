import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, refreshSession, setAccessToken, setSessionLostHandler } from "../api/client";
import type { User } from "../api/types";

interface AuthValue {
  user: User | null;
  loading: boolean; // true while we check for an existing session on page load
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, fullName: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}
const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
    // Silent sign-in: if the HttpOnly refresh cookie is valid we get a fresh access token.
    refreshSession().then((d) => setUser(d?.user ?? null)).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const d = await api.login({ email, password });
    setAccessToken(d.access_token);
    setUser(d.user);
    return d.user;
  }, []);
  const register = useCallback(async (email: string, password: string, full_name: string) => {
    const d = await api.register({ email, password, full_name });
    setAccessToken(d.access_token);
    setUser(d.user);
    return d.user;
  }, []);
  const logout = useCallback(async () => { await api.logout(); setUser(null); }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout, setUser }),
    [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
