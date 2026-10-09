import React, { useEffect, useState } from 'react';
import { api, ApiClientError } from '../api/client';
import { CitationItem, ChunkResponse } from '../api/types';
import { formatSourceLabel } from '../lib/format';
import { HighlightedText } from './HighlightedText';
import { Skeleton } from './Skeleton';
import { X, Quote, AlertCircle, FileText, Database } from 'lucide-react';

interface CitationPanelProps {
  citation: CitationItem | null;
  onClose: () => void;
}

// In-memory session cache for full chunk texts
const chunkCache = new Map<string, ChunkResponse>();

export const CitationPanel: React.FC<CitationPanelProps> = ({ citation, onClose }) => {
  const [chunkData, setChunkData] = useState<ChunkResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Esc closes the panel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!citation) {
      setChunkData(null);
      setError(null);
      return;
    }

    const chunkId = citation.chunk_id;
    if (chunkCache.has(chunkId)) {
      setChunkData(chunkCache.get(chunkId)!);
      setError(null);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    api
      .getCitation(chunkId, controller.signal)
      .then((res) => {
        if (!isMounted) return;
        chunkCache.set(chunkId, res);
        setChunkData(res);
        setError(null);
      })
      .catch((err) => {
        if (!isMounted) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (err instanceof ApiClientError && err.status === 404) {
          setError('This source is no longer available.');
        } else {
          setError('This source is no longer available.');
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [citation]);

  if (!citation) return null;

  const isDb = Boolean(citation.row_id || citation.chunk_id.startsWith('db:'));

  return (
    <aside
      aria-label="Citation Details"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[400px] flex-col border-l border-border bg-surface shadow-panel transition-transform duration-200 ease-in-out lg:static lg:h-full lg:shadow-none"
      data-testid="citation-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-4 bg-surface-raised">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
            {isDb ? <Database size={14} /> : <FileText size={14} />}
            <span>Citation [{citation.id}]</span>
          </div>
          <h2 className="truncate text-sm font-semibold text-text mt-0.5" title={citation.file}>
            {formatSourceLabel(citation.file, citation.page, citation.row_id)}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close citation panel (Esc)"
          className="rounded-btn p-1.5 text-text-muted hover:bg-surface hover:text-text transition-colors"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Highlight quote preview if present */}
        {citation.highlight_text && (
          <div className="rounded-card border border-border bg-surface-raised/70 p-3.5 space-y-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider">
              <Quote size={12} className="text-accent" aria-hidden="true" />
              <span>Cited passage</span>
            </div>
            <p className="text-sm italic text-text leading-relaxed font-serif">
              "{citation.highlight_text}"
            </p>
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="space-y-3 pt-2" aria-live="polite">
            <div className="text-xs text-text-muted font-medium">Fetching verified chunk text...</div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {/* 404 or Fetch Error */}
        {!isLoading && error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-card border border-border bg-surface-raised p-4 text-sm text-text-muted"
          >
            <AlertCircle size={18} className="shrink-0 text-text-muted mt-0.5" aria-hidden="true" />
            <p className="leading-relaxed">{error}</p>
          </div>
        )}

        {/* Full Text Passage with Marks */}
        {!isLoading && !error && chunkData && (
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              Source Chunk Content
            </div>
            <div className="rounded-card border border-border bg-surface p-3.5 text-xs font-mono leading-relaxed">
              <HighlightedText
                text={chunkData.text}
                highlights={citation.highlights}
                autoScrollToFirst={true}
              />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
