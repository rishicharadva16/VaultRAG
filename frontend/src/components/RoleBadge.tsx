import React from 'react';
import { Role } from '../api/types';
import { DepartmentBadge } from './DepartmentBadge';

interface RoleBadgeProps {
  role?: Role;
  department?: string | null;
  isAdmin?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({
  role,
  department,
  isAdmin: propIsAdmin,
  className = '',
  size = 'sm',
}) => {
  const isAdmin = propIsAdmin || role === 'admin';
  const dept = department || (role === 'hr_admin' ? 'HR' : role === 'finance_admin' ? 'Finance' : undefined);
  return (
    <DepartmentBadge
      department={dept}
      isAdmin={isAdmin}
      className={className}
      size={size}
    />
  );
};

