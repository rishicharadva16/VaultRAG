import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface EmptyStateProps {
  onSelectQuestion?: (question: string) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = () => {
  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 text-center max-w-2xl mx-auto">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-raised border border-border text-accent mb-4 shadow-xs">
        <ShieldCheck size={26} aria-hidden="true" />
      </div>

      <h1 className="text-xl font-bold text-text tracking-tight">VaultRAG Knowledge Assistant</h1>
      <p className="mt-2 text-sm text-text-muted max-w-md leading-relaxed">
        Answers are verified and grounded strictly in documents you are permitted to see.
      </p>
    </div>
  );
};
