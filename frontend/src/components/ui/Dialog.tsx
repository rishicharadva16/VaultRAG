import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string | React.ReactNode;
  description?: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  showCloseButton?: boolean;
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  maxWidth = 'md',
  showCloseButton = true,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
  }[maxWidth];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 overflow-y-auto"
      role="dialog"
      aria-modal="true"
    >
      {/* Blurred Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-md transition-opacity duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Content modal */}
      <div
        ref={dialogRef}
        className={`relative z-10 w-full ${maxWidthClasses} flex flex-col h-full sm:h-auto rounded-none sm:rounded-card border-0 sm:border border-border bg-surface p-6 shadow-panel animate-in fade-in zoom-in-95 duration-150 overflow-y-auto`}
      >
        {(title || showCloseButton) && (
          <div className="flex items-start justify-between border-b border-border pb-4 mb-5">
            <div>
              {title && (
                <h2 className="font-heading text-lg font-bold text-text">
                  {title}
                </h2>
              )}
              {description && (
                <p className="mt-1 text-xs text-text-muted">{description}</p>
              )}
            </div>
            {showCloseButton && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                className="rounded-btn p-1.5 text-text-muted hover:bg-surface-2 hover:text-text transition-colors min-h-[40px] min-w-[40px] flex items-center justify-center ml-2 shrink-0"
              >
                <X size={18} aria-hidden="true" />
              </button>
            )}
          </div>
        )}

        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
};
