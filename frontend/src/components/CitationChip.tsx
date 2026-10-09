import React, { useState } from 'react';
import { CitationItem } from '../api/types';
import { formatSourceLabel } from '../lib/format';
import { FileText, Database } from 'lucide-react';

interface CitationChipProps {
  citation: CitationItem;
  onClick: (citation: CitationItem) => void;
  variant?: 'marker' | 'source';
  isSelected?: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  citation,
  onClick,
  variant = 'marker',
  isSelected = false,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    onClick(citation);
  };

  const isDb = Boolean(citation.row_id || citation.file.endsWith('table') || citation.chunk_id.startsWith('db:'));

  if (variant === 'marker') {
    return (
      <span className="relative inline-block align-baseline mx-0.5">
        <button
          type="button"
          onClick={handleClick}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          onFocus={() => setShowTooltip(true)}
          onBlur={() => setShowTooltip(false)}
          aria-label={`Citation [${citation.id}]: ${citation.file}`}
          className={`inline-flex items-center justify-center font-mono text-xs px-1.5 py-0.5 rounded-btn font-semibold transition-all border ${
            isSelected
              ? 'bg-accent text-accent-contrast border-accent shadow-xs scale-105'
              : 'bg-surface text-accent border-border hover:bg-surface-raised hover:border-accent hover:text-accent-hover'
          }`}
          data-testid={`citation-marker-${citation.id}`}
        >
          [{citation.id}]
        </button>

        {showTooltip && citation.snippet && (
          <span
            role="tooltip"
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-30 w-64 rounded-card border border-border bg-surface p-2.5 text-xs text-text shadow-raised transition-opacity pointer-events-none"
          >
            <span className="block font-medium text-text-muted mb-1 truncate">
              {formatSourceLabel(citation.file, citation.page, citation.row_id)}
            </span>
            <span className="block line-clamp-3 text-text font-normal leading-relaxed">
              "{citation.snippet}"
            </span>
          </span>
        )}
      </span>
    );
  }

  // variant === 'source'
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
        aria-label={`Open citation ${citation.id} from ${citation.file}`}
        className={`flex items-center gap-1.5 rounded-btn border px-2.5 py-1 text-xs font-medium transition-colors ${
          isSelected
            ? 'bg-accent text-accent-contrast border-accent'
            : 'bg-surface text-text border-border hover:bg-surface-raised hover:border-accent'
        }`}
        data-testid={`citation-source-${citation.id}`}
      >
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-surface-raised font-mono text-[10px] text-text-muted">
          {citation.id}
        </span>
        {isDb ? (
          <Database size={13} className="shrink-0 text-text-muted" aria-hidden="true" />
        ) : (
          <FileText size={13} className="shrink-0 text-text-muted" aria-hidden="true" />
        )}
        <span className="truncate max-w-[180px]">
          {formatSourceLabel(citation.file, citation.page, citation.row_id)}
        </span>
      </button>

      {showTooltip && citation.snippet && (
        <div
          role="tooltip"
          className="absolute bottom-full left-0 mb-1.5 z-30 w-72 rounded-card border border-border bg-surface p-2.5 text-xs text-text shadow-raised transition-opacity pointer-events-none"
        >
          <div className="font-medium text-text-muted mb-1 truncate">
            {formatSourceLabel(citation.file, citation.page, citation.row_id)}
          </div>
          <div className="line-clamp-4 text-text leading-relaxed">"{citation.snippet}"</div>
        </div>
      )}
    </div>
  );
};
