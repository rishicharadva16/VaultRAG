import React, { useRef, useEffect } from 'react';
import { ArrowUp, Square, Loader2 } from 'lucide-react';

interface ComposerProps {
  value: string;
  onChange: (val: string) => void;
  onSend: () => void;
  onStop: () => void;
  isLoading: boolean;
  disabled?: boolean;
  className?: string;
}

const MAX_CHARS = 500;

export const Composer: React.FC<ComposerProps> = ({
  value,
  onChange,
  onSend,
  onStop,
  isLoading,
  disabled = false,
  className = '',
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim().length > 0 && !disabled) {
        onSend();
      }
    }
  };

  const remaining = MAX_CHARS - value.length;
  const isTooLong = remaining < 0;
  const isAtLimit = value.length >= MAX_CHARS;
  const isNearLimit = value.length >= MAX_CHARS * 0.9 && !isAtLimit;
  const isEmpty = value.trim().length === 0;

  return (
    <div
      className={`rounded-2xl border border-border bg-surface p-3.5 shadow-sm transition-all focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 ${className}`}
      data-testid="composer"
    >
      <label htmlFor="chat-composer-input" className="sr-only">
        Ask a question about your documents
      </label>
      <textarea
        id="chat-composer-input"
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX_CHARS))}
        onKeyDown={handleKeyDown}
        disabled={disabled || isLoading}
        placeholder="Ask a question about policies, contracts, or records..."
        rows={2}
        className="w-full min-h-[44px] max-h-[180px] resize-none bg-transparent text-sm text-text placeholder:text-text-muted outline-none disabled:opacity-50 font-sans leading-relaxed"
        aria-label="Ask a question about your documents"
      />

      <div className="mt-2.5 flex items-center justify-between border-t border-border-subtle pt-2.5 text-xs">
        <div className="flex items-center gap-3 text-text-muted">
          <span className="hidden sm:inline text-[11px] text-text-muted">
            Enter to send - Shift+Enter for newline
          </span>
          <span
            className={`font-mono text-[11px] transition-colors ${
              isAtLimit || isTooLong
                ? 'text-danger font-semibold'
                : isNearLimit
                ? 'text-amber-600 dark:text-amber-400 font-semibold'
                : 'text-text-muted'
            }`}
            data-testid="char-counter"
          >
            {value.length}/{MAX_CHARS}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isLoading && (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating answer"
              className="flex items-center gap-1.5 rounded-btn bg-danger px-3 py-1.5 font-semibold text-xs text-white shadow-xs hover:bg-danger/90 transition-colors min-h-[40px]"
              data-testid="stop-button"
            >
              <Square size={13} className="fill-current" />
              <span>Stop</span>
            </button>
          )}

          <button
            type="button"
            onClick={onSend}
            disabled={isEmpty || isTooLong || disabled || isLoading}
            aria-label={isLoading ? 'Sending question...' : 'Send question'}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent hover:bg-accent-hover text-accent-contrast shadow-xs disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-accent shrink-0"
            data-testid="send-button"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin text-accent-contrast" aria-hidden="true" />
            ) : (
              <ArrowUp size={18} strokeWidth={2.5} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

