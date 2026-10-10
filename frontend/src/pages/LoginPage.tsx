import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ThemeToggle } from '../components/ThemeToggle';
import { Eye, EyeOff, Lock, Mail, ShieldCheck, FileCheck, Loader2, AlertCircle } from 'lucide-react';
import { ApiClientError } from '../api/client';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

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
    setEmailError(null);
    setPasswordError(null);
    clearError();

    const trimmedEmail = email.trim();
    let hasValidationError = false;

    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      hasValidationError = true;
    } else if (!validateEmail(trimmedEmail)) {
      setEmailError('Please enter a valid email address.');
      hasValidationError = true;
    }

    if (!password) {
      setPasswordError('Password is required.');
      hasValidationError = true;
    }

    if (hasValidationError) {
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
    <div className="relative flex min-h-screen w-full flex-col justify-between items-center bg-background p-4 sm:p-6 text-text overflow-hidden select-none sm:select-auto">
      {/* Decorative dot pattern (6% opacity, aria-hidden) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage: 'radial-gradient(currentColor 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Soft primary-tinted decorative circles in top and bottom corners (5% opacity) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 -left-32 h-80 w-80 rounded-full bg-accent opacity-[0.05]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-32 -right-32 h-80 w-80 rounded-full bg-accent opacity-[0.05]"
      />

      {/* Header: Theme toggle at top right */}
      <header className="w-full flex justify-end z-20 shrink-0">
        <ThemeToggle className="rounded-xl border border-border bg-surface/70 hover:bg-surface-raised px-3 py-1.5 shadow-xs text-xs" />
      </header>

      {/* Main Container: Centered both ways */}
      <main className="my-auto flex flex-col items-center justify-center w-full max-w-[440px] z-10 px-0">
        <div className="w-full rounded-[20px] border border-border bg-surface p-7 sm:p-10 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.08),0_12px_48px_-6px_rgba(0,0,0,0.06)] relative overflow-hidden login-card-anim">
          {/* 4px primary-colored bar across the top inside rounded corners */}
          <div className="absolute top-0 inset-x-0 h-1 bg-accent" aria-hidden="true" />

          {/* Logo Mark, Wordmark, and Tagline */}
          <div className="text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-accent-contrast shadow-xs mb-3">
              <ShieldCheck size={30} aria-hidden="true" />
            </div>
            <h2 className="text-[24px] font-bold text-text tracking-tight leading-none">VaultRAG</h2>
            <p className="mt-1 text-xs text-text-muted font-medium">
              Secure Multi-Modal RAG with Access Control
            </p>
          </div>

          {/* Heading and Subtitle */}
          <div className="text-center mt-5 mb-5">
            <h1 className="text-[26px] font-bold text-text tracking-tight leading-tight">
              Welcome back
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-text-muted">Sign in to your workspace</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="login-email" className="block text-xs font-semibold text-text mb-1.5">
                Email address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-muted">
                  <Mail size={17} aria-hidden="true" />
                </div>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError(null);
                    if (localError) setLocalError(null);
                  }}
                  disabled={isSubmitting}
                  required
                  placeholder="name@company.com"
                  className={`h-[46px] w-full rounded-xl border bg-background pl-10 pr-3.5 text-sm text-text placeholder:text-text-muted transition-colors focus:outline-none focus:ring-2 ${
                    emailError
                      ? 'border-danger focus:border-danger focus:ring-danger/20'
                      : 'border-border focus:border-accent focus:ring-accent'
                  }`}
                  autoComplete="username"
                />
              </div>
              {emailError && (
                <p className="mt-1.5 text-xs text-danger flex items-center gap-1 font-medium">
                  <AlertCircle size={13} className="shrink-0" aria-hidden="true" />
                  <span>{emailError}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="login-password" className="block text-xs font-semibold text-text mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-muted">
                  <Lock size={17} aria-hidden="true" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (passwordError) setPasswordError(null);
                    if (localError) setLocalError(null);
                  }}
                  disabled={isSubmitting}
                  required
                  placeholder="••••••••••••"
                  className={`h-[46px] w-full rounded-xl border bg-background pl-10 pr-11 text-sm text-text placeholder:text-text-muted transition-colors focus:outline-none focus:ring-2 ${
                    passwordError
                      ? 'border-danger focus:border-danger focus:ring-danger/20'
                      : 'border-border focus:border-accent focus:ring-accent'
                  }`}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-text-muted hover:text-text transition-colors cursor-pointer"
                >
                  {showPassword ? <EyeOff size={17} aria-hidden="true" /> : <Eye size={17} aria-hidden="true" />}
                </button>
              </div>
              {passwordError && (
                <p className="mt-1.5 text-xs text-danger flex items-center gap-1 font-medium">
                  <AlertCircle size={13} className="shrink-0" aria-hidden="true" />
                  <span>{passwordError}</span>
                </p>
              )}
            </div>

            {/* Inline Error Message */}
            {displayedError && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-xl border border-red-300 bg-red-50 p-3 text-xs text-red-900 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200"
                data-testid="login-error"
              >
                <AlertCircle size={16} className="shrink-0 text-danger mt-0.5" aria-hidden="true" />
                <div className="leading-relaxed font-medium">{displayedError}</div>
              </div>
            )}

            {/* Submit Button: 46px solid primary */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full h-[46px] min-h-[46px] flex items-center justify-center gap-2 rounded-xl bg-accent py-2.5 px-4 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
              data-testid="login-submit-button"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={17} className="animate-spin text-accent-contrast" aria-hidden="true" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Sign in</span>
              )}
            </button>
          </form>

          {/* Thin divider and helper line */}
          <div className="pt-4 mt-5 border-t border-border-subtle/50 text-center">
            <div className="inline-flex items-center justify-center gap-1.5 text-xs text-text-muted">
              <ShieldCheck size={14} className="text-accent shrink-0" aria-hidden="true" />
              <span>Access is checked on the server for every question.</span>
            </div>
          </div>
        </div>

        {/* Row of three small chips outside the box */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-2.5 mt-5 text-xs text-text-muted max-w-md mx-auto">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface/80 border border-border text-[11px] sm:text-xs shadow-xs">
            <ShieldCheck size={13} className="text-accent shrink-0" aria-hidden="true" />
            <span>Access enforced at retrieval</span>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface/80 border border-border text-[11px] sm:text-xs shadow-xs">
            <FileCheck size={13} className="text-accent shrink-0" aria-hidden="true" />
            <span>Every answer cited</span>
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface/80 border border-border text-[11px] sm:text-xs shadow-xs">
            <Lock size={13} className="text-accent shrink-0" aria-hidden="true" />
            <span>Private by design</span>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-text-muted py-2 shrink-0 z-10">
        VaultRAG — Secure Document and Data Retrieval System
      </footer>

      {/* Scoped fade-and-rise motion style */}
      <style>{`
        @keyframes loginFadeRise {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .login-card-anim {
          animation: loginFadeRise 200ms ease-out forwards;
        }
        @media (prefers-reduced-motion: reduce) {
          .login-card-anim {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
          }
        }
      `}</style>
    </div>
  );
};

