import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Card } from '../components/ui';

export const NotFoundPage: React.FC = () => {
  return (
    <div
      className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center animate-in fade-in duration-200"
      data-testid="not-found-page"
    >
      <Card className="max-w-md w-full p-8 flex flex-col items-center text-center shadow-soft border-border">
        {/* Inline SVG Illustration */}
        <div className="relative mb-6 flex items-center justify-center">
          <svg
            className="relative h-24 w-24 text-accent"
            viewBox="0 0 120 120"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            {/* Outer shield */}
            <path
              d="M60 14L24 28V58C24 81 39.5 101.5 60 108C80.5 101.5 96 81 96 58V28L60 14Z"
              className="fill-accent/10 stroke-accent/40"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
            {/* Inner vault lock circle */}
            <circle
              cx="60"
              cy="60"
              r="22"
              className="fill-surface-2 stroke-accent"
              strokeWidth="2"
            />
            {/* Keyhole / question symbol */}
            <path
              d="M56 52C56 49.8 57.8 48 60 48C62.2 48 64 49.8 64 52C64 54 62.5 55.5 61 56.8C59.8 57.8 59 59.2 59 61V63"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <circle cx="59.5" cy="69.5" r="1.5" fill="currentColor" />
          </svg>
        </div>

        <h1 className="text-2xl font-bold tracking-tight text-text">
          Page not found
        </h1>
        <p className="mt-2 text-sm text-text-muted leading-relaxed max-w-sm">
          The page you are looking for does not exist or has been moved.
        </p>

        <Link
          to="/chat"
          className="mt-6 inline-flex items-center justify-center gap-2 rounded-btn bg-accent hover:bg-accent-hover text-accent-contrast px-5 py-2.5 text-sm font-semibold shadow-xs transition-colors focus-visible:ring-2 focus-visible:ring-focus-ring outline-hidden"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          <span>Back to Chat</span>
        </Link>
      </Card>
    </div>
  );
};

