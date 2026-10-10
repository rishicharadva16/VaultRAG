import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ThemeToggle } from '../components/ThemeToggle';
import { Eye, EyeOff, Lock, Mail, ShieldCheck, Loader2, AlertCircle } from 'lucide-react';
import { ApiClientError } from '../api/client';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const { login, error: authError, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/chat';

  const validateEmail = (val: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setLocalError('Please enter both email and password.');
      return;
    }

    if (!validateEmail(trimmedEmail)) {
      setLocalError('Please enter a valid email address.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(trimmedEmail, password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setLocalError(err.message || 'Invalid email or password.');
      } else {
        setLocalError('Cannot reach the VaultRAG server. Is the backend running?');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayedError = localError || authError;

  return (
    <div className="flex min-h-screen w-full flex-col justify-between bg-background p-4 sm:p-6 text-text">
      <header className="flex justify-end">
        <ThemeToggle />
      </header>

      <main className="mx-auto w-full max-w-md my-auto">
        <div className="rounded-card border border-border bg-surface p-6 sm:p-8 shadow-raised">
          {/* VaultRAG Logo & Header */}
          <div className="text-center mb-6">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-accent text-accent-contrast shadow-sm mb-3">
              <ShieldCheck size={28} aria-hidden="true" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-text">Sign in to VaultRAG</h1>
            <p className="mt-1.5 text-xs text-text-muted">
              Enter your corporate credentials to access authorized documents.
            </p>
          </div>

          {/* Inline Error Message */}
          {displayedError && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-2.5 rounded-card border border-red-300 bg-red-50 p-3 text-xs text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
              data-testid="login-error"
            >
              <AlertCircle size={16} className="shrink-0 text-danger mt-0.5" aria-hidden="true" />
              <div className="leading-relaxed">{displayedError}</div>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="login-email" className="block text-xs font-semibold text-text mb-1">
                Email address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-text-muted">
                  <Mail size={16} aria-hidden="true" />
                </div>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (localError) setLocalError(null);
                  }}
                  disabled={isSubmitting}
                  required
                  placeholder="name@northwind.example"
                  className="w-full rounded-input border border-border bg-background py-2 pl-9 pr-3 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="block text-xs font-semibold text-text mb-1">
                Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-text-muted">
                  <Lock size={16} aria-hidden="true" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (localError) setLocalError(null);
                  }}
                  disabled={isSubmitting}
                  required
                  placeholder="••••••••••••"
                  className="w-full rounded-input border border-border bg-background py-2 pl-9 pr-10 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-muted hover:text-text"
                >
                  {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full flex items-center justify-center gap-2 rounded-btn bg-accent py-2 px-4 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-50 transition-colors focus-visible:ring-2 focus-visible:ring-accent"
              data-testid="login-submit-button"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Sign in</span>
              )}
            </button>
          </form>
        </div>
      </main>

      <footer className="text-center text-xs text-text-muted">
        VaultRAG • Secure Document & Data Retrieval System
      </footer>
    </div>
  );
};
