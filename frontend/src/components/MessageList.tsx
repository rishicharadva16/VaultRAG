import React, { useEffect, useRef } from 'react';
import { AskResponse, CitationItem } from '../api/types';
import { AnswerCard } from './AnswerCard';
import { RefusalNotice } from './RefusalNotice';
import { Skeleton } from './Skeleton';
import { Bot } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

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
  const { user } = useAuth();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, elapsedSeconds]);

  const getInitials = (name?: string) => {
    if (!name) return 'U';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  };

  const userInitials = getInitials(user?.name);

  const formatTime = (date?: Date) => {
    if (!date) return '';
    try {
      const d = new Date(date);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return '';
    }
  };

  return (
    <div className={`space-y-6 pb-4 ${className}`} aria-live="polite">
      {messages.map((msg) => (
        <div key={msg.id} className="space-y-4">
          {/* User Question */}
          <div className="flex items-start gap-2.5 sm:gap-3 justify-end">
            <div className="flex flex-col items-end max-w-[85%] sm:max-w-[75%] space-y-1">
              <div className="rounded-2xl rounded-tr-xs bg-accent px-4 py-3 text-sm text-white shadow-xs">
                <p className="leading-relaxed whitespace-pre-wrap font-medium">{msg.question}</p>
              </div>
              <span className="text-[11px] text-text-muted px-1">
                {formatTime(msg.timestamp)}
              </span>
            </div>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-accent-contrast text-xs font-semibold shadow-xs select-none">
              {userInitials}
            </div>
          </div>

          {/* AI Response or Loading State */}
          <div className="flex items-start gap-2.5 sm:gap-3 justify-start">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent/10 border border-accent/20 text-accent">
              <Bot size={17} aria-hidden="true" />
            </div>

            <div className="max-w-[90%] sm:max-w-[85%] flex-1 flex flex-col space-y-1">
              {msg.isLoading ? (
                /* Loading State with Elapsed Timer and Animated Typing Dots */
                <div
                  className="rounded-2xl border border-border bg-surface p-4 space-y-3.5 shadow-sm"
                  data-testid="searching-skeleton"
                >
                  <div className="flex items-center justify-between text-xs font-medium text-text-muted">
                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-accent animate-bounce [animation-delay:-0.3s]" />
                        <span className="h-1.5 w-1.5 rounded-full bg-accent animate-bounce [animation-delay:-0.15s]" />
                        <span className="h-1.5 w-1.5 rounded-full bg-accent animate-bounce" />
                      </span>
                      <span className="font-medium text-text">Searching your documents...</span>
                    </div>
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

              {!msg.isLoading && (
                <span className="text-[11px] text-text-muted px-1">
                  {formatTime(msg.timestamp)}
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
};

