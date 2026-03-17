"use client";

/**
 * Auth context for Sentinel frontend.
 * Manages JWT tokens and current user state.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

import { appQueryClient } from "@/components/QueryProvider";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type UserRole = "auditor" | "supervisor" | "admin" | "system";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isSupervisorOrAdmin: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "sentinel_access_token";
const REFRESH_KEY = "sentinel_refresh_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    isLoading: true,
  });

  const fetchCurrentUser = useCallback(async (token: string): Promise<AuthUser | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  }, []);

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    if (!refreshToken) return null;

    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      return data.access_token;
    } catch {
      return null;
    }
  }, []);

  // On mount, restore session from localStorage
  useEffect(() => {
    const init = async () => {
      const stored = localStorage.getItem(TOKEN_KEY);
      if (!stored) {
        setState((s) => ({ ...s, isLoading: false }));
        return;
      }

      let user = await fetchCurrentUser(stored);

      if (!user) {
        // Try refreshing
        const newToken = await refreshAccessToken();
        if (newToken) {
          user = await fetchCurrentUser(newToken);
          if (user) {
            setState({ user, accessToken: newToken, isLoading: false });
            return;
          }
        }
        // Clear invalid tokens
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_KEY);
        appQueryClient.clear();
        setState({ user: null, accessToken: null, isLoading: false });
        return;
      }

      setState({ user, accessToken: stored, isLoading: false });
    };

    init();
  }, [fetchCurrentUser, refreshAccessToken]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    appQueryClient.clear();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);

    const user = await fetchCurrentUser(data.access_token);
    if (!user) throw new Error("Failed to fetch user after login");

    setState({ user, accessToken: data.access_token, isLoading: false });
  }, [fetchCurrentUser]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    appQueryClient.clear();
    setState({ user: null, accessToken: null, isLoading: false });
  }, []);

  const isSupervisorOrAdmin =
    state.user?.role === "supervisor" || state.user?.role === "admin";
  const isAdmin = state.user?.role === "admin";

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        isSupervisorOrAdmin,
        isAdmin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
