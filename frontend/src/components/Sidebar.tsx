import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { UserCard } from './UserCard';
import { ThemeToggle } from './ThemeToggle';
import {
  MessageSquare,
  Search,
  Files,
  LayoutDashboard,
  Users,
  LogOut,
  ShieldCheck,
} from 'lucide-react';

interface SidebarProps {
  onCloseMobile?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ onCloseMobile, className = '' }) => {
  const { user, logout } = useAuth();
  const isAdmin = Boolean(user?.roles && user.roles.includes('admin'));

  const handleLinkClick = () => {
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `group relative flex items-center gap-3 rounded-btn px-3 py-2.5 text-sm font-medium transition-all duration-150 min-h-[40px] ${
      isActive
        ? 'bg-accent text-accent-contrast font-semibold shadow-xs'
        : 'text-text-muted hover:bg-surface-raised hover:text-text'
    }`;

  return (
    <aside
      className={`flex h-full w-[260px] flex-col justify-between border-r border-border bg-surface p-4 text-text shadow-xs ${className}`}
      aria-label="Main Navigation"
      data-testid="app-sidebar"
    >
      <div className="space-y-6 overflow-y-auto pr-1">
        {/* Brand Logo & Wordmark */}
        <div className="flex items-center gap-3 px-2 pt-1">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-accent-contrast shadow-xs">
            <ShieldCheck size={20} className="text-white" aria-hidden="true" />
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-text leading-none">
              VaultRAG
            </div>
            <div className="text-[11px] font-medium text-text-muted mt-1">
              Enterprise Secure RAG
            </div>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1" aria-label="Application sections">
          <NavLink to="/chat" onClick={handleLinkClick} className={navLinkClass}>
            <MessageSquare size={18} className="shrink-0" aria-hidden="true" />
            <span>Chat Assistant</span>
          </NavLink>

          <NavLink to="/search" onClick={handleLinkClick} className={navLinkClass}>
            <Search size={18} className="shrink-0" aria-hidden="true" />
            <span>Document Search</span>
          </NavLink>

          <NavLink
            to="/documents"
            onClick={handleLinkClick}
            className={navLinkClass}
            data-testid="nav-documents"
          >
            <Files size={18} className="shrink-0" aria-hidden="true" />
            <span>My Documents</span>
          </NavLink>

          {/* Admin Section */}
          {isAdmin && (
            <div className="pt-4 mt-4 border-t border-border">
              <div className="px-3 pb-2 text-[11px] font-bold uppercase tracking-wider text-text-muted">
                ADMIN
              </div>
              <div className="space-y-1">
                <NavLink
                  to="/admin"
                  end
                  onClick={handleLinkClick}
                  className={navLinkClass}
                  data-testid="nav-admin"
                >
                  <LayoutDashboard size={18} className="shrink-0" aria-hidden="true" />
                  <span>Dashboard</span>
                </NavLink>

                <NavLink
                  to="/admin/users"
                  onClick={handleLinkClick}
                  className={navLinkClass}
                  data-testid="nav-admin-users"
                >
                  <Users size={18} className="shrink-0" aria-hidden="true" />
                  <span>User Management</span>
                </NavLink>
              </div>
            </div>
          )}
        </nav>
      </div>

      {/* User Card & Footer Controls at Bottom */}
      <div className="space-y-3 pt-4 border-t border-border shrink-0">
        {user && <UserCard user={user} />}

        <div className="flex items-center gap-2 pt-1">
          <ThemeToggle className="flex-1 justify-center rounded-btn py-2 text-text-muted hover:text-text hover:bg-surface-raised min-h-[40px] text-xs font-semibold" />

          <button
            type="button"
            onClick={logout}
            aria-label="Sign out of VaultRAG"
            className="flex items-center justify-center gap-2 rounded-btn px-3 py-2 text-xs font-semibold text-danger hover:bg-danger/10 transition-colors min-h-[40px]"
            data-testid="sign-out-button"
            title="Sign out"
          >
            <LogOut size={16} aria-hidden="true" />
            <span className="sr-only sm:not-sr-only">Sign out</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
