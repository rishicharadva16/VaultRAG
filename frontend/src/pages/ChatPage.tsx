import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { api, ApiClientError } from '../api/client';
import { CitationItem } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Composer } from '../components/Composer';
import { EmptyState } from '../components/EmptyState';
import { MessageList, ChatMessage } from '../components/MessageList';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { PlusCircle, X } from 'lucide-react';

const TIMEOUT_SECONDS = 130;

interface LocationState {
  source_ids?: string[];
  source_filename?: string;
}

export const ChatPage: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>('');
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  // Document filter state (when navigated via "Ask about this document")
  const [sourceFilter, setSourceFilter] = useState<{
    source_ids: string[];
    filename: string;
  } | null>(() => {
    const state = location.state as LocationState | undefined;
    if (state?.source_ids && state?.source_ids.length > 0 && state?.source_filename) {
      return {
        source_ids: state.source_ids,
        filename: state.source_filename,
      };
    }
    return null;
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerIntervalRef = useRef<number | null>(null);
  const timeoutIdRef = useRef<number | null>(null);
  const prevUserIdRef = useRef<string | null>(user?.id ?? null);

  const clearTimers = useCallback(() => {
    if (timerIntervalRef.current !== null) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (timeoutIdRef.current !== null) {
      clearTimeout(timeoutIdRef.current);
      timeoutIdRef.current = null;
    }
  }, []);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearTimers();
    setIsLoading(false);
    // Remove the loading message if aborted
    setMessages((prev) => prev.filter((m) => !m.isLoading));
  }, [clearTimers]);

  const handleNewChat = useCallback(() => {
    handleStop();
    setMessages([]);
    setSelectedCitation(null);
    setErrorMessage(null);
  }, [handleStop]);

  // Reset chat and filters when switching demo users
  useEffect(() => {
    if (user && prevUserIdRef.current !== null && prevUserIdRef.current !== user.id) {
      handleNewChat();
      setSourceFilter(null);
    }
    prevUserIdRef.current = user?.id ?? null;
  }, [user, handleNewChat]);

  // Update source filter if location state changes
  useEffect(() => {
    const state = location.state as LocationState | undefined;
    if (state?.source_ids && state?.source_ids.length > 0 && state?.source_filename) {
      setSourceFilter({
        source_ids: state.source_ids,
        filename: state.source_filename,
      });
    }
  }, [location.state]);

  useEffect(() => {
    return () => {
      clearTimers();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [clearTimers]);

  const handleSendQuestion = async (questionToSend: string) => {
    const q = questionToSend.trim();
    if (!q || isLoading) return;

    setInputQuestion('');
    setErrorMessage(null);
    setLastQuestion(q);
    setIsLoading(true);
    setElapsedSeconds(0);

    const messageId = `msg-${Date.now()}`;
    const loadingMessage: ChatMessage = {
      id: messageId,
      question: q,
      isLoading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, loadingMessage]);

    // Setup elapsed timer
    const startTime = Date.now();
    timerIntervalRef.current = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    // Setup 130s abort timeout
    const controller = new AbortController();
    abortControllerRef.current = controller;

    timeoutIdRef.current = window.setTimeout(() => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearTimers();
      setIsLoading(false);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      setErrorMessage('The AI service took too long. Please try again.');
    }, TIMEOUT_SECONDS * 1000);

    try {
      const response = await api.ask(
        {
          question: q,
          top_k: 5,
          source_ids: sourceFilter ? sourceFilter.source_ids : undefined,
        },
        controller.signal
      );
      const latencyMs = Date.now() - startTime;

      clearTimers();
      setIsLoading(false);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? {
                ...m,
                isLoading: false,
                response,
                latencyMs,
              }
            : m
        )
      );
    } catch (err: unknown) {
      clearTimers();
      setIsLoading(false);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));

      if (err instanceof DOMException && err.name === 'AbortError') {
        // Handled by stop/timeout
        return;
      }

      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Cannot reach the VaultRAG server. Is the backend running?');
      }
    }
  };

  const handleRetry = () => {
    if (lastQuestion) {
      handleSendQuestion(lastQuestion);
    }
  };

  // Find citations array from the message that contains the selected citation
  const activeMessage = messages.find((m) =>
    m.response?.citations.some(
      (c) => c.id === selectedCitation?.id && c.chunk_id === selectedCitation?.chunk_id
    )
  );
  const activeCitations = activeMessage?.response?.citations || (selectedCitation ? [selectedCitation] : []);
  const activeIndex = selectedCitation
    ? activeCitations.findIndex(
        (c) => c.id === selectedCitation.id && c.chunk_id === selectedCitation.chunk_id
      )
    : -1;

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      {/* Conversation column (max width 760px, centred) */}
      <div className="flex flex-1 flex-col h-full overflow-hidden items-center min-w-0">
        {/* Top Chat Bar with New Chat button */}
        <div className="w-full border-b border-border-subtle bg-surface px-4 py-2 flex items-center justify-between text-xs text-text-muted shrink-0">
          <span className="font-medium text-text">Session Workspace</span>
          <button
            type="button"
            onClick={handleNewChat}
            className="flex items-center gap-1.5 rounded-btn px-2.5 py-1 font-medium text-text-muted hover:bg-surface-raised hover:text-text transition-colors"
            data-testid="new-chat-button"
          >
            <PlusCircle size={14} aria-hidden="true" />
            <span>New chat</span>
          </button>
        </div>

        {/* Scrollable Messages Area */}
        <div className="flex-1 w-full max-w-[760px] overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <EmptyState onSelectQuestion={handleSendQuestion} />
          ) : (
            <MessageList
              messages={messages}
              elapsedSeconds={elapsedSeconds}
              selectedCitationId={selectedCitation?.id}
              onSelectCitation={setSelectedCitation}
            />
          )}

          {/* Inline Error Banner */}
          {errorMessage && (
            <div className="my-4">
              <ErrorBanner
                message={errorMessage}
                onRetry={lastQuestion ? handleRetry : undefined}
                onDismiss={() => setErrorMessage(null)}
              />
            </div>
          )}
        </div>

        {/* Composer fixed at bottom */}
        <div className="w-full max-w-[760px] p-4 bg-background shrink-0 space-y-2">
          {/* Removable source filter chip */}
          {sourceFilter && (
            <div
              className="flex items-center justify-between gap-2 px-3 py-1.5 bg-surface border border-accent/40 rounded-btn text-xs shadow-xs"
              role="status"
              aria-live="polite"
              data-testid="source-filter-chip"
            >
              <div className="flex items-center gap-1.5 min-w-0 truncate">
                <span className="text-text-muted shrink-0">Asking only about:</span>
                <span className="font-semibold text-accent truncate">{sourceFilter.filename}</span>
              </div>
              <button
                type="button"
                onClick={() => setSourceFilter(null)}
                className="p-1 rounded text-text-muted hover:text-text hover:bg-surface-raised transition-colors shrink-0"
                aria-label="Remove document filter"
                data-testid="remove-source-filter-button"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          )}

          <Composer
            value={inputQuestion}
            onChange={setInputQuestion}
            onSend={() => handleSendQuestion(inputQuestion)}
            onStop={handleStop}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Citation Slide-over Panel */}
      {selectedCitation && (
        <CitationPanel
          citation={selectedCitation}
          citations={activeCitations}
          currentIndex={activeIndex >= 0 ? activeIndex : 0}
          onNavigate={(cit) => setSelectedCitation(cit)}
          siblingCitations={activeCitations.filter((c) => c.id !== selectedCitation.id)}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
