import React from 'react';
import { User } from '../api/types';
import { Badge } from './ui/Badge';

interface UserCardProps {
  user: User;
  className?: string;
}

export const UserCard: React.FC<UserCardProps> = ({ user, className = '' }) => {
  const isAdmin = Boolean(user.roles && user.roles.includes('admin'));

  const getInitials = (name?: string, email?: string): string => {
    if (name && name.trim()) {
      const parts = name.trim().split(/\s+/);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      }
      return parts[0].slice(0, 2).toUpperCase();
    }
    return (email || 'U').charAt(0).toUpperCase();
  };

  return (
    <div
      className={`flex items-start gap-3 rounded-card border border-border bg-surface-raised p-3 transition-colors ${className}`}
      data-testid="user-card"
    >
      {/* Solid Avatar */}
      <div
        className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-accent-contrast font-bold text-xs shrink-0 select-none shadow-xs"
        aria-hidden="true"
      >
        {getInitials(user.name, user.email)}
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate font-semibold text-text text-sm" title={user.name || user.email}>
          {user.name || user.email}
        </div>
        <div className="truncate text-text-muted text-xs" title={user.email}>
          {user.email}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {user.department && <Badge department={user.department} size="sm" />}
          {isAdmin && <Badge isAdmin={true} size="sm" />}
          {!user.department && !isAdmin && <Badge department={null} size="sm" />}
        </div>
      </div>
    </div>
  );
};
