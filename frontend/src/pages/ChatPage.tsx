import React, { useState, useRef, useEffect, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import { CitationItem } from '../api/types';
import { Composer } from '../components/Composer';
import { EmptyState } from '../components/EmptyState';
import { MessageList, ChatMessage } from '../components/MessageList';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { PlusCircle } from 'lucide-react';

const TIMEOUT_SECONDS = 130;

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>('');
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerIntervalRef = useRef<number | null>(null);
  const timeoutIdRef = useRef<number | null>(null);

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

  useEffect(() => {
    return () => {
      clearTimers();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [clearTimers]);

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
      const response = await api.ask({ question: q, top_k: 5 }, controller.signal);
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

  const handleNewChat = () => {
    handleStop();
    setMessages([]);
    setSelectedCitation(null);
    setErrorMessage(null);
  };

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      {/* Conversation column (max width 760px, centred) */}
      <div className="flex flex-1 flex-col h-full overflow-hidden items-center">
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
        <div className="w-full max-w-[760px] p-4 bg-background shrink-0">
          <Composer
            value={inputQuestion}
            onChange={setInputQuestion}
            onSend={() => handleSendQuestion(inputQuestion)}
            onStop={handleStop}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Citation Slide-over Panel (400px on desktop) */}
      {selectedCitation && (
        <CitationPanel
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
