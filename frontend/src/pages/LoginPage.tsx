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
    <div className="flex min-h-screen w-full bg-background text-text">
      {/* Left Brand Panel (lg and up) */}
      <div className="hidden lg:flex lg:w-1/2 relative flex-col justify-between p-12 bg-gradient-to-br from-[#0B1020] via-[#111A3A] to-[#1A1B4B] text-white overflow-hidden border-r border-[#232B4A]/60">
        {/* Ambient Blurred Colour Blobs */}
        <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-primary/20 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[450px] h-[450px] rounded-full bg-accent/20 blur-[130px] pointer-events-none" />
        
        {/* Faint Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-[0.04] pointer-events-none"
          style={{
            backgroundImage: `linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)`,
            backgroundSize: '36px 36px'
          }}
        />

        {/* Brand Header */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-accent shadow-md shadow-accent/20">
            <ShieldCheck size={26} className="text-white" aria-hidden="true" />
          </div>
          <span className="font-heading text-2xl font-bold tracking-tight text-white">
            VaultRAG
          </span>
        </div>

        {/* Hero Headline & Trust Points */}
        <div className="relative z-10 my-auto max-w-lg space-y-8">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-badge border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              Enterprise Zero-Knowledge RAG
            </div>
            <h1 className="font-heading text-3xl xl:text-4xl font-extrabold tracking-tight text-white leading-tight">
              Ask your documents. <br />
              <span className="bg-gradient-to-r from-accent to-primary bg-clip-text text-transparent">
                See only what you're allowed to.
              </span>
            </h1>
          </div>

          <div className="space-y-4 pt-2">
            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-accent">
                <Shield size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Access enforced at retrieval, on the server</h2>
                <p className="text-xs text-slate-300">Tokens filter raw vector embeddings prior to model synthesis.</p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-accent">
                <FileCheck2 size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Every answer cited to its exact source</h2>
                <p className="text-xs text-slate-300">Auditable highlighted text snippets and verified source bounding boxes.</p>
              </div>
            </div>

            <div className="flex items-start gap-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-accent">
                <HardDrive size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-white">Your documents never leave this machine</h2>
                <p className="text-xs text-slate-300">100% on-premises vector database, relational store, and neural runtime.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Left Footer */}
        <div className="relative z-10 text-xs text-slate-400 font-medium">
          Secure Multi-Modal RAG with Access Control • v1.0 Enterprise
        </div>
      </div>

      {/* Right Sign-in Panel */}
      <div className="flex flex-1 flex-col justify-between p-4 sm:p-8 lg:p-12 relative overflow-y-auto">
        <div className="flex justify-between items-center w-full">
          {/* Mobile Logo (< lg) */}
          <div className="flex items-center gap-2.5 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-gradient text-white shadow-xs">
              <ShieldCheck size={18} aria-hidden="true" />
            </div>
            <span className="font-heading text-lg font-bold text-text">VaultRAG</span>
          </div>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>

        {/* Centered Sign-in Card */}
        <div className="mx-auto w-full max-w-md my-auto py-8">
          <div className="rounded-card border border-border bg-surface p-7 sm:p-9 shadow-md relative">
            <div className="mb-6">
              <h2 className="font-heading text-2xl font-bold tracking-tight text-text">
                Welcome back
              </h2>
              <p className="mt-1 text-xs sm:text-sm text-text-muted">
                Sign in to your corporate workspace
              </p>
            </div>

            {/* Error Banner */}
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

            {/* Form */}
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
                    className="w-full rounded-input border border-border bg-surface-2/50 py-2.5 pl-9 pr-3.5 text-sm text-text placeholder:text-text-muted transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus:border-primary min-h-[42px]"
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
                    className="w-full rounded-input border border-border bg-surface-2/50 py-2.5 pl-9 pr-10 text-sm text-text placeholder:text-text-muted transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus:border-primary min-h-[42px]"
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
                className="w-full flex items-center justify-center gap-2 rounded-btn bg-brand-gradient py-2.5 px-4 text-sm font-semibold text-white shadow-sm hover:shadow-md hover:brightness-105 active:brightness-95 disabled:opacity-50 transition-all min-h-[42px] focus-visible:ring-2 focus-visible:ring-focus-ring outline-none"
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
              <p className="text-[11px] text-text-muted">
                Access is checked on the server for every question.
              </p>
            </div>
          </div>
        </div>

        <div className="text-center text-xs text-text-muted">
          VaultRAG • Secure Document & Data Retrieval System
        </div>
      </div>
    </div>
  );
};
