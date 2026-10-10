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

  return (
    <aside
      className={`flex h-full w-[260px] flex-col justify-between border-r border-border bg-surface p-4 transition-colors ${className}`}
      aria-label="Main Navigation"
      data-testid="app-sidebar"
    >
      <div className="space-y-6 overflow-y-auto">
        {/* App Title / Header */}
        <div className="flex items-center gap-2.5 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-contrast shadow-xs font-bold text-base">
            V
          </div>
          <div>
            <div className="font-bold text-base tracking-tight text-text">VaultRAG</div>
            <div className="text-[11px] font-medium text-text-muted">Enterprise Secure RAG</div>
          </div>
        </div>

        {/* Current User Card */}
        {user && <UserCard user={user} />}

        {/* Main Navigation Links */}
        <nav className="space-y-1" aria-label="Application sections">
          <NavLink
            to="/chat"
            onClick={handleLinkClick}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-accent text-accent-contrast'
                  : 'text-text-muted hover:bg-surface-raised hover:text-text'
              }`
            }
          >
            <MessageSquare size={17} aria-hidden="true" />
            <span>Chat Assistant</span>
          </NavLink>

          <NavLink
            to="/search"
            onClick={handleLinkClick}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-accent text-accent-contrast'
                  : 'text-text-muted hover:bg-surface-raised hover:text-text'
              }`
            }
          >
            <Search size={17} aria-hidden="true" />
            <span>Document Search</span>
          </NavLink>

          <NavLink
            to="/documents"
            onClick={handleLinkClick}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-accent text-accent-contrast'
                  : 'text-text-muted hover:bg-surface-raised hover:text-text'
              }`
            }
            data-testid="nav-documents"
          >
            <Files size={17} aria-hidden="true" />
            <span>My Documents</span>
          </NavLink>

          {/* Admin Group (Visible to Admin Only) */}
          {isAdmin && (
            <div className="pt-4 mt-4 border-t border-border-subtle">
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Admin
              </div>
              <div className="space-y-1">
                <NavLink
                  to="/admin"
                  end
                  onClick={handleLinkClick}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-accent text-accent-contrast'
                        : 'text-text-muted hover:bg-surface-raised hover:text-text'
                    }`
                  }
                  data-testid="nav-admin"
                >
                  <LayoutDashboard size={17} aria-hidden="true" />
                  <span>Dashboard</span>
                </NavLink>

                <NavLink
                  to="/admin/users"
                  onClick={handleLinkClick}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-accent text-accent-contrast'
                        : 'text-text-muted hover:bg-surface-raised hover:text-text'
                    }`
                  }
                  data-testid="nav-admin-users"
                >
                  <Users size={17} aria-hidden="true" />
                  <span>User Management</span>
                </NavLink>
              </div>
            </div>
          )}
        </nav>
      </div>

      {/* Footer: Theme Toggle & Sign Out */}
      <div className="border-t border-border-subtle pt-4 space-y-2 shrink-0">
        <ThemeToggle className="w-full justify-start min-h-[40px] md:min-h-0" />

        <button
          type="button"
          onClick={logout}
          aria-label="Sign out of VaultRAG"
          className="flex w-full items-center gap-2 rounded-btn px-2.5 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-red-50 hover:text-danger dark:hover:bg-red-950/40 min-h-[40px] md:min-h-0"
          data-testid="sign-out-button"
        >
          <LogOut size={16} aria-hidden="true" />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
};
