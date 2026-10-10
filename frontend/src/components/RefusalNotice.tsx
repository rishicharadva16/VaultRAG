import React from 'react';
import { Info } from 'lucide-react';

interface RefusalNoticeProps {
  answer: string;
  className?: string;
}

export const RefusalNotice: React.FC<RefusalNoticeProps> = ({ answer, className = '' }) => {
  return (
    <div
      className={`rounded-card border border-border bg-surface-raised p-4 transition-colors ${className}`}
      data-testid="refusal-notice"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-full p-1 bg-surface text-text-muted border border-border">
          <Info size={16} aria-hidden="true" />
        </div>
        <div className="space-y-1.5 flex-1">
          <p className="text-sm font-medium text-text leading-relaxed">{answer}</p>
          <p className="text-xs text-text-muted">
            Answers come only from documents available to you.
          </p>
        </div>
      </div>
    </div>
  );
};
