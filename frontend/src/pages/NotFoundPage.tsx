import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center"
      data-testid="not-found-page"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-raised border border-border text-text-muted mb-4 shadow-xs">
        <FileQuestion size={32} aria-hidden="true" />
      </div>
      <h1 className="text-2xl font-bold tracking-tight text-text">Page not found</h1>
      <p className="mt-2 text-sm text-text-muted max-w-sm">
        The page you are looking for does not exist or has been moved.
      </p>
      <Link
        to="/chat"
        className="mt-6 inline-flex items-center gap-2 rounded-btn bg-accent px-4 py-2 text-xs font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover transition-colors"
      >
        <ArrowLeft size={14} aria-hidden="true" />
        <span>Back to Chat</span>
      </Link>
    </div>
  );
};
