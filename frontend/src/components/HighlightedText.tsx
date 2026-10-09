import React, { useEffect, useRef } from 'react';
import { HighlightSpan } from '../api/types';
import { splitHighlightedText } from '../lib/highlight';

interface HighlightedTextProps {
  text: string;
  highlights: HighlightSpan[];
  className?: string;
  autoScrollToFirst?: boolean;
}

export const HighlightedText: React.FC<HighlightedTextProps> = ({
  text,
  highlights = [],
  className = '',
  autoScrollToFirst = true,
}) => {
  const firstHighlightRef = useRef<HTMLElement | null>(null);
  const segments = splitHighlightedText(text, highlights);

  useEffect(() => {
    if (autoScrollToFirst && firstHighlightRef.current) {
      firstHighlightRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [text, highlights, autoScrollToFirst]);

  let isFirstHighlightAssigned = false;

  return (
    <div className={`whitespace-pre-wrap leading-relaxed text-sm text-text font-normal ${className}`}>
      {segments.map((seg, idx) => {
        if (!seg.isHighlighted) {
          return <React.Fragment key={idx}>{seg.text}</React.Fragment>;
        }

        const assignRef = !isFirstHighlightAssigned;
        if (assignRef) {
          isFirstHighlightAssigned = true;
        }

        return (
          <mark
            key={idx}
            ref={assignRef ? firstHighlightRef : undefined}
            className="rounded-xs bg-highlight text-[var(--color-highlight-text)] px-0.5 py-0.5 font-medium transition-colors"
            data-testid="highlighted-mark"
          >
            {seg.text}
          </mark>
        );
      })}
    </div>
  );
};
