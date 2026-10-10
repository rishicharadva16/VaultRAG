import React from 'react';
import { User } from '../api/types';
import { DepartmentBadge } from './DepartmentBadge';

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
      className={`flex items-start gap-3 rounded-card border border-border bg-surface p-3 transition-colors ${className}`}
      data-testid="user-card"
    >
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-raised font-semibold text-text text-xs border border-border"
        aria-hidden="true"
      >
        {getInitials(user.name, user.email)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-text text-sm" title={user.name || user.email}>
          {user.name || user.email}
        </div>
        <div className="truncate text-text-muted text-xs" title={user.email}>
          {user.email}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {user.department && <DepartmentBadge department={user.department} size="sm" />}
          {isAdmin && <DepartmentBadge isAdmin={true} size="sm" />}
          {!user.department && !isAdmin && <DepartmentBadge department={null} size="sm" />}
        </div>
      </div>
    </div>
  );
};
