import React, { useRef, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Composer } from '../components/Composer';
import { EmptyState } from '../components/EmptyState';
import { MessageList } from '../components/MessageList';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { useChat } from '../chat/ChatContext';
import { MessageSquare, Globe, FileText, X, Plus, ArrowDown } from 'lucide-react';

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
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Update source filter if location state changes
  useEffect(() => {
    const state = location.state as {
      source_ids?: string[];
      source_filename?: string;
      auto_send_question?: string;
    } | undefined;
    if (state?.source_ids && state.source_ids.length > 0 && state.source_filename) {
      setSourceFilter({
        source_ids: state.source_ids,
        filename: state.source_filename,
      });
    }
    if (state?.auto_send_question) {
      const q = state.auto_send_question;
      window.history.replaceState({}, document.title);
      handleSendQuestion(q);
    }
  }, [location.state, setSourceFilter, handleSendQuestion]);

  // Scroll to bottom on initial mount and when messages change
  useEffect(() => {
    if (scrollContainerRef.current && messages.length > 0) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    setShowScrollBottom(distanceFromBottom > 150);
  };

  const scrollToBottom = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
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
        {/* Header Bar: 64px high, surface bg, bottom border, subtle shadow */}
        <header className="w-full h-16 shrink-0 bg-surface border-b border-border shadow-xs px-4 sm:px-6 flex items-center justify-between gap-3 z-10">
          {/* Left: 36px icon tile + Title + Subtitle */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="h-9 w-9 rounded-xl bg-accent/10 text-accent flex items-center justify-center shrink-0">
              <MessageSquare size={18} aria-hidden="true" />
            </div>
            <div className="flex flex-col min-w-0">
              <h1 className="text-sm sm:text-base font-semibold text-text leading-tight truncate">
                Chat Assistant
              </h1>
              <p className="text-[11px] sm:text-xs text-text-muted leading-tight truncate hidden sm:block">
                Answers come only from documents you can access
              </p>
            </div>
          </div>

          {/* Center / Scope Chip (hidden below md) */}
          <div className="hidden md:flex items-center justify-center shrink-0">
            {sourceFilter ? (
              <div
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-xs text-accent font-medium max-w-[280px]"
                role="status"
                aria-live="polite"
                data-testid="source-filter-chip"
              >
                <FileText size={13} className="shrink-0" aria-hidden="true" />
                <span className="truncate">
                  Limited to: <strong className="font-semibold">{sourceFilter.filename}</strong>
                </span>
                <button
                  type="button"
                  onClick={() => setSourceFilter(null)}
                  className="p-0.5 rounded-full hover:bg-accent/20 transition-colors shrink-0 cursor-pointer"
                  aria-label="Remove document filter"
                  data-testid="remove-source-filter-button"
                >
                  <X size={12} aria-hidden="true" />
                </button>
              </div>
            ) : (
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-raised border border-border text-xs text-text-muted font-medium">
                <Globe size={13} className="shrink-0 text-text-muted/80" aria-hidden="true" />
                <span>Searching all documents you can access</span>
              </div>
            )}
          </div>

          {/* Right: Green dot pill + Message count + New chat button */}
          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            {/* Access control active */}
            <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs font-medium text-emerald-600 dark:text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
              <span>Access control active</span>
            </div>

            {/* Message counter chip */}
            {messages.length > 0 && (
              <span className="hidden sm:inline-block text-xs font-medium text-text-muted bg-surface-raised border border-border px-2.5 py-1 rounded-full">
                {messages.length} {messages.length === 1 ? 'message' : 'messages'}
              </span>
            )}

            {/* New chat button: Outlined style, 40px high, 12px radius, 1.5px border */}
            <button
              type="button"
              onClick={handleNewChat}
              className="flex items-center justify-center gap-1.5 h-10 min-h-[40px] px-3 sm:px-4 rounded-xl border-[1.5px] border-accent text-accent font-semibold text-xs hover:bg-accent/10 active:bg-accent/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent transition-colors shrink-0 cursor-pointer"
              aria-label="New chat"
              data-testid="new-chat-button"
            >
              <Plus size={16} strokeWidth={2.2} aria-hidden="true" />
              <span className="hidden sm:inline">New chat</span>
            </button>
          </div>
        </header>

        {/* Scrollable Messages Area: FULL WIDTH of chat area (scrollbar at far right edge) */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="flex-1 w-full overflow-y-auto overflow-x-hidden relative chat-custom-scroll min-h-0"
        >
          {/* Centered content column (max-width 760px) */}
          <div className="w-full max-w-[760px] mx-auto px-4 py-6 min-h-full flex flex-col justify-start">
            {messages.length === 0 ? (
              <div className="flex-1 flex items-center justify-center my-auto py-4">
                <EmptyState onSelectQuestion={(q) => setInputQuestion(q)} />
              </div>
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

          {/* Floating Scroll to Latest Button */}
          {showScrollBottom && (
            <button
              type="button"
              onClick={scrollToBottom}
              aria-label="Scroll to latest messages"
              className="absolute bottom-4 right-6 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-surface border border-border text-text shadow-md hover:bg-surface-raised hover:text-accent active:scale-95 transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
            >
              <ArrowDown size={18} aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Composer fixed at bottom outside the scroll area */}
        <div className="w-full shrink-0 border-t border-border-subtle/40 bg-background py-3 px-4 flex flex-col items-center">
          <div className="w-full max-w-[760px] space-y-2">
            {/* Removable source filter chip on smaller screens */}
            {sourceFilter && (
              <div
                className="md:hidden flex items-center justify-between gap-2 px-3 py-1.5 bg-accent/10 border border-accent/30 rounded-xl text-xs text-accent font-medium shadow-xs"
                role="status"
                aria-live="polite"
              >
                <div className="flex items-center gap-1.5 min-w-0 truncate">
                  <FileText size={13} className="shrink-0" aria-hidden="true" />
                  <span className="truncate">
                    Limited to: <strong className="font-semibold">{sourceFilter.filename}</strong>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSourceFilter(null)}
                  className="p-1 rounded-full hover:bg-accent/20 transition-colors shrink-0"
                  aria-label="Remove document filter"
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

      {/* Scoped custom scrollbar style */}
      <style>{`
        .chat-custom-scroll {
          scrollbar-width: thin;
          scrollbar-color: transparent transparent;
          transition: scrollbar-color 0.2s;
        }
        .chat-custom-scroll:hover {
          scrollbar-color: var(--color-border-subtle) transparent;
        }
        .chat-custom-scroll::-webkit-scrollbar {
          width: 6px;
          height: 0px;
        }
        .chat-custom-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .chat-custom-scroll::-webkit-scrollbar-thumb {
          background-color: transparent;
          border-radius: 9999px;
          transition: background-color 0.2s;
        }
        .chat-custom-scroll:hover::-webkit-scrollbar-thumb {
          background-color: var(--color-border-subtle);
        }
        .chat-custom-scroll::-webkit-scrollbar-thumb:hover {
          background-color: var(--color-text-muted);
        }
      `}</style>
    </div>
  );
};

