import React from 'react';
import { Shield } from 'lucide-react';

interface RefusalNoticeProps {
  answer: string;
  className?: string;
}

export const RefusalNotice: React.FC<RefusalNoticeProps> = ({ answer, className = '' }) => {
  return (
    <div
      className={`rounded-card border border-border bg-surface-2 p-4 sm:p-5 shadow-xs transition-colors ${className}`}
      data-testid="refusal-notice"
    >
      <div className="flex items-start gap-3.5">
        <div className="mt-0.5 rounded-xl p-2 bg-surface text-primary border border-border shadow-xs shrink-0">
          <Shield size={18} aria-hidden="true" />
        </div>
        <div className="space-y-1.5 flex-1 min-w-0">
          <p className="text-sm font-medium text-text leading-relaxed whitespace-pre-wrap">{answer}</p>
          <p className="text-xs text-text-muted">
            Answers come only from documents available to you.
          </p>
        </div>
      </div>
    </div>
  );
};
