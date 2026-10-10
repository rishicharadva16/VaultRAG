import React, { useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';

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
  const isEmpty = value.trim().length === 0;

  return (
    <div
      className={`rounded-card border border-border bg-surface p-3 shadow-sm transition-all focus-within:border-accent focus-within:ring-1 focus-within:ring-accent ${className}`}
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
        disabled={disabled}
        placeholder="Ask a question about policies, contracts, or records... (Enter to send, Shift+Enter for newline)"
        rows={2}
        className="w-full resize-none bg-transparent text-sm text-text placeholder:text-text-muted outline-none disabled:opacity-50 font-sans"
        aria-label="Ask a question about your documents"
      />

      <div className="mt-2 flex items-center justify-between border-t border-border-subtle pt-2 text-xs">
        <span
          className={`font-mono text-xs ${
            isTooLong ? 'text-danger font-semibold' : 'text-text-muted'
          }`}
          data-testid="char-counter"
        >
          {value.length}/{MAX_CHARS}
        </span>

        <div className="flex items-center gap-2">
          {isLoading ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating answer"
              className="flex items-center gap-1.5 rounded-btn bg-danger px-3 py-1.5 font-medium text-white shadow-xs hover:bg-red-700 transition-colors"
              data-testid="stop-button"
            >
              <Square size={14} className="fill-current" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              disabled={isEmpty || isTooLong || disabled}
              aria-label="Send question"
              className="flex items-center gap-1.5 rounded-btn bg-accent px-3 py-1.5 font-medium text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              data-testid="send-button"
            >
              <span>Send</span>
              <Send size={14} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
