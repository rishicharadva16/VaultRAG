import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, FileCheck, Lock, Upload, Search, Folder } from 'lucide-react';

interface EmptyStateProps {
  onSelectQuestion?: (question: string) => void;
}

const QUICK_ACTIONS = [
  {
    title: 'Upload a document',
    hint: 'PDF, image, CSV or text',
    icon: Upload,
    path: '/documents',
  },
  {
    title: 'Search documents',
    hint: 'Find passages without a full answer',
    icon: Search,
    path: '/search',
  },
  {
    title: 'My documents',
    hint: 'Manage and share your uploads',
    icon: Folder,
    path: '/documents',
  },
];

export const EmptyState: React.FC<EmptyStateProps> = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center py-4 px-2 sm:px-4 text-center max-w-2xl mx-auto w-full">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-raised border border-border text-accent mb-3 shadow-xs">
        <ShieldCheck size={22} aria-hidden="true" />
      </div>

      <h1 className="text-lg sm:text-xl font-bold text-text tracking-tight">
        VaultRAG Knowledge Assistant
      </h1>
      <p className="mt-1 text-xs sm:text-sm text-text-muted max-w-md leading-relaxed">
        Answers are verified and grounded strictly in documents you are permitted to see.
      </p>

      {/* 3 Compact Quick-Action Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 w-full mt-5">
        {QUICK_ACTIONS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => navigate(item.path)}
              className="group flex items-center gap-3 h-[56px] min-h-[56px] px-3 py-2 rounded-xl border border-border bg-surface hover:border-accent hover:shadow-xs hover:-translate-y-0.5 active:translate-y-0 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer text-left w-full"
            >
              <div className="h-8 w-8 rounded-lg bg-accent/10 text-accent flex items-center justify-center shrink-0 group-hover:bg-accent/20 transition-colors">
                <Icon size={16} aria-hidden="true" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="font-semibold text-xs sm:text-sm text-text truncate leading-tight">
                  {item.title}
                </span>
                <span className="text-[11px] text-text-muted truncate leading-tight mt-0.5">
                  {item.hint}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Security and Grounding Trust Chips */}
      <div className="flex flex-wrap items-center justify-center gap-2 mt-5 pt-4 border-t border-border-subtle/50 w-full max-w-xl text-xs text-text-muted">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-raised border border-border text-[11px]">
          <ShieldCheck size={13} className="text-accent shrink-0" aria-hidden="true" />
          <span>Access enforced at retrieval</span>
        </div>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-raised border border-border text-[11px]">
          <FileCheck size={13} className="text-accent shrink-0" aria-hidden="true" />
          <span>Every answer cited</span>
        </div>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-surface-raised border border-border text-[11px]">
          <Lock size={13} className="text-accent shrink-0" aria-hidden="true" />
          <span>Private by design</span>
        </div>
      </div>
    </div>
  );
};


