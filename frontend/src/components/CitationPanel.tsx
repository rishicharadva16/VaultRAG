import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import { CitationItem, SourceViewResponse, SourcePagesResponse, Rect } from '../api/types';
import { formatSourceLabel } from '../lib/format';
import { HighlightedText } from './HighlightedText';
import { Skeleton } from './Skeleton';
import { FileTypeIcon } from './ui';
import {
  X,
  Quote,
  AlertCircle,
  Database,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Lock,
  Layers,
  FileCode,
  RotateCcw,
} from 'lucide-react';

export interface CitationPanelProps {
  citation: CitationItem | null;
  citations?: CitationItem[];
  currentIndex?: number;
  onNavigate?: (citation: CitationItem, newIndex: number) => void;
  siblingCitations?: CitationItem[];
  onClose: () => void;
}

// In-memory session cache for view and pages metadata
const viewCache = new Map<string, SourceViewResponse>();
const pagesCache = new Map<string, SourcePagesResponse>();

export function clearCitationViewCache() {
  viewCache.clear();
  pagesCache.clear();
}

export function toPercentString(val: number): string {
  return `${Number((val * 100).toFixed(4))}%`;
}

/**
 * Parses structured field: value or label value pairs from DB row text.
 */
export function parseDbRowFields(text: string): { label: string; value: string }[] | null {
  if (!text) return null;

  // Pattern 1: key: value separated by commas, newlines, or pipes
  if (text.includes(':')) {
    const parts = text.split(/,|\n|\|/).map((s) => s.trim()).filter(Boolean);
    const fields: { label: string; value: string }[] = [];
    for (const part of parts) {
      const colonIdx = part.indexOf(':');
      if (colonIdx > 0) {
        const label = part.slice(0, colonIdx).trim();
        const value = part.slice(colonIdx + 1).trim();
        if (label && value) {
          fields.push({ label, value });
        }
      }
    }
    if (fields.length >= 2) {
      return fields;
    }
  }

  // Pattern 2: "name Asha Patel, email asha@..."
  const commaParts = text.split(',').map((s) => s.trim()).filter(Boolean);
  if (commaParts.length >= 2) {
    const fields: { label: string; value: string }[] = [];
    for (const part of commaParts) {
      const spaceIdx = part.indexOf(' ');
      if (spaceIdx > 0) {
        const label = part.slice(0, spaceIdx).trim();
        const value = part.slice(spaceIdx + 1).trim();
        if (/^[a-zA-Z_]+$/.test(label) && value) {
          fields.push({ label, value });
        }
      }
    }
    if (fields.length >= 2) {
      return fields;
    }
  }

  return null;
}

const EMPTY_CITATIONS: CitationItem[] = [];

