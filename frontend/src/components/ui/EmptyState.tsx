import React from 'react';

export interface EmptyStateProps {
  title: string;
  hint?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  hint,
  action,
  icon,
  className = '',
}) => {
  return (
    <div
      className={`rounded-card border border-border bg-surface p-8 sm:p-12 text-center shadow-xs ${className}`}
    >
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 border border-border text-text-muted mb-4 shadow-xs">
        {icon || (
          <svg
            className="h-7 w-7 text-text-muted/80"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect width="18" height="18" x="3" y="3" rx="4" />
            <path d="m9 9 6 6m0-6-6 6" />
          </svg>
        )}
      </div>

      <h3 className="font-heading text-base sm:text-lg font-semibold text-text mb-1.5">
        {title}
      </h3>

      {hint && (
        <p className="text-xs sm:text-sm text-text-muted max-w-md mx-auto leading-relaxed mb-5">
          {hint}
        </p>
      )}

      {action && <div className="flex justify-center">{action}</div>}
    </div>
  );
};
