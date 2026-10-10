import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { api, ApiClientError } from '../api/client';
import { CitationItem, SearchResultItem, HighlightSpan } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { formatLatency, formatSourceLabel } from '../lib/format';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { PageHeader } from '../components/ui/PageHeader';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import { FileTypeIcon } from '../components/ui/FileTypeIcon';
import { HighlightedText } from '../components/HighlightedText';
import { Search, SlidersHorizontal, ExternalLink, X, Compass, Database } from 'lucide-react';

interface LocationState {
  source_ids?: string[];
  source_filename?: string;
}

export const SearchPage: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [rerank, setRerank] = useState(false);
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  // Document filter state
  const [sourceFilter, setSourceFilter] = useState<{
    source_ids: string[];
    filename: string;
  } | null>(() => {
    const state = location.state as LocationState | undefined;
    if (state?.source_ids && state?.source_ids.length > 0 && state?.source_filename) {
      return {
        source_ids: state.source_ids,
        filename: state.source_filename,
      };
    }
    return null;
  });

  const prevUserIdRef = useRef<string | null>(user?.id ?? null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut '/' to focus search input
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current && !(document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, []);

  // Reset search when user changes
  useEffect(() => {
    if (user && prevUserIdRef.current !== null && prevUserIdRef.current !== user.id) {
      setResults(null);
      setQuery('');
      setLatencyMs(null);
      setErrorMessage(null);
      setSelectedCitation(null);
      setSourceFilter(null);
    }
    prevUserIdRef.current = user?.id ?? null;
  }, [user]);

  // Update source filter if location state changes
  useEffect(() => {
    const state = location.state as LocationState | undefined;
    if (state?.source_ids && state?.source_ids.length > 0 && state?.source_filename) {
      setSourceFilter({
        source_ids: state.source_ids,
        filename: state.source_filename,
      });
    }
  }, [location.state]);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const q = query.trim();
    if (!q || isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);
    setResults(null);
    setLatencyMs(null);

    const t0 = Date.now();
    try {
      const res = await api.search({
        query: q,
        top_k: topK,
        rerank,
        source_ids: sourceFilter ? sourceFilter.source_ids : undefined,
      });
      setLatencyMs(Date.now() - t0);
      setResults(res.results);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Cannot reach the VaultRAG server. Is the backend running?');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectResult = (item: SearchResultItem, index: number) => {
    const citationItem: CitationItem = {
      id: index + 1,
      chunk_id: item.chunk_id,
      source_id: item.source_id,
      file: item.file,
      page: item.page,
      row_id: item.row_id,
      snippet: item.text.slice(0, 300),
      highlights: [],
      highlight_text: '',
    };
    setSelectedCitation(citationItem);
  };

  const citations: CitationItem[] = (results || []).map((item, idx) => ({
    id: idx + 1,
    chunk_id: item.chunk_id,
    source_id: item.source_id,
    file: item.file,
    page: item.page,
    row_id: item.row_id,
    snippet: item.text.slice(0, 300),
    highlights: [],
    highlight_text: '',
  }));
  const activeIndex = selectedCitation
    ? citations.findIndex((c) => c.chunk_id === selectedCitation.chunk_id)
    : -1;

  // Helper to highlight terms of query in snippet
  const getQueryHighlights = (text: string, q: string): HighlightSpan[] => {
    if (!q.trim()) return [];
    const words = q.trim().toLowerCase().split(/\s+/).filter((w) => w.length > 2);
    if (words.length === 0) return [];
    const spans: HighlightSpan[] = [];
    const lowerText = text.toLowerCase();
    for (const w of words) {
      let pos = 0;
      while ((pos = lowerText.indexOf(w, pos)) !== -1 && spans.length < 15) {
        spans.push({ start: pos, end: pos + w.length });
        pos += w.length;
      }
    }
    return spans;
  };

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full overflow-y-auto px-4 py-6 md:px-6 md:py-8 items-center min-w-0">
        <div className="w-full max-w-4xl space-y-6">
          {/* PageHeader */}
          <PageHeader
            title="Document Search"
            subtitle="Direct hybrid retrieval (BM25 + Dense) with strict server-side access policy filtering."
            breadcrumb="Workspace / Search"
          />

          {/* Search Controls Card */}
          <form
            onSubmit={handleSearch}
            className="rounded-card border border-border bg-surface p-5 shadow-sm space-y-4"
          >
            {sourceFilter && (
              <div
                className="flex items-center justify-between gap-2 px-3.5 py-2 bg-primary-soft border border-primary/30 rounded-btn text-xs shadow-xs"
                role="status"
                aria-live="polite"
                data-testid="search-source-filter-chip"
              >
                <div className="flex items-center gap-2 min-w-0 truncate">
                  <span className="text-text-muted shrink-0 font-medium">Searching only in:</span>
                  <span className="font-semibold text-primary truncate">{sourceFilter.filename}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setSourceFilter(null)}
                  className="p-1 rounded text-text-muted hover:text-text hover:bg-surface transition-colors shrink-0"
                  aria-label="Remove document filter"
                  data-testid="clear-search-source-filter-button"
                >
                  <X size={14} aria-hidden="true" />
                </button>
              </div>
            )}

            {/* Large Search Input */}
            <div className="relative flex items-center">
              <div className="pointer-events-none absolute left-3.5 flex items-center text-text-muted">
                <Search size={20} aria-hidden="true" />
              </div>
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search across documents, expenses, contracts, or policies..."
                className="w-full rounded-input border border-border bg-surface-2/60 py-3 pl-11 pr-32 text-sm sm:text-base text-text placeholder:text-text-muted outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus:border-primary transition-all shadow-xs"
              />
              <div className="absolute right-2 flex items-center gap-1.5">
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery('')}
                    aria-label="Clear query"
                    className="p-1.5 text-text-muted hover:text-text rounded"
                  >
                    <X size={16} aria-hidden="true" />
                  </button>
                )}
                <button
                  type="submit"
                  disabled={isLoading || !query.trim()}
                  className="rounded-btn bg-brand-gradient px-4 py-2 text-xs font-semibold text-white shadow-xs hover:shadow-md hover:brightness-105 active:brightness-95 disabled:opacity-40 transition-all min-h-[36px]"
                  data-testid="search-submit-button"
                >
                  {isLoading ? 'Searching...' : 'Search'}
                </button>
              </div>
            </div>

            {/* Options Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border-subtle pt-3.5 text-xs text-text-muted">
              <div className="flex items-center gap-5">
                {/* Re-rank toggle */}
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rerank}
                    onChange={(e) => setRerank(e.target.checked)}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-focus-ring"
                  />
                  <span className="font-semibold text-text">Cross-Encoder Re-rank</span>
                </label>

                {/* Top K selector */}
                <div className="flex items-center gap-1.5">
                  <SlidersHorizontal size={13} className="text-text-muted" aria-hidden="true" />
                  <label htmlFor="top-k-select" className="text-text-muted font-medium">
                    Top K:
                  </label>
                  <select
                    id="top-k-select"
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="rounded-input border border-border bg-surface px-2.5 py-1 text-xs text-text focus:border-primary outline-none font-semibold cursor-pointer"
                  >
                    <option value={3}>3</option>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="hidden sm:inline text-[11px] text-text-muted">
                  Press <kbd className="font-mono bg-surface-2 border border-border px-1 rounded text-[10px]">/</kbd> to focus
                </span>
                {latencyMs !== null && (
                  <div className="font-mono text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded-btn border border-border" data-testid="search-latency">
                    Latency: {formatLatency(latencyMs)}
                  </div>
                )}
              </div>
            </div>
          </form>

          {/* Error Banner */}
          {errorMessage && (
            <ErrorBanner
              message={errorMessage}
              onRetry={handleSearch}
              onDismiss={() => setErrorMessage(null)}
            />
          )}

          {/* Loading Skeletons */}
          {isLoading && (
            <div className="space-y-3 pt-2" aria-live="polite">
              <Skeleton className="h-28 w-full rounded-card" />
              <Skeleton className="h-28 w-full rounded-card" />
              <Skeleton className="h-28 w-full rounded-card" />
            </div>
          )}

          {/* First visit EmptyState */}
          {!isLoading && results === null && (
            <EmptyState
              icon={<Compass size={28} className="text-primary" />}
              title="Explore Authorized Documents"
              hint="Search across board memos, engineering specifications, compensation records, and vendor invoices permitted under your role."
            />
          )}

          {/* Results List */}
          {!isLoading && results !== null && (
            <div className="space-y-3.5" aria-live="polite">
              {results.length === 0 ? (
                /* No Results Empty State */
                <div
                  className="rounded-card border border-border bg-surface p-8 text-center text-sm text-text-muted shadow-xs"
                  data-testid="no-results-found"
                >
                  <p className="font-heading font-semibold text-text text-base">No accessible results found.</p>
                  <p className="text-xs text-text-muted mt-1.5 max-w-sm mx-auto">
                    Try refining your query or keywords. Only chunks you have explicit access to are returned.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-text-muted px-1">
                    <span>Results ({results.length})</span>
                    <span>Relevance</span>
                  </div>

                  {results.map((item, idx) => {
                    const isDb = Boolean(item.row_id || item.chunk_id.startsWith('db:'));
                    const ext = item.file.split('.').pop() || 'text';
                    const scorePct = Math.min(100, Math.max(12, Math.round(item.score * 100)));
                    const highlightSpans = getQueryHighlights(item.text, query);

                    return (
                      <div
                        key={item.chunk_id}
                        className="rounded-card border border-border bg-surface p-4 sm:p-5 transition-all hover:border-primary hover:shadow-md space-y-3 shadow-xs"
                        data-testid={`search-result-${idx}`}
                      >
                        {/* Header Row */}
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2.5 min-w-0">
                            {isDb ? (
                              <Database size={16} className="text-cyan-600 dark:text-cyan-400 shrink-0" aria-hidden="true" />
                            ) : (
                              <FileTypeIcon kind={ext} size={17} />
                            )}
                            <h3 className="font-heading font-bold text-sm text-text truncate">
                              {formatSourceLabel(item.file, item.page, item.row_id)}
                            </h3>
                            {item.page !== null && (
                              <span className="rounded bg-surface-2 px-1.5 py-0.2 text-[10px] font-mono text-text-muted border border-border shrink-0">
                                Page {item.page}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {/* Relevance bar */}
                            <div className="hidden sm:flex items-center gap-1.5">
                              <div className="h-1.5 w-16 bg-surface-2 rounded-full overflow-hidden border border-border/40">
                                <div
                                  className="h-full bg-brand-gradient rounded-full"
                                  style={{ width: `${scorePct}%` }}
                                />
                              </div>
                            </div>
                            <span className="font-mono text-xs font-semibold text-text-muted rounded bg-surface-2 px-2 py-0.5 border border-border">
                              {item.score.toFixed(3)}
                            </span>
                          </div>
                        </div>

                        {/* Snippet with Highlighted Query Terms */}
                        <div className="text-xs sm:text-sm text-text-muted line-clamp-3 leading-relaxed font-sans font-normal border-l-2 border-primary/30 pl-3">
                          <HighlightedText text={item.text} highlights={highlightSpans} autoScrollToFirst={false} />
                        </div>

                        {/* Footer Action */}
                        <div className="flex justify-end pt-1 border-t border-border-subtle">
                          <button
                            type="button"
                            onClick={() => handleSelectResult(item, idx)}
                            className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-accent transition-colors py-1 px-2.5 rounded-btn hover:bg-surface-2 min-h-[34px]"
                          >
                            <span>Open source</span>
                            <ExternalLink size={13} aria-hidden="true" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Citation Slide-over Panel */}
      {selectedCitation && (
        <CitationPanel
          citation={selectedCitation}
          citations={citations}
          currentIndex={activeIndex >= 0 ? activeIndex : 0}
          onNavigate={(cit) => setSelectedCitation(cit)}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
