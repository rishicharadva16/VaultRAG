import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth, DEMO_USERS } from '../auth/AuthContext';
import { UserCard } from './UserCard';
import { ThemeToggle } from './ThemeToggle';
import { RoleBadge } from './RoleBadge';
import {
  MessageSquare,
  Search,
  LogOut,
  Users,
  ChevronDown,
} from 'lucide-react';

interface SidebarProps {
  onCloseMobile?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ onCloseMobile, className = '' }) => {
  const { user, logout, switchDemoUser } = useAuth();
  const [showDemoMenu, setShowDemoMenu] = useState(false);
  const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

  const handleLinkClick = () => {
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  const handleDemoSwitch = async (demoUser: typeof DEMO_USERS[0]) => {
    setShowDemoMenu(false);
    if (onCloseMobile) onCloseMobile();
    await switchDemoUser(demoUser);
  };

  return (
    <aside
      className={`flex h-full w-[260px] flex-col justify-between border-r border-border bg-surface p-4 transition-colors ${className}`}
      aria-label="Main Navigation"
      data-testid="app-sidebar"
    >
      <div className="space-y-6">
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

        {/* Navigation Links */}
        <nav className="space-y-1">
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
        </nav>

        {/* Demo User Switcher Menu */}
        {isDemoMode && (
          <div className="relative border-t border-border-subtle pt-4">
            <button
              type="button"
              onClick={() => setShowDemoMenu(!showDemoMenu)}
              className="flex w-full items-center justify-between rounded-btn border border-border bg-surface-raised px-3 py-2 text-xs font-medium text-text hover:bg-border transition-colors"
              aria-expanded={showDemoMenu}
              aria-haspopup="true"
              data-testid="switch-demo-user-button"
            >
              <span className="flex items-center gap-2">
                <Users size={14} className="text-accent" aria-hidden="true" />
                <span>Switch demo user</span>
              </span>
              <ChevronDown
                size={14}
                className={`transition-transform ${showDemoMenu ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </button>

            {showDemoMenu && (
              <div
                className="absolute left-0 top-full mt-1.5 z-50 w-full rounded-card border border-border bg-surface p-1.5 shadow-raised max-h-64 overflow-y-auto"
                role="menu"
                aria-orientation="vertical"
              >
                {DEMO_USERS.map((du) => (
                  <button
                    key={du.externalId}
                    type="button"
                    onClick={() => handleDemoSwitch(du)}
                    className="flex w-full items-center justify-between rounded-btn px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-surface-raised"
                    role="menuitem"
                  >
                    <div className="truncate pr-2">
                      <div className="font-medium text-text truncate">{du.name}</div>
                      <div className="text-[10px] text-text-muted truncate">{du.email}</div>
                    </div>
                    <RoleBadge role={du.role} size="sm" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer: Theme Toggle & Sign Out */}
      <div className="border-t border-border-subtle pt-4 space-y-2">
        <ThemeToggle className="w-full justify-start" />

        <button
          type="button"
          onClick={logout}
          aria-label="Sign out"
          className="flex w-full items-center gap-2 rounded-btn px-2.5 py-1.5 text-sm font-medium text-text-muted transition-colors hover:bg-red-50 hover:text-danger dark:hover:bg-red-950/40"
          data-testid="sign-out-button"
        >
          <LogOut size={16} aria-hidden="true" />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
};
