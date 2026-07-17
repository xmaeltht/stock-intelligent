"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type AuthUser = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
};

type AuthState = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

// Pull a human-readable message out of a FastAPI error body (string detail,
// validation array, or nothing).
async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  } catch {
    /* non-JSON body */
  }
  return fallback;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/research/auth/me", { cache: "no-store" });
      setUser(response.ok ? await response.json() : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await fetch("/api/research/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) throw new Error(await errorMessage(response, "Incorrect email or password"));
    setUser(await response.json());
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const response = await fetch("/api/research/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password, display_name: displayName || null }),
      });
      if (!response.ok) throw new Error(await errorMessage(response, "Could not create account"));
      setUser(await response.json());
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await fetch("/api/research/auth/logout", { method: "POST" });
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
