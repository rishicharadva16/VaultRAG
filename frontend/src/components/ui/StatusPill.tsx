import React from 'react';
import { CheckCircle2, Loader2, XCircle, Clock, AlertTriangle } from 'lucide-react';

export type StatusPillType = 'ready' | 'processing' | 'queued' | 'failed' | 'active' | 'inactive';

export interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusPillType;
  label?: string;
  reasonCode?: string | null;
  testId?: string;
  className?: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({
  status,
  label,
  reasonCode,
  testId,
  className = '',
  ...rest
}) => {
  const tid = testId || ((rest as Record<string, unknown>)['data-testid'] as string | undefined);
  const norm = (status || '').toLowerCase();

  switch (norm) {
    case 'ready':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 ${className}`}
          {...rest}
        >
          <CheckCircle2 size={13} className="shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>{label || 'Ready'}</span>
        </span>
      );

    case 'processing':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-300 ${className}`}
          {...rest}
        >
          <Loader2 size={13} className="animate-spin shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          <span>{label || 'Processing'}</span>
        </span>
      );

    case 'queued':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 text-xs font-semibold text-blue-700 dark:text-blue-300 ${className}`}
          {...rest}
        >
          <Clock size={13} className="shrink-0 text-blue-600 dark:text-blue-400" aria-hidden="true" />
          <span>{label || 'Queued'}</span>
        </span>
      );

    case 'failed':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-rose-500/10 border border-rose-500/20 px-2.5 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-300 ${className}`}
          title={reasonCode ? `Reason: ${reasonCode}` : undefined}
          {...rest}
        >
          <AlertTriangle size={13} className="shrink-0 text-rose-600 dark:text-rose-400" aria-hidden="true" />
          <span>{label || 'Failed'}</span>
        </span>
      );

    case 'active':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300 ${className}`}
          {...rest}
        >
          <CheckCircle2 size={13} className="shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>{label || 'Active'}</span>
        </span>
      );

    case 'inactive':
      return (
        <span
          data-testid={tid}
          className={`inline-flex items-center gap-1.5 rounded-badge bg-slate-500/10 border border-slate-500/20 px-2.5 py-0.5 text-xs font-semibold text-slate-600 dark:text-slate-400 ${className}`}
          {...rest}
        >
          <XCircle size={13} className="shrink-0 text-slate-500 dark:text-slate-400" aria-hidden="true" />
          <span>{label || 'Inactive'}</span>
        </span>
      );

    default:
      return null;
  }
};
