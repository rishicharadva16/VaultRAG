import React from 'react';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '', ...props }) => {
  return (
    <div
      className={`animate-shimmer rounded-btn bg-surface-2 ${className}`}
      aria-hidden="true"
      {...props}
    />
  );
};
