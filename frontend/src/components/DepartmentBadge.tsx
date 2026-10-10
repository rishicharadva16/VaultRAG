import React from 'react';
import { ShieldCheck, Building2, Users, Calculator, Code2, Briefcase } from 'lucide-react';

interface DepartmentBadgeProps {
  department?: string | null;
  isAdmin?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export const DepartmentBadge: React.FC<DepartmentBadgeProps> = ({
  department,
  isAdmin = false,
  className = '',
  size = 'sm',
}) => {
  if (isAdmin) {
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-badge border font-medium transition-colors bg-purple-100 text-purple-900 border-purple-300 dark:bg-purple-950/60 dark:text-purple-200 dark:border-purple-800 ${sizeClasses} ${className}`}
        data-testid="badge-admin"
      >
        <ShieldCheck size={size === 'sm' ? 12 : 14} aria-hidden="true" className="shrink-0" />
        <span>Admin</span>
      </span>
    );
  }

  const dept = department || 'General';
  let bg = 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800/80 dark:text-slate-200 dark:border-slate-700';
  let Icon = Building2;

  switch (dept.toLowerCase()) {
    case 'hr':
      bg = 'bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-800';
      Icon = Users;
      break;
    case 'finance':
      bg = 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800';
      Icon = Calculator;
      break;
    case 'engineering':
      bg = 'bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-950/60 dark:text-blue-200 dark:border-blue-800';
      Icon = Code2;
      break;
    case 'sales':
      bg = 'bg-orange-100 text-orange-900 border-orange-300 dark:bg-orange-950/60 dark:text-orange-200 dark:border-orange-800';
      Icon = Briefcase;
      break;
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';
  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-badge border font-medium transition-colors ${bg} ${sizeClasses} ${className}`}
      data-testid={`badge-dept-${dept.toLowerCase()}`}
    >
      <Icon size={iconSize} aria-hidden="true" className="shrink-0" />
      <span>{dept}</span>
    </span>
  );
};
