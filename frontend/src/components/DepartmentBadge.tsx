import React from 'react';
import { Badge, DepartmentType } from './ui/Badge';

export interface DepartmentBadgeProps {
  department?: DepartmentType | null;
  isAdmin?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export const DepartmentBadge: React.FC<DepartmentBadgeProps> = (props) => {
  return <Badge {...props} />;
};
