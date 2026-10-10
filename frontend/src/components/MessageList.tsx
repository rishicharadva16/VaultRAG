import React, { useEffect, useRef } from 'react';
import { AskResponse, CitationItem } from '../api/types';
import { AnswerCard } from './AnswerCard';
import { RefusalNotice } from './RefusalNotice';
import { Skeleton } from './ui/Skeleton';
import { User, ShieldCheck } from 'lucide-react';

export interface ChatMessage {
  id: string;
  question: string;
  response?: AskResponse;
  isLoading?: boolean;
  error?: string;
  latencyMs?: number;
  timestamp: Date;
}

interface MessageListProps {
  messages: ChatMessage[];
  elapsedSeconds?: number;
  selectedCitationId?: number | null;
  onSelectCitation: (citation: CitationItem) => void;
  className?: string;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  elapsedSeconds = 0,
  selectedCitationId,
  onSelectCitation,
  className = '',
}) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, elapsedSeconds]);

  return (
    <div className={`space-y-6 pb-4 ${className}`} aria-live="polite">
      {messages.map((msg) => (
        <div key={msg.id} className="space-y-4">
          {/* User Question: Right-aligned indigo gradient bubble */}
          <div className="flex items-start gap-3 justify-end animate-in fade-in duration-150">
            <div className="max-w-[85%] sm:max-w-[75%] rounded-card bg-gradient-to-r from-primary to-indigo-600 p-4 text-sm text-white shadow-sm">
              <p className="leading-relaxed whitespace-pre-wrap font-medium">{msg.question}</p>
            </div>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-primary to-accent text-white shadow-xs">
              <User size={16} aria-hidden="true" />
            </div>
          </div>

          {/* AI Response or Waiting State */}
          <div className="flex items-start gap-3 justify-start animate-in fade-in duration-200">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-2 border border-border text-primary shadow-xs">
              <ShieldCheck size={20} aria-hidden="true" />
            </div>

            <div className="max-w-[92%] sm:max-w-[88%] flex-1">
              {msg.isLoading ? (
                /* Assistant Waiting Card with Animated Typing Dots */
                <div
                  className="rounded-card border border-border bg-surface p-5 space-y-4 shadow-soft"
                  data-testid="searching-skeleton"
                >
                  <div className="flex items-center justify-between text-xs font-semibold text-text-muted">
                    <div className="flex items-center gap-2.5">
                      {/* Animated Typing Dots */}
                      <div className="flex items-center gap-1 h-3">
                        <span className="h-2 w-2 rounded-full bg-primary typing-dot-1" />
                        <span className="h-2 w-2 rounded-full bg-accent typing-dot-2" />
                        <span className="h-2 w-2 rounded-full bg-primary typing-dot-3" />
                      </div>
                      <span className="text-text font-medium">
                        {elapsedSeconds >= 8
                          ? 'Writing the answer...'
                          : 'Searching your documents...'}
                      </span>
                    </div>

                    <span className="font-mono text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded-btn border border-border">
                      {elapsedSeconds}s elapsed
                    </span>
                  </div>

                  <div className="space-y-2.5 pt-1">
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-2/3" />
                  </div>
                </div>
              ) : msg.response ? (
                msg.response.refused ? (
                  /* Refusal Notice */
                  <RefusalNotice answer={msg.response.answer} />
                ) : (
                  /* Grounded Answer Card */
                  <AnswerCard
                    response={msg.response}
                    latencyMs={msg.latencyMs}
                    selectedCitationId={selectedCitationId}
                    onSelectCitation={onSelectCitation}
                  />
                )
              ) : null}
            </div>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
};
