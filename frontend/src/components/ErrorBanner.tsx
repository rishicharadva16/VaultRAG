import React from 'react';
import { AlertCircle, RotateCcw, X } from 'lucide-react';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  onRetry,
  onDismiss,
  className = '',
}) => {
  return (
    <div
      role="alert"
      className={`flex items-start justify-between gap-3 rounded-card border border-red-300 bg-red-50 p-3.5 text-sm text-red-900 shadow-sm dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200 ${className}`}
      data-testid="error-banner"
    >
      <div className="flex items-start gap-2.5">
        <AlertCircle size={18} className="shrink-0 text-danger mt-0.5" aria-hidden="true" />
        <div className="font-normal leading-relaxed">{message}</div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 rounded-btn bg-surface px-2.5 py-1 text-xs font-medium text-danger border border-red-200 shadow-xs hover:bg-surface-raised dark:border-red-800 dark:bg-surface-raised"
          >
            <RotateCcw size={12} aria-hidden="true" />
            <span>Retry</span>
          </button>
        )}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss error"
            className="rounded p-1 text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900/40"
          >
            <X size={14} aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
};
