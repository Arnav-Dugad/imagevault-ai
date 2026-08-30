import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "../lib/api";
import type { TokenResponse, User } from "../types";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const clear = () => setUser(null);
    window.addEventListener("imagevault:unauthorized", clear);
    return () => window.removeEventListener("imagevault:unauthorized", clear);
  }, []);

  async function authenticate(path: string, body: object) {
    const response = await api<TokenResponse>(path, { method: "POST", body: JSON.stringify(body) });
    setToken(response.access_token);
    setUser(response.user);
  }

  const value: AuthValue = {
    user,
    loading,
    login: (email, password) => authenticate("/auth/login", { email, password }),
    register: (email, display_name, password) => authenticate("/auth/register", { email, display_name, password }),
    logout: () => { setToken(null); setUser(null); },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
