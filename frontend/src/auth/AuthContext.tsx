import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, clearSession, getAuthToken, setAuthToken, setOnUnauthorized } from '../api/client';
import { DemoUser, User } from '../api/types';

export const SEED_PASSWORD = 'changeme123';

export const DEMO_USERS: DemoUser[] = [
  { externalId: 'u_asha', name: 'Asha Patel', email: 'asha.patel@northwind.example', role: 'employee', label: 'Employee (Eng)' },
  { externalId: 'u_neha', name: 'Neha Desai', email: 'neha.desai@northwind.example', role: 'employee', label: 'Employee (Sales)' },
  { externalId: 'u_ravi', name: 'Ravi Menon', email: 'ravi.menon@northwind.example', role: 'manager', label: 'Manager (Eng)' },
  { externalId: 'u_dev', name: 'Dev Joshi', email: 'dev.joshi@northwind.example', role: 'manager', label: 'Manager (Sales)' },
  { externalId: 'u_meera', name: 'Meera Iyer', email: 'meera.iyer@northwind.example', role: 'hr_admin', label: 'HR Admin' },
  { externalId: 'u_karan', name: 'Karan Shah', email: 'karan.shah@northwind.example', role: 'finance_admin', label: 'Finance Admin' },
  { externalId: 'u_admin', name: 'Platform Admin', email: 'admin@northwind.example', role: 'admin', label: 'Administrator' },
];

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchDemoUser: (demoUser: DemoUser) => Promise<void>;
  clearError: () => void;
  setError: (msg: string | null) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  // Initialize auth on mount
  useEffect(() => {
    const handleUnauthorized = () => {
      clearSession();
      setUser(null);
      setError('Your session expired. Please sign in again.');
    };

    setOnUnauthorized(handleUnauthorized);

    const initAuth = async () => {
      const token = getAuthToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await api.getMe();
        setUser(currentUser);
      } catch {
        // Any error / 401 on start clears session
        clearSession();
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const tokenRes = await api.login({ email, password });
      setAuthToken(tokenRes.access_token);
      const currentUser = await api.getMe();
      setUser(currentUser);
    } catch (err) {
      clearSession();
      setUser(null);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const switchDemoUser = async (demoUser: DemoUser) => {
    setError(null);
    setIsLoading(true);
    try {
      clearSession();
      setUser(null);
      await login(demoUser.email, SEED_PASSWORD);
    } finally {
      setIsLoading(false);
    }
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        error,
        login,
        logout,
        switchDemoUser,
        clearError,
        setError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
