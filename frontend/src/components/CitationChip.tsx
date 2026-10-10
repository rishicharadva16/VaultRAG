import React, { useState } from 'react';
import { CitationItem } from '../api/types';
import { formatSourceLabel } from '../lib/format';
import { FileTypeIcon } from './ui/FileTypeIcon';
import { Database } from 'lucide-react';

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
          className={`inline-flex items-center justify-center font-mono text-xs px-2 py-0.5 rounded-badge font-semibold transition-all border outline-none focus-visible:ring-2 focus-visible:ring-focus-ring ${
            isSelected
              ? 'bg-brand-gradient text-white border-transparent shadow-sm scale-105'
              : 'bg-primary-soft text-primary border-primary/20 hover:bg-primary/20 hover:border-primary/40'
          }`}
          data-testid={`citation-marker-${citation.id}`}
        >
          [{citation.id}]
        </button>

        {showTooltip && citation.snippet && (
          <span
            role="tooltip"
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 w-72 rounded-card border border-border bg-surface p-3 text-xs text-text shadow-panel transition-opacity pointer-events-none animate-in fade-in duration-100"
          >
            <span className="block font-semibold text-text-muted mb-1 truncate text-[11px] uppercase tracking-wider">
              {formatSourceLabel(citation.file, citation.page, citation.row_id)}
            </span>
            <span className="block line-clamp-3 text-text font-normal leading-relaxed text-xs">
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
        className={`flex items-center gap-2 rounded-btn border px-3 py-1.5 text-xs font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-focus-ring min-h-[36px] ${
          isSelected
            ? 'bg-primary-soft text-primary border-primary shadow-xs ring-1 ring-primary/40 font-semibold'
            : 'bg-surface text-text border-border hover:bg-surface-2 hover:border-border-subtle'
        }`}
        data-testid={`citation-source-${citation.id}`}
      >
        <span
          className={`flex h-4 w-4 items-center justify-center rounded-full font-mono text-[10px] font-bold ${
            isSelected ? 'bg-primary text-white' : 'bg-surface-2 text-text-muted border border-border'
          }`}
        >
          {citation.id}
        </span>
        {isDb ? (
          <Database size={14} className="shrink-0 text-cyan-600 dark:text-cyan-400" aria-hidden="true" />
        ) : (
          <FileTypeIcon kind={citation.file.split('.').pop() || 'text'} size={14} />
        )}
        <span className="truncate max-w-[160px] sm:max-w-[200px]">
          {citation.file}
        </span>
        {citation.page !== null && (
          <span className="rounded bg-surface-2 px-1.5 py-0.2 text-[10px] font-mono text-text-muted border border-border/60">
            p.{citation.page}
          </span>
        )}
      </button>

      {showTooltip && citation.snippet && (
        <div
          role="tooltip"
          className="absolute bottom-full left-0 mb-2 z-30 w-80 rounded-card border border-border bg-surface p-3 text-xs text-text shadow-panel transition-opacity pointer-events-none animate-in fade-in duration-100"
        >
          <div className="font-semibold text-text-muted mb-1 truncate text-[11px] uppercase tracking-wider">
            {formatSourceLabel(citation.file, citation.page, citation.row_id)}
          </div>
          <div className="line-clamp-4 text-text leading-relaxed text-xs">
            "{citation.snippet}"
          </div>
        </div>
      )}
    </div>
  );
};
