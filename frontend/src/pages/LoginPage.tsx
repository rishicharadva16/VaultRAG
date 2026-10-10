import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { ThemeToggle } from '../components/ThemeToggle';
import { Eye, EyeOff, Lock, Mail, ShieldCheck, Loader2, AlertCircle, Shield, FileCheck2, HardDrive } from 'lucide-react';
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
    <div className="flex flex-col lg:flex-row h-screen max-h-screen w-full overflow-hidden bg-background text-text select-none">
      {/* ── Left Panel (Solid primary blue, subtle faint grid/dots, vertically centered) ── */}
      <div className="bg-[#2563eb] text-white shrink-0 lg:w-1/2 flex flex-col justify-between p-6 sm:p-8 lg:p-12 relative overflow-hidden">
        {/* Subtle Faint Dot/Grid Pattern at Low Opacity */}
        <div
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.4) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
          aria-hidden="true"
        />

        {/* Top Header: Logo Mark & Wordmark */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20 text-white shadow-xs">
              <ShieldCheck size={24} aria-hidden="true" />
            </div>
            <span className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              VaultRAG
            </span>
          </div>

          {/* On mobile (< lg), theme toggle in header */}
          <div className="lg:hidden">
            <ThemeToggle className="text-white hover:bg-white/15 rounded-btn p-1.5 transition-colors" />
          </div>
        </div>

        {/* Center Content: Headline & Trust Points */}
        <div className="relative z-10 my-auto py-3 lg:py-6 max-w-lg space-y-5 lg:space-y-7">
          {/* Headline Section */}
          <div className="space-y-3">
            <div className="hidden lg:inline-flex items-center gap-2 rounded-badge border border-white/25 bg-white/15 px-3 py-1 text-xs font-semibold text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
              Secure Multi-Modal RAG
            </div>

            <h1 className="text-xl sm:text-2xl lg:text-[clamp(28px,2.8vw,42px)] font-bold tracking-tight text-white leading-tight">
              Ask your documents.
              <br />
              See only what you are allowed to.
            </h1>

            <p className="hidden lg:block text-sm text-white/85 leading-relaxed">
              Enterprise search and question answering with strict role and department access control.
            </p>
          </div>

          {/* Three Trust Points (Desktop / lg only to keep layout non-scrolling) */}
          <div className="hidden lg:flex flex-col space-y-4">
            <div className="flex items-start gap-3.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white">
                <Shield size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Access enforced at retrieval, on the server
                </h2>
                <p className="text-xs text-white/80 mt-0.5">
                  Permission tokens filter raw vector embeddings prior to model synthesis.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white">
                <FileCheck2 size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Every answer cited to its exact source
                </h2>
                <p className="text-xs text-white/80 mt-0.5">
                  Auditable highlighted text snippets and verified source bounding boxes.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white">
                <HardDrive size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Your documents never leave this machine
                </h2>
                <p className="text-xs text-white/80 mt-0.5">
                  100% on-premises vector database, relational store, and neural runtime.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer (Desktop / lg only) */}
        <div className="relative z-10 hidden lg:block text-xs text-white/70 font-medium">
          Secure Multi-Modal RAG with Access Control
        </div>
      </div>

      {/* ── Right Sign-in Panel (Same page background as app, centered white card, subtle theme toggle top right) ── */}
      <div className="flex-1 flex flex-col justify-between p-6 sm:p-8 lg:p-12 relative overflow-y-auto bg-background">
        {/* Top-Right Theme Toggle on Desktop */}
        <div className="hidden lg:flex justify-end w-full">
          <ThemeToggle className="text-text-muted hover:text-text rounded-btn p-1.5 transition-colors" />
        </div>

        {/* Centered White Card (max-w-[420px], 16px radius, soft shadow) */}
        <div className="mx-auto w-full max-w-[420px] my-auto">
          <div className="rounded-card border border-border bg-surface p-7 sm:p-8 shadow-soft">
            <div className="mb-6">
              <h2 className="text-2xl font-bold tracking-tight text-text">
                Welcome back
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                Sign in to your workspace
              </p>
            </div>

            {/* Inline Error Banner */}
            {displayedError && (
              <div
                role="alert"
                className="mb-5 flex items-start gap-2.5 rounded-btn border border-danger/30 bg-danger/10 p-3 text-xs text-danger"
                data-testid="login-error"
              >
                <AlertCircle size={16} className="shrink-0 text-danger mt-0.5" aria-hidden="true" />
                <div className="leading-relaxed font-medium">{displayedError}</div>
              </div>
            )}

            {/* Sign-in Form */}
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div>
                <label htmlFor="login-email" className="block text-xs font-semibold text-text mb-1.5">
                  Email address
                </label>
                <div className="relative flex items-center">
                  <div className="pointer-events-none absolute left-3 flex items-center text-text-muted">
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
                    className="w-full rounded-input border border-border bg-surface-raised py-2.5 pl-9 pr-3.5 text-sm text-text placeholder:text-text-muted transition-colors outline-hidden focus:border-accent min-h-[42px]"
                    autoComplete="email"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password" className="block text-xs font-semibold text-text mb-1.5">
                  Password
                </label>
                <div className="relative flex items-center">
                  <div className="pointer-events-none absolute left-3 flex items-center text-text-muted">
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
                    className="w-full rounded-input border border-border bg-surface-raised py-2.5 pl-9 pr-10 text-sm text-text placeholder:text-text-muted transition-colors outline-hidden focus:border-accent min-h-[42px]"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 flex items-center text-text-muted hover:text-text p-1 rounded"
                  >
                    {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex items-center justify-center gap-2 rounded-btn bg-accent hover:bg-accent-hover text-accent-contrast py-2.5 px-4 text-sm font-semibold shadow-xs transition-colors disabled:opacity-50 min-h-[42px] focus-visible:ring-2 focus-visible:ring-focus-ring outline-hidden cursor-pointer"
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

            <div className="mt-5 border-t border-border-subtle pt-4 text-center">
              <p className="text-xs text-text-muted">
                Access is checked on the server for every question.
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-text-muted py-2">
          VaultRAG • Secure Document & Data Retrieval System
        </div>
      </div>
    </div>
  );
};
