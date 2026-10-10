import React, { useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Composer } from '../components/Composer';
import { EmptyState } from '../components/EmptyState';
import { MessageList } from '../components/MessageList';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { useChat } from '../chat/ChatContext';
import { PlusCircle, X } from 'lucide-react';

export const ChatPage: React.FC = () => {
  const {
    messages,
    selectedCitation,
    setSelectedCitation,
    inputQuestion,
    setInputQuestion,
    isLoading,
    elapsedSeconds,
    errorMessage,
    setErrorMessage,
    lastQuestion,
    sourceFilter,
    setSourceFilter,
    handleSendQuestion,
    handleStop,
    handleRetry,
    handleNewChat,
  } = useChat();

  const location = useLocation();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Update source filter if location state changes
  useEffect(() => {
    const state = location.state as { source_ids?: string[]; source_filename?: string } | undefined;
    if (state?.source_ids && state.source_ids.length > 0 && state.source_filename) {
      setSourceFilter({
        source_ids: state.source_ids,
        filename: state.source_filename,
      });
    }
  }, [location.state, setSourceFilter]);

  // Scroll to bottom on initial mount and when messages change
  useEffect(() => {
    if (scrollContainerRef.current && messages.length > 0) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (scrollContainerRef.current && messages.length > 0) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, []);

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
        <div ref={scrollContainerRef} className="flex-1 w-full max-w-[760px] overflow-y-auto px-4 py-6">
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
          <div ref={messagesEndRef} />
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

      {/* Citation Slide-over Panel (400px on desktop) */}
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
