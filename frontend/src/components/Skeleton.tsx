import React from 'react';
import { Skeleton as UiSkeleton, SkeletonProps } from './ui/Skeleton';

export const Skeleton: React.FC<SkeletonProps> = (props) => {
  return <UiSkeleton {...props} />;
};
