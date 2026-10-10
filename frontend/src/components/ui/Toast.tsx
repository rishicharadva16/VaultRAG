import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'info';
  onClose?: () => void;
  className?: string;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'success',
  onClose,
  className = '',
}) => {
  const icon = {
    success: <CheckCircle2 size={18} className="text-emerald-500 shrink-0" aria-hidden="true" />,
    error: <AlertCircle size={18} className="text-rose-500 shrink-0" aria-hidden="true" />,
    info: <Info size={18} className="text-cyan-500 shrink-0" aria-hidden="true" />,
  }[type];

  const colors = {
    success: 'border-emerald-500/30 bg-surface text-text shadow-md',
    error: 'border-rose-500/30 bg-surface text-text shadow-md',
    info: 'border-cyan-500/30 bg-surface text-text shadow-md',
  }[type];

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-5 right-5 z-50 flex items-center gap-3 rounded-card border px-4 py-3 text-sm shadow-panel animate-in slide-in-from-bottom duration-200 ${colors} ${className}`}
    >
      {icon}
      <span className="font-medium text-xs sm:text-sm">{message}</span>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Dismiss notification"
          className="ml-2 text-text-muted hover:text-text rounded p-1 hover:bg-surface-2 transition-colors min-h-[32px] min-w-[32px] flex items-center justify-center"
        >
          <X size={15} aria-hidden="true" />
        </button>
      )}
    </div>
  );
};