export const CitationPanel: React.FC<CitationPanelProps> = ({
  citation,
  citations = EMPTY_CITATIONS,
  currentIndex,
  onNavigate,
  siblingCitations = EMPTY_CITATIONS,
  onClose,
}) => {
  const panelRef = useRef<HTMLElement>(null);
  const prevFocusRef = useRef<HTMLElement | null>(null);
  const firstRectRef = useRef<HTMLDivElement | null>(null);
  const createdBlobUrlsRef = useRef<Set<string>>(new Set());

  // Panel resizing state
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('vaultrag_citation_panel_width');
      if (saved) {
        const val = parseInt(saved, 10);
        if (!isNaN(val) && val >= 320 && val <= (typeof window !== 'undefined' ? window.innerWidth * 0.85 : 1200)) {
          return val;
        }
      }
    } catch {
      // ignore
    }
    return typeof window !== 'undefined' ? Math.max(380, Math.round(window.innerWidth * 0.5)) : 520;
  });

  // Data fetching state
  const [viewData, setViewData] = useState<SourceViewResponse | null>(null);
  const [pagesData, setPagesData] = useState<SourcePagesResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [siblingRects, setSiblingRects] = useState<Rect[]>([]);

  // Sibling citation rects fetching (fainter highlights from other citations of the same answer)
  useEffect(() => {
    if (!citation || !siblingCitations || siblingCitations.length === 0) {
      setSiblingRects((prev) => (prev.length > 0 ? [] : prev));
      return;
    }

    const matchingSiblings = siblingCitations.filter(
      (sc) => sc.chunk_id === citation.chunk_id && sc.highlights && sc.highlights.length > 0
    );

    if (matchingSiblings.length === 0) {
      setSiblingRects((prev) => (prev.length > 0 ? [] : prev));
      return;
    }

    const controller = new AbortController();
    Promise.all(
      matchingSiblings.map((sc) =>
        api.getSourceView(sc.chunk_id, sc.highlights, controller.signal).catch(() => null)
      )
    ).then((responses) => {
      const allSibRects: Rect[] = [];
      for (const res of responses) {
        if (res && res.rects) {
          allSibRects.push(...res.rects);
        }
      }
      setSiblingRects(allSibRects);
    });

    return () => {
      controller.abort();
    };
  }, [citation, siblingCitations]);

  // Document viewing state
  const [pageImages, setPageImages] = useState<Record<number, string>>({});
  const [loadingPages, setLoadingPages] = useState<Record<number, boolean>>({});
  const [viewMode, setViewMode] = useState<'document' | 'text'>('document');
  const [zoom, setZoom] = useState<number>(100);
  const [fitWidth, setFitWidth] = useState<boolean>(true);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [jumpInput, setJumpInput] = useState<string>('1');
  const [pulsing, setPulsing] = useState<boolean>(false);

  // Focus trap & Escape key listener
  useEffect(() => {
    prevFocusRef.current = document.activeElement as HTMLElement;
    panelRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }

      if (e.key === 'Tab' && panelRef.current) {
        const focusables = panelRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      prevFocusRef.current?.focus();
    };
  }, [onClose]);

  // Clean up all blob URLs on unmount
  useEffect(() => {
    return () => {
      createdBlobUrlsRef.current.forEach((url) => {
        try {
          URL.revokeObjectURL(url);
        } catch {
          // ignore
        }
      });
      createdBlobUrlsRef.current.clear();
    };
  }, []);

  // Draggable edge resizing
  const isDraggingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  const handleMouseDownResize = (e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    startXRef.current = e.clientX;
    startWidthRef.current = panelWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = startXRef.current - moveEvent.clientX;
      const newWidth = Math.min(
        Math.max(340, startWidthRef.current + delta),
        window.innerWidth - 300
      );
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      try {
        localStorage.setItem('vaultrag_citation_panel_width', String(panelWidth));
      } catch {
        // ignore
      }
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  const pageImagesRef = useRef<Record<number, string>>({});
  const loadingPagesRef = useRef<Record<number, boolean>>({});

  // Helper to load image blob for a specific page
  const loadPageImage = useCallback(
    async (pageNum: number, chunkId: string, signal?: AbortSignal) => {
      if (pageImagesRef.current[pageNum] || loadingPagesRef.current[pageNum]) return;

      loadingPagesRef.current[pageNum] = true;
      setLoadingPages((prev) => ({ ...prev, [pageNum]: true }));
      try {
        const blob = await api.getSourcePageImageBlob(chunkId, pageNum, signal);
        const objectUrl = URL.createObjectURL(blob);
        createdBlobUrlsRef.current.add(objectUrl);
        pageImagesRef.current[pageNum] = objectUrl;
        setPageImages((prev) => ({ ...prev, [pageNum]: objectUrl }));
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        // If image fails to load, fallback to text view
        setViewMode('text');
      } finally {
        loadingPagesRef.current[pageNum] = false;
        setLoadingPages((prev) => ({ ...prev, [pageNum]: false }));
      }
    },
    []
  );

  // Main data fetch on citation change
  const fetchSource = useCallback(
    async (activeCit: CitationItem, signal: AbortSignal) => {
      setIsLoading(true);
      setError(null);
      setViewData(null);
      setPagesData(null);
      setPageImages({});
      setLoadingPages({});
      pageImagesRef.current = {};
      loadingPagesRef.current = {};

      const chunkId = activeCit.chunk_id;

      try {
        // 1. Fetch view metadata
        let vData: SourceViewResponse;
        if (viewCache.has(chunkId)) {
          vData = viewCache.get(chunkId)!;
        } else {
          vData = await api.getSourceView(chunkId, activeCit.highlights, signal);
          viewCache.set(chunkId, vData);
        }
        setViewData(vData);

        // 2. Dispatch by kind
        if (vData.kind === 'pdf_text') {
          let pData: SourcePagesResponse;
          if (pagesCache.has(chunkId)) {
            pData = pagesCache.get(chunkId)!;
          } else {
            pData = await api.getSourcePages(chunkId, signal);
            pagesCache.set(chunkId, pData);
          }
          setPagesData(pData);

          const targetPage = vData.page || 1;
          setCurrentPage(targetPage);
          setJumpInput(String(targetPage));

          // Set view mode based on match
          if (vData.match === 'none') {
            setViewMode('text');
          } else {
            setViewMode('document');
            // Fetch cited page image
            if (pData.readable_pages.includes(targetPage)) {
              loadPageImage(targetPage, chunkId, signal);
            }
          }
        } else if (vData.kind === 'image') {
          setCurrentPage(1);
          setJumpInput('1');
          if (vData.match === 'none') {
            setViewMode('text');
          } else {
            setViewMode('document');
            loadPageImage(1, chunkId, signal);
          }
        } else {
          // db_row
          setViewMode('text');
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (err instanceof ApiClientError && err.status === 404) {
          setError('This source is no longer available.');
        } else {
          setError('Failed to load source. Please try again.');
        }
      } finally {
        setIsLoading(false);
      }
    },
    [loadPageImage]
  );

  useEffect(() => {
    if (!citation) {
      setViewData(null);
      setError(null);
      return;
    }

    const controller = new AbortController();
    fetchSource(citation, controller.signal);

    return () => {
      controller.abort();
    };
  }, [citation, fetchSource]);

  // Scroll to highlight with pulse once loaded
  useEffect(() => {
    if (viewData && viewData.rects.length > 0 && viewMode === 'document') {
      const timer = setTimeout(() => {
        if (firstRectRef.current) {
          firstRectRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setPulsing(true);
          const pulseTimer = setTimeout(() => setPulsing(false), 2400);
          return () => clearTimeout(pulseTimer);
        }
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [viewData, viewMode, pageImages]);

  if (!citation) return null;

  // Active citation index in multi-citation navigation
  const activeIdx =
    currentIndex !== undefined
      ? currentIndex
      : citations.findIndex((c) => c.chunk_id === citation.chunk_id && c.id === citation.id);
  const totalCitations = citations.length > 0 ? citations.length : 1;
  const canGoPrev = citations.length > 1 && activeIdx > 0;
  const canGoNext = citations.length > 1 && activeIdx >= 0 && activeIdx < citations.length - 1;

  const totalDocPages = pagesData?.page_count || viewData?.page || 1;
  const readablePages = pagesData?.readable_pages || (viewData?.page ? [viewData.page] : [1]);
  const isDb = Boolean(viewData?.kind === 'db_row' || citation.row_id || citation.chunk_id.startsWith('db:'));

  const handlePrev = () => {
    if (canGoPrev && onNavigate) {
      onNavigate(citations[activeIdx - 1], activeIdx - 1);
    }
  };

  const handleNext = () => {
    if (canGoNext && onNavigate) {
      onNavigate(citations[activeIdx + 1], activeIdx + 1);
    }
  };

  const handleJumpToPage = (e: React.FormEvent) => {
    e.preventDefault();
    const p = parseInt(jumpInput, 10);
    if (!isNaN(p) && p >= 1 && p <= totalDocPages) {
      setCurrentPage(p);
      const el = document.getElementById(`source-page-${p}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      if (readablePages.includes(p) && !pageImages[p]) {
        loadPageImage(p, citation.chunk_id);
      }
    }
  };

  const parsedDbFields = viewData ? parseDbRowFields(viewData.text) : null;

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      aria-label="Source Document Viewer"
      className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-border bg-surface shadow-panel transition-all duration-150 ease-in-out md:static md:h-full md:shadow-none"
      style={{ width: `${panelWidth}px` }}
      data-testid="citation-panel"
    >
      {/* Draggable Resizer Edge on Desktop */}
      <div
        onMouseDown={handleMouseDownResize}
        title="Drag to resize panel"
        aria-hidden="true"
        className="hidden md:block absolute left-0 top-0 bottom-0 w-2 cursor-col-resize hover:bg-accent/40 active:bg-accent transition-colors z-20 group"
      >
        <div className="w-0.5 h-8 bg-border group-hover:bg-accent mx-auto relative top-1/2 -translate-y-1/2 rounded" />
      </div>

      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-col border-b border-border bg-surface-2/70 shrink-0">
        <div className="flex items-center justify-between p-4 gap-2">
          {/* File & Location Info */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-text-muted">
              {isDb ? (
                <Database size={14} className="shrink-0 text-cyan-600 dark:text-cyan-400" />
              ) : (
                <FileTypeIcon kind={citation.file.split('.').pop() || 'text'} size={15} />
              )}
              <span className="truncate">
                {isDb
                  ? `Row ${viewData?.row_id || citation.row_id || 'N/A'}`
                  : `Page ${currentPage} of ${totalDocPages}`}
              </span>
              {viewData?.match === 'exact' && (
                <span className="rounded-badge bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold shrink-0">
                  Exact match
                </span>
              )}
              {viewData?.match === 'partial' && (
                <span className="rounded-badge bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 px-2 py-0.5 text-[10px] font-semibold shrink-0">
                  Approximate
                </span>
              )}
            </div>
            <h2 className="truncate font-heading text-sm font-bold text-text mt-1" title={citation.file}>
              {formatSourceLabel(citation.file, citation.page, citation.row_id)}
            </h2>
          </div>

          {/* Citation Stepper & Close */}
          <div className="flex items-center gap-1.5 shrink-0">
            {citations.length > 1 && (
              <div className="flex items-center border border-border rounded-btn bg-surface px-1 py-0.5 text-xs text-text-muted mr-1 shadow-xs">
                <button
                  type="button"
                  onClick={handlePrev}
                  disabled={!canGoPrev}
                  aria-label="Previous citation"
                  className="p-1 rounded hover:bg-surface-2 hover:text-text disabled:opacity-30 disabled:pointer-events-none transition-colors"
                >
                  <ChevronLeft size={15} />
                </button>
                <span className="px-2 font-mono font-semibold select-none text-[11px] text-text">
                  {activeIdx + 1} of {totalCitations}
                </span>
                <button
                  type="button"
                  onClick={handleNext}
                  disabled={!canGoNext}
                  aria-label="Next citation"
                  className="p-1 rounded hover:bg-surface-2 hover:text-text disabled:opacity-30 disabled:pointer-events-none transition-colors"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={onClose}
              aria-label="Close source viewer (Esc)"
              className="rounded-btn p-1.5 text-text-muted hover:bg-surface-2 hover:text-text transition-colors min-h-[36px] min-w-[36px] flex items-center justify-center"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Highlighted Quote Caption (Tinted callout) */}
        {citation.highlight_text && (
          <div
            className="border-t border-border-subtle bg-primary-soft/40 px-4 py-2.5 text-xs text-text flex items-start gap-2 min-w-0"
            data-testid="citation-caption"
          >
            <Quote size={13} className="shrink-0 text-primary mt-0.5" aria-hidden="true" />
            <span className="italic leading-relaxed font-medium line-clamp-2">
              "{citation.highlight_text}"
            </span>
          </div>
        )}

        {/* ── Document Toolbar ──────────────────────────────────── */}
        {!isLoading && !error && viewData && viewData.kind !== 'db_row' && (
          <div className="flex flex-wrap items-center justify-between border-t border-border-subtle px-3.5 py-2 text-xs bg-surface gap-2">
            {/* Page Jump / Indicator */}
            {viewData.kind === 'pdf_text' && (
              <form onSubmit={handleJumpToPage} className="flex items-center gap-1.5">
                <span className="text-text-muted text-[11px]">Page</span>
                <input
                  type="number"
                  min={1}
                  max={totalDocPages}
                  value={jumpInput}
                  onChange={(e) => setJumpInput(e.target.value)}
                  className="w-12 rounded-input border border-border bg-surface-raised px-1.5 py-0.5 text-center text-xs font-mono font-semibold text-text focus:border-accent outline-none"
                  aria-label="Jump to page"
                />
                <span className="text-text-muted text-[11px]">of {totalDocPages}</span>
              </form>
            )}

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 text-text-muted">
              <button
                type="button"
                onClick={() => {
                  setFitWidth(false);
                  setZoom((prev) => Math.max(50, prev - 25));
                }}
                disabled={zoom <= 50 && !fitWidth}
                aria-label="Zoom out"
                className="rounded-btn p-1 hover:bg-surface-raised hover:text-text disabled:opacity-30 transition-colors"
              >
                <ZoomOut size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setFitWidth(false);
                  setZoom(100);
                }}
                className="px-1.5 py-0.5 rounded font-mono text-[11px] font-medium hover:bg-surface-raised hover:text-text transition-colors"
                title="Reset zoom to 100%"
              >
                {fitWidth ? 'Fit' : `${zoom}%`}
              </button>
              <button
                type="button"
                onClick={() => {
                  setFitWidth(false);
                  setZoom((prev) => Math.min(200, prev + 25));
                }}
                disabled={zoom >= 200 && !fitWidth}
                aria-label="Zoom in"
                className="rounded-btn p-1 hover:bg-surface-raised hover:text-text disabled:opacity-30 transition-colors"
              >
                <ZoomIn size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setFitWidth(true);
                  setZoom(100);
                }}
                className={`p-1 rounded-btn hover:bg-surface-raised hover:text-text transition-colors ${
                  fitWidth ? 'text-accent font-semibold' : ''
                }`}
                title="Fit to width"
                aria-label="Fit to width"
              >
                <Maximize2 size={13} />
              </button>
            </div>

            {/* Document vs Text View Toggle */}
            <div className="flex items-center border border-border rounded-btn bg-surface-raised p-0.5">
              <button
                type="button"
                onClick={() => setViewMode('document')}
                disabled={viewData.match === 'none'}
                className={`flex items-center gap-1 rounded-btn px-2 py-0.5 text-[11px] font-medium transition-colors ${
                  viewMode === 'document'
                    ? 'bg-surface text-accent shadow-xs font-semibold'
                    : 'text-text-muted hover:text-text disabled:opacity-40'
                }`}
              >
                <Layers size={12} />
                <span>Page</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('text')}
                className={`flex items-center gap-1 rounded-btn px-2 py-0.5 text-[11px] font-medium transition-colors ${
                  viewMode === 'text'
                    ? 'bg-surface text-accent shadow-xs font-semibold'
                    : 'text-text-muted hover:text-text'
                }`}
              >
                <FileCode size={12} />
                <span>Text</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Body ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 space-y-4">
        {/* Partial Match Notice */}
        {viewData?.match === 'partial' && viewMode === 'document' && (
          <div
            className="flex items-center gap-2 rounded-card border border-warning/40 bg-warning/10 p-2.5 text-xs text-warning"
            data-testid="partial-match-notice"
          >
            <AlertCircle size={14} className="shrink-0" />
            <span>Partial layout match: some highlighted lines could not be precisely mapped to the document layout.</span>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-4 pt-3" aria-live="polite" data-testid="viewer-skeleton">
            <div className="text-xs text-text-muted font-medium">Loading verified source page...</div>
            <Skeleton className="h-64 w-full rounded-card" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        )}

        {/* 404 or Fetch Error */}
        {!isLoading && error && (
          <div
            role="alert"
            className="flex flex-col items-center justify-center p-8 text-center space-y-3 rounded-card border border-border bg-surface-raised"
            data-testid="citation-error"
          >
            <div className="rounded-full bg-surface p-3 border border-border text-text-muted">
              <AlertCircle size={22} aria-hidden="true" />
            </div>
            <p className="text-sm font-semibold text-text">{error}</p>
            {error !== 'This source is no longer available.' && (
              <button
                type="button"
                onClick={() => {
                  const controller = new AbortController();
                  fetchSource(citation, controller.signal);
                }}
                className="flex items-center gap-1.5 rounded-btn bg-accent px-3 py-1.5 text-xs font-semibold text-accent-contrast hover:bg-accent-hover transition-colors"
              >
                <RotateCcw size={13} />
                <span>Retry</span>
              </button>
            )}
          </div>
        )}

        {/* ── DB Row View ───────────────────────────────────────── */}
        {!isLoading && !error && viewData && viewData.kind === 'db_row' && (
          <div className="space-y-4" data-testid="db-row-card">
            <div className="rounded-card border border-border bg-surface p-4 space-y-3 shadow-xs">
              <div className="flex items-center justify-between border-b border-border-subtle pb-2.5">
                <div className="flex items-center gap-2">
                  <div className="rounded-md bg-accent/10 p-1.5 text-accent">
                    <Database size={15} />
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">Database Record</div>
                    <div className="text-sm font-bold text-text font-mono">
                      {viewData.file} • Row {viewData.row_id || citation.row_id || 'N/A'}
                    </div>
                  </div>
                </div>
              </div>

              {parsedDbFields ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {parsedDbFields.map((f, i) => (
                    <div key={i} className="rounded-input border border-border-subtle bg-surface-raised p-2.5">
                      <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-0.5">
                        {f.label}
                      </div>
                      <div className="font-mono text-xs text-text break-words font-medium">{f.value}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-input border border-border-subtle bg-surface-raised p-3 text-xs font-mono whitespace-pre-wrap text-text">
                  {viewData.text}
                </div>
              )}
            </div>

            {/* Cited record text passage */}
            <div className="space-y-1.5">
              <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">Cited Record Passage</div>
              <div className="rounded-card border border-border bg-surface p-3.5 text-xs font-mono leading-relaxed">
                <HighlightedText text={viewData.text} highlights={citation.highlights} autoScrollToFirst={true} />
              </div>
            </div>
          </div>
        )}

        {/* ── Text View Toggle (or fallback on match none) ───────── */}
        {!isLoading && !error && viewData && viewData.kind !== 'db_row' && viewMode === 'text' && (
          <div className="space-y-3" data-testid="chunk-text-view">
            {viewData.match === 'none' && (
              <div className="rounded-card border border-border bg-surface-raised p-3 text-xs text-text-muted flex items-start gap-2">
                <AlertCircle size={14} className="shrink-0 mt-0.5 text-accent" />
                <span>Document layout coordinates unavailable for this segment. Showing verified chunk text.</span>
              </div>
            )}
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">Source Chunk Content</div>
            <div className="rounded-card border border-border bg-surface p-4 text-xs font-mono leading-relaxed shadow-xs">
              <HighlightedText text={viewData.text} highlights={citation.highlights} autoScrollToFirst={true} />
            </div>
          </div>
        )}

        {/* ── Document Page View (PDF & Image) ──────────────────── */}
        {!isLoading && !error && viewData && viewData.kind !== 'db_row' && viewMode === 'document' && (
          <div
            className="flex flex-col items-center w-full transition-transform duration-100"
            style={{
              width: fitWidth ? '100%' : `${zoom}%`,
              margin: '0 auto',
            }}
            data-testid="document-page-view"
          >
            {/* Render all pages for PDF (or single page for image) */}
            {Array.from({ length: totalDocPages }, (_, idx) => idx + 1).map((p) => {
              const isCitedPage = p === (viewData.page || 1);
              const isPageReadable = readablePages.includes(p);
              const imageUrl = pageImages[p];
              const isPageLoading = loadingPages[p];

              // Unreadable page -> locked placeholder (no hints, no text)
              if (!isPageReadable) {
                return (
                  <div
                    key={p}
                    id={`source-page-${p}`}
                    data-testid={`locked-page-${p}`}
                    className="relative w-full rounded-card border border-border bg-surface-raised flex flex-col items-center justify-center p-8 text-center text-text-muted my-3 aspect-[1/1.414] shadow-xs select-none"
                  >
                    <div className="rounded-full bg-surface p-3 border border-border text-text-muted mb-2.5">
                      <Lock size={20} aria-hidden="true" />
                    </div>
                    <p className="font-semibold text-text text-xs">Page unavailable</p>
                    <p className="text-[11px] text-text-muted mt-1 max-w-xs">
                      Page {p} cannot be viewed under your access policy.
                    </p>
                  </div>
                );
              }

              return (
                <div
                  key={p}
                  id={`source-page-${p}`}
                  className="relative w-full rounded-card border border-border bg-surface shadow-xs overflow-hidden my-3 group"
                  style={{
                    aspectRatio:
                      viewData.page_width && viewData.page_height
                        ? `${viewData.page_width} / ${viewData.page_height}`
                        : '1 / 1.414',
                  }}
                >
                  {imageUrl ? (
                    <>
                      <img
                        src={imageUrl}
                        alt={`Document page ${p}`}
                        className="w-full h-auto block select-none pointer-events-none"
                        data-testid={`page-image-${p}`}
                      />

                      {/* Sibling citation highlights (fainter) */}
                      {isCitedPage &&
                        siblingRects.map((rect, sIdx) => (
                          <div
                            key={`sib-${sIdx}`}
                            className="absolute bg-yellow-300/20 border border-yellow-400/40 rounded-xs pointer-events-none"
                            style={{
                              left: toPercentString(rect.x),
                              top: toPercentString(rect.y),
                              width: toPercentString(rect.w),
                              height: toPercentString(rect.h),
                            }}
                            data-testid="sibling-highlight-rect"
                          />
                        ))}

                      {/* Primary Highlight Rectangles Overlay */}
                      {isCitedPage &&
                        viewData.rects.map((rect: Rect, rIdx: number) => {
                          const isFirst = rIdx === 0;
                          return (
                            <div
                              key={rIdx}
                              ref={isFirst ? firstRectRef : undefined}
                              className={`absolute bg-yellow-400/40 border border-yellow-500/70 dark:bg-yellow-400/35 dark:border-yellow-400/60 rounded-xs pointer-events-none transition-all ${
                                isFirst && pulsing ? 'animate-highlight-pulse ring-2 ring-yellow-400' : ''
                              }`}
                              style={{
                                left: toPercentString(rect.x),
                                top: toPercentString(rect.y),
                                width: toPercentString(rect.w),
                                height: toPercentString(rect.h),
                              }}
                              data-testid="highlight-rect"
                            />
                          );
                        })}
                    </>
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center p-6 text-text-muted">
                      {isPageLoading ? (
                        <div className="flex flex-col items-center gap-2">
                          <Skeleton className="h-6 w-6 rounded-full" />
                          <span className="text-xs">Loading page {p}...</span>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => loadPageImage(p, citation.chunk_id)}
                          className="rounded-btn border border-border bg-surface-raised px-3 py-1.5 text-xs font-medium text-text hover:bg-surface transition-colors"
                        >
                          Load page {p}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
};
