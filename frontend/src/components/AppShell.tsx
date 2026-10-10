import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Menu, X, ShieldCheck } from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  // Close drawer on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false);
      }
    };
    if (mobileMenuOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [mobileMenuOpen]);

  // Derive subtle breadcrumbs & page titles
  const getHeaderMeta = () => {
    const p = location.pathname;
    if (p.startsWith('/chat')) {
      return { title: 'Chat Assistant', breadcrumb: 'Workspace / Assistant' };
    }
    if (p.startsWith('/search')) {
      return { title: 'Document Search', breadcrumb: 'Workspace / Search' };
    }
    if (p.startsWith('/documents')) {
      return { title: 'My Documents', breadcrumb: 'Workspace / Documents' };
    }
    if (p.startsWith('/admin/users')) {
      return { title: 'User Management', breadcrumb: 'Admin / Users' };
    }
    if (p.startsWith('/admin')) {
      return { title: 'Admin Dashboard', breadcrumb: 'Admin / Monitoring' };
    }
    return { title: 'VaultRAG', breadcrumb: 'Enterprise Secure RAG' };
  };

  const headerMeta = getHeaderMeta();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-text">
      {/* Desktop Sidebar (>= md) */}
      <div className="hidden md:flex shrink-0">
        <Sidebar />
      </div>

      {/* Mobile Drawer Backdrop & Slide-in (< md) */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 flex md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation Menu"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 transition-opacity duration-200"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />

          {/* Slide-in Drawer */}
          <div className="relative z-10 flex h-full max-w-[85vw] animate-in slide-in-from-left duration-200">
            <Sidebar onCloseMobile={() => setMobileMenuOpen(false)} />
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="Close navigation menu"
              className="absolute top-4 right-4 rounded-btn p-2 text-text-muted hover:text-text hover:bg-surface-raised md:hidden min-h-[40px] min-w-[40px] flex items-center justify-center"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Top Header Bar */}
        <header className="flex h-14 sm:h-16 items-center justify-between border-b border-border bg-surface px-4 md:px-6 shrink-0 z-10 transition-colors">
          <div className="flex items-center gap-3">
            {/* Mobile Hamburger (< md) */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation menu"
              className="flex h-10 w-10 items-center justify-center rounded-btn text-text-muted hover:bg-surface-2 hover:text-text md:hidden transition-colors"
            >
              <Menu size={22} aria-hidden="true" />
            </button>

            {/* Mobile Logo (< md) */}
            <div className="flex items-center gap-2 md:hidden">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-accent-contrast shadow-xs">
                <ShieldCheck size={16} aria-hidden="true" />
              </div>
              <span className="font-bold text-base text-text">VaultRAG</span>
            </div>

            {/* Desktop Title & Breadcrumb (>= md) */}
            <div className="hidden md:flex flex-col">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">
                {headerMeta.breadcrumb}
              </span>
              <span className="font-bold text-base text-text leading-tight">
                {headerMeta.title}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-text-muted font-medium bg-surface-2 px-2.5 py-1 rounded-badge border border-border">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>ACL Active</span>
            </div>
          </div>
        </header>

        {/* Page Content Container: max-w-1200px centered with consistent padding */}
        <main
          className="flex-1 overflow-hidden flex flex-col relative w-full"
          role="main"
        >
          {children}
        </main>
      </div>
    </div>
  );
};
