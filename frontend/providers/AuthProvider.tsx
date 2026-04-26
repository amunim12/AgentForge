"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { api, extractErrorMessage } from "@/lib/api";
import { clearTokens, getAccessToken, setTokens } from "@/lib/auth";
import type { AuthTokens, User } from "@/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get<User>("/api/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    fetchMe().finally(() => setLoading(false));
  }, [fetchMe]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      try {
        const { data } = await api.post<AuthTokens>("/api/auth/login", {
          identifier,
          password,
        });
        setTokens(data.access_token, data.refresh_token);
        await fetchMe();
        router.push("/dashboard");
      } catch (err) {
        throw new Error(extractErrorMessage(err, "Login failed"));
      }
    },
    [fetchMe, router],
  );

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      try {
        await api.post<User>("/api/auth/register", { email, username, password });
        await login(email, password);
      } catch (err) {
        throw new Error(extractErrorMessage(err, "Registration failed"));
      }
    },
    [login],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, refresh: fetchMe }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
