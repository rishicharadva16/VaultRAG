import React, { useEffect, useRef } from 'react';
import { AskResponse, CitationItem } from '../api/types';
import { AnswerCard } from './AnswerCard';
import { RefusalNotice } from './RefusalNotice';
import { Skeleton } from './Skeleton';
import { User, Bot, Loader2 } from 'lucide-react';

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
          {/* User Question */}
          <div className="flex items-start gap-3 justify-end">
            <div className="max-w-[85%] sm:max-w-[75%] rounded-card bg-surface-raised border border-border p-3.5 text-sm text-text shadow-xs">
              <p className="leading-relaxed whitespace-pre-wrap font-medium">{msg.question}</p>
            </div>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-accent-contrast">
              <User size={16} aria-hidden="true" />
            </div>
          </div>

          {/* AI Response or Loading State */}
          <div className="flex items-start gap-3 justify-start">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-raised border border-border text-text">
              <Bot size={16} aria-hidden="true" />
            </div>

            <div className="max-w-[90%] sm:max-w-[85%] flex-1">
              {msg.isLoading ? (
                /* Loading State with Elapsed Timer */
                <div
                  className="rounded-card border border-border bg-surface p-4 space-y-3 shadow-xs"
                  data-testid="searching-skeleton"
                >
                  <div className="flex items-center justify-between text-xs font-medium text-text-muted">
                    <span className="flex items-center gap-2">
                      <Loader2 size={14} className="animate-spin text-accent" />
                      <span>Searching your documents...</span>
                    </span>
                    <span className="font-mono text-xs text-text-muted">
                      {elapsedSeconds}s elapsed
                    </span>
                  </div>
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ) : msg.response ? (
                msg.response.refused ? (
                  /* Refusal State */
                  <RefusalNotice answer={msg.response.answer} />
                ) : (
                  /* Verified Grounded Answer */
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
