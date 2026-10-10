import React from 'react';
import { Users, Calculator, Code2, Briefcase, ShieldCheck, Building2 } from 'lucide-react';

export type DepartmentType = 'HR' | 'Finance' | 'Engineering' | 'Sales' | string;

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  department?: DepartmentType | null;
  isAdmin?: boolean;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  department,
  isAdmin = false,
  size = 'sm',
  className = '',
  ...props
}) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs gap-1.5' : 'px-2.5 py-1 text-sm gap-2';
  const iconSize = size === 'sm' ? 12 : 14;

  if (isAdmin) {
    return (
      <span
        className={`inline-flex items-center font-medium rounded-badge border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 dark:border-rose-500/20 select-none ${sizeClasses} ${className}`}
        data-testid="badge-admin"
        {...props}
      >
        <ShieldCheck size={iconSize} className="shrink-0 text-rose-600 dark:text-rose-400" aria-hidden="true" />
        <span>Admin</span>
      </span>
    );
  }

  const dept = department || 'General';
  const lower = dept.toLowerCase();

  let styleClasses = 'border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300';
  let Icon = Building2;
  let iconColor = 'text-slate-600 dark:text-slate-400';

  if (lower === 'hr') {
    styleClasses = 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
    Icon = Users;
    iconColor = 'text-emerald-600 dark:text-emerald-400';
  } else if (lower === 'finance') {
    styleClasses = 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300';
    Icon = Calculator;
    iconColor = 'text-amber-600 dark:text-amber-400';
  } else if (lower === 'engineering') {
    styleClasses = 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300';
    Icon = Code2;
    iconColor = 'text-blue-600 dark:text-blue-400';
  } else if (lower === 'sales') {
    styleClasses = 'border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300';
    Icon = Briefcase;
    iconColor = 'text-violet-600 dark:text-violet-400';
  }

  return (
    <span
      className={`inline-flex items-center font-medium rounded-badge border select-none ${styleClasses} ${sizeClasses} ${className}`}
      data-testid={`badge-dept-${lower}`}
      {...props}
    >
      <Icon size={iconSize} className={`shrink-0 ${iconColor}`} aria-hidden="true" />
      <span>{dept}</span>
    </span>
  );
};
