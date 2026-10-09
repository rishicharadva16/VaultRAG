import React, { useState } from 'react';
import { api, ApiClientError } from '../api/client';
import { CitationItem, SearchResultItem } from '../api/types';
import { formatLatency, formatSourceLabel } from '../lib/format';
import { CitationPanel } from '../components/CitationPanel';
import { ErrorBanner } from '../components/ErrorBanner';
import { Skeleton } from '../components/Skeleton';
import { Search, SlidersHorizontal, Database, FileText, Info } from 'lucide-react';

export const SearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [rerank, setRerank] = useState(false);
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

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

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full overflow-y-auto px-4 py-6 items-center">
        <div className="w-full max-w-3xl space-y-6">
          {/* Header */}
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text">Document Search</h1>
            <p className="text-xs text-text-muted mt-1">
              Direct hybrid retrieval (BM25 + Dense) with strict authorization filtering.
            </p>
          </div>

          {/* Search Controls Card */}
          <form
            onSubmit={handleSearch}
            className="rounded-card border border-border bg-surface p-4 shadow-xs space-y-4"
          >
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-text-muted">
                <Search size={18} aria-hidden="true" />
              </div>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search across documents, expenses, contracts, or policies..."
                className="w-full rounded-input border border-border bg-background py-2.5 pl-10 pr-24 text-sm text-text placeholder:text-text-muted focus:border-accent focus:outline-none font-sans"
              />
              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="absolute inset-y-1.5 right-1.5 flex items-center justify-center rounded-btn bg-accent px-4 text-xs font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover disabled:opacity-40 transition-colors"
                data-testid="search-submit-button"
              >
                {isLoading ? 'Searching...' : 'Search'}
              </button>
            </div>

            {/* Options bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border-subtle pt-3 text-xs text-text-muted">
              <div className="flex items-center gap-4">
                {/* Rerank toggle */}
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rerank}
                    onChange={(e) => setRerank(e.target.checked)}
                    className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                  />
                  <span className="font-medium text-text">Re-rank results</span>
                </label>

                {/* Top K selector */}
                <div className="flex items-center gap-1.5">
                  <SlidersHorizontal size={13} aria-hidden="true" />
                  <label htmlFor="top-k-select" className="text-text-muted">
                    Top K:
                  </label>
                  <select
                    id="top-k-select"
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="rounded-input border border-border bg-surface px-2 py-1 text-xs text-text focus:border-accent outline-none font-medium"
                  >
                    <option value={3}>3</option>
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                  </select>
                </div>
              </div>

              {latencyMs !== null && (
                <div className="font-mono text-xs text-text-muted" data-testid="search-latency">
                  Latency: {formatLatency(latencyMs)}
                </div>
              )}
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

          {/* Loading Skeleton */}
          {isLoading && (
            <div className="space-y-3 pt-2" aria-live="polite">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          )}

          {/* Results List */}
          {!isLoading && results !== null && (
            <div className="space-y-3" aria-live="polite">
              {results.length === 0 ? (
                /* Neutral Empty Result */
                <div
                  className="rounded-card border border-border bg-surface-raised p-5 text-center text-sm text-text-muted"
                  data-testid="no-results-found"
                >
                  <div className="inline-flex rounded-full bg-surface p-2 text-text-muted border border-border mb-2">
                    <Info size={16} aria-hidden="true" />
                  </div>
                  <p className="font-medium text-text">No accessible results found.</p>
                  <p className="text-xs text-text-muted mt-1">
                    Try refining your query or keywords. Only chunks you have access to are returned.
                  </p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-text-muted">
                    <span>Results ({results.length})</span>
                    <span>Score</span>
                  </div>

                  {results.map((item, idx) => {
                    const isDb = Boolean(item.row_id || item.chunk_id.startsWith('db:'));
                    return (
                      <button
                        key={item.chunk_id}
                        type="button"
                        onClick={() => handleSelectResult(item, idx)}
                        className="w-full text-left rounded-card border border-border bg-surface p-4 transition-all hover:border-accent hover:bg-surface-raised hover:shadow-xs group focus-visible:border-accent"
                        data-testid={`search-result-${idx}`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-1.5">
                          <div className="flex items-center gap-2 text-xs font-semibold text-text group-hover:text-accent transition-colors">
                            {isDb ? (
                              <Database size={14} className="text-text-muted" aria-hidden="true" />
                            ) : (
                              <FileText size={14} className="text-text-muted" aria-hidden="true" />
                            )}
                            <span>{formatSourceLabel(item.file, item.page, item.row_id)}</span>
                          </div>
                          <span className="font-mono text-xs font-semibold text-text-muted rounded bg-surface-raised px-1.5 py-0.5 border border-border-subtle">
                            {item.score.toFixed(3)}
                          </span>
                        </div>

                        <p className="text-xs text-text-muted line-clamp-3 leading-relaxed font-sans font-normal">
                          {item.text}
                        </p>
                      </button>
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
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
