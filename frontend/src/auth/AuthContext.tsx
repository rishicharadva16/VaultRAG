import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, clearSession, getAuthToken, setAuthToken, setOnUnauthorized } from '../api/client';
import { User } from '../api/types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  switchDemoUser?: (demoUser?: unknown) => Promise<void>;
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

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        error,
        login,
        logout,
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
