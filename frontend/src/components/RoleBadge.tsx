import React from 'react';
import { Role } from '../api/types';
import { formatRoleLabel } from '../lib/format';
import { ShieldCheck, User, Users, Briefcase, Calculator } from 'lucide-react';

interface RoleBadgeProps {
  role: Role;
  className?: string;
  size?: 'sm' | 'md';
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({ role, className = '', size = 'sm' }) => {
  const getBadgeStyle = (r: Role) => {
    switch (r) {
      case 'admin':
        return {
          bg: 'bg-purple-100 text-purple-900 border-purple-300 dark:bg-purple-950/60 dark:text-purple-200 dark:border-purple-800',
          Icon: ShieldCheck,
        };
      case 'hr_admin':
        return {
          bg: 'bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-800',
          Icon: Users,
        };
      case 'finance_admin':
        return {
          bg: 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800',
          Icon: Calculator,
        };
      case 'manager':
        return {
          bg: 'bg-indigo-100 text-indigo-900 border-indigo-300 dark:bg-indigo-950/60 dark:text-indigo-200 dark:border-indigo-800',
          Icon: Briefcase,
        };
      case 'employee':
      default:
        return {
          bg: 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800/80 dark:text-slate-200 dark:border-slate-700',
          Icon: User,
        };
    }
  };

  const { bg, Icon } = getBadgeStyle(role);
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';
  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-badge border font-medium transition-colors ${bg} ${sizeClasses} ${className}`}
      data-testid={`role-badge-${role}`}
    >
      <Icon size={iconSize} aria-hidden="true" className="shrink-0" />
      <span>{formatRoleLabel(role)}</span>
    </span>
  );
};
