import React from 'react';
import { ShieldCheck, ArrowUpRight, HelpCircle, FileText, FileSearch, UserCheck } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

interface EmptyStateProps {
  onSelectQuestion: (question: string) => void;
}

export const EXAMPLE_QUESTIONS = [
  {
    title: 'Leave Policy',
    question: 'How many paid leaves do employees get?',
    icon: HelpCircle,
    category: 'HR Policies',
  },
  {
    title: 'Travel Limits',
    question: 'What does the travel policy say about hotel limits?',
    icon: FileText,
    category: 'Finance / Travel',
  },
  {
    title: 'Uploaded Document',
    question: 'Summarise the document I uploaded',
    icon: FileSearch,
    category: 'My Documents',
  },
  {
    title: 'Personal Record',
    question: 'What is my phone number on record?',
    icon: UserCheck,
    category: 'Personal Records',
  },
];

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectQuestion }) => {
  const { user } = useAuth();
  const firstName = user?.name ? user.name.split(' ')[0] : 'there';

  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 text-center max-w-2xl mx-auto animate-in fade-in duration-200">
      {/* Shield Icon */}
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-accent text-accent-contrast mb-5 shadow-xs">
        <ShieldCheck size={32} aria-hidden="true" />
      </div>

      <h2 className="text-2xl sm:text-3xl font-bold text-text tracking-tight">
        Hi {firstName}
      </h2>
      <p className="mt-2 text-sm text-text-muted max-w-md leading-relaxed">
        Ask about policies, contracts and records you have access to
      </p>

      {/* 2x2 Grid of Clickable Suggestion Cards */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3.5 w-full text-left">
        {EXAMPLE_QUESTIONS.map((ex, idx) => {
          const Icon = ex.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectQuestion(ex.question)}
              className="group flex flex-col justify-between rounded-card border border-border bg-surface p-4 transition-all duration-150 hover:-translate-y-0.5 hover:border-accent hover:shadow-md hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-focus-ring outline-none"
              data-testid={`example-question-${idx}`}
            >
              <div>
                <div className="flex items-center justify-between text-xs text-text-muted mb-2">
                  <span className="font-semibold flex items-center gap-1.5 text-primary">
                    <Icon size={14} className="text-accent" aria-hidden="true" />
                    {ex.category}
                  </span>
                  <ArrowUpRight
                    size={15}
                    className="opacity-0 transition-opacity group-hover:opacity-100 text-accent"
                    aria-hidden="true"
                  />
                </div>
                <div className="text-sm font-medium text-text group-hover:text-primary transition-colors line-clamp-2 leading-snug">
                  {ex.question}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
