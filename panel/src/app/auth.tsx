import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import {
  changePassword as changePasswordRequest,
  login as loginRequest,
  logout as logoutRequest,
  me,
  updatePreferences as updatePreferencesRequest,
} from '../api/auth';
import { clearStoredToken } from '../api/client';
import type { AuthUser } from '../api/types';
import { canPermissions, type AppPermission } from './permissions';

interface AuthContextValue {
  ready: boolean;
  isAuthenticated: boolean;
  user: AuthUser | null;
  mustChangePassword: boolean;
  login: (username: string, password: string) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  updatePreferences: (preferences: { language?: string; timezone?: string }) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (permission: AppPermission, serverId?: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);

  async function refresh() {
    try {
      const response = await me();
      setUser(response.user);
    } catch {
      clearStoredToken();
      setUser(null);
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function login(username: string, password: string) {
    const response = await loginRequest(username, password);
    setUser(response.user);
    setReady(true);
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    const response = await changePasswordRequest(currentPassword, newPassword);
    setUser(response.user);
    setReady(true);
  }

  async function logout() {
    try {
      await logoutRequest();
    } catch {
      // ignore and still clear local auth state
    }
    clearStoredToken();
    setUser(null);
    setReady(true);
  }

  async function updatePreferences(preferences: { language?: string; timezone?: string }) {
    const response = await updatePreferencesRequest(preferences);
    setUser(response.user);
    setReady(true);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      isAuthenticated: Boolean(user),
      user,
      mustChangePassword: Boolean(user?.must_change_password),
      login,
      changePassword,
      updatePreferences,
      logout,
      refresh,
      can: (permission, serverId) => {
        if (!user) return false;
        if (user.must_change_password) return false;
        if (!canPermissions(user.permissions, permission)) return false;
        if (!serverId) return true;
        return user.allowed_servers.includes('*') || user.allowed_servers.includes(serverId);
      },
    }),
    [ready, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
