import React from 'react';
import { User } from '../api/types';
import { RoleBadge } from './RoleBadge';

interface UserCardProps {
  user: User;
  className?: string;
}

export const UserCard: React.FC<UserCardProps> = ({ user, className = '' }) => {
  const primaryRole = user.roles && user.roles.length > 0 ? user.roles[0] : 'employee';

  return (
    <div
      className={`flex items-start gap-3 rounded-card border border-border bg-surface p-3 transition-colors ${className}`}
      data-testid="user-card"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-raised font-semibold text-text text-sm border border-border">
        {user.name ? user.name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-text text-sm">{user.name || user.email}</div>
        <div className="truncate text-text-muted text-xs">{user.email}</div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          <RoleBadge role={primaryRole} size="sm" />
        </div>
      </div>
    </div>
  );
};
