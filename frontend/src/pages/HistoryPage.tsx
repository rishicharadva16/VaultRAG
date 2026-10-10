import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import { HistoryItem } from '../api/types';
import {
  History,
  Search,
  Trash2,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  FileText,
  User,
  Loader2,
  Clock,
  X,
} from 'lucide-react';

export const HistoryPage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = Boolean(user?.roles && user.roles.includes('admin'));
  const navigate = useNavigate();

  const [items, setItems] = useState<HistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const PAGE_SIZE = 50;

  // Debounce search input by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Fetch history items
  const fetchHistory = useCallback(
    async (q: string, currentOffset: number, append: boolean = false) => {
      try {
        if (append) {
          setIsLoadingMore(true);
        } else {
          setIsLoading(true);
        }

        const data = await api.getHistory({
          limit: PAGE_SIZE,
          offset: currentOffset,
          q: q.trim() || undefined,
        });

        if (append) {
          setItems((prev) => [...prev, ...data]);
        } else {
          setItems(data);
        }

        setHasMore(data.length >= PAGE_SIZE);
      } catch (err) {
        console.error('Failed to load history', err);
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    []
  );

  // Trigger fetch when debounced query changes
  useEffect(() => {
    setOffset(0);
    fetchHistory(debouncedQuery, 0, false);
  }, [debouncedQuery, fetchHistory]);

  const handleLoadMore = () => {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    fetchHistory(debouncedQuery, nextOffset, true);
  };

  const handleAskAgain = (question: string) => {
    navigate('/chat', { state: { auto_send_question: question } });
  };

  const handleDelete = async (id: string) => {
    try {
      setDeletingId(id);
      await api.deleteHistory(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch (err) {
      console.error('Failed to delete history item', err);
    } finally {
      setDeletingId(null);
    }
  };

  // Group items into Today, Yesterday, Earlier
  const groups = useMemo(() => {
    const today: HistoryItem[] = [];
    const yesterday: HistoryItem[] = [];
    const earlier: HistoryItem[] = [];

    const now = new Date();
    const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayDate = todayDate - 86400000;

    for (const item of items) {
      const itemDate = new Date(item.created_at);
      const itemMidnight = new Date(
        itemDate.getFullYear(),
        itemDate.getMonth(),
        itemDate.getDate()
      ).getTime();

      if (itemMidnight >= todayDate) {
        today.push(item);
      } else if (itemMidnight >= yesterdayDate) {
        yesterday.push(item);
      } else {
        earlier.push(item);
      }
    }

    return [
      { title: 'Today', items: today },
      { title: 'Yesterday', items: yesterday },
      { title: 'Earlier', items: earlier },
    ].filter((g) => g.items.length > 0);
  }, [items]);

  const formatTime = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return '';
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex h-full w-full flex-col overflow-y-auto bg-background px-4 py-6 sm:px-8">
      <div className="mx-auto w-full max-w-4xl space-y-6">
        {/* Page Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border-subtle/50 pb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent shrink-0">
              <History size={20} aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text leading-tight">
                History
              </h1>
              <p className="text-xs sm:text-sm text-text-muted mt-0.5">
                {isAdmin
                  ? 'Audit and re-run all enterprise query activities'
                  : 'Review and re-run your previous questions in Chat'}
              </p>
            </div>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-72 shrink-0">
            <Search
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search history..."
              className="h-10 w-full rounded-xl border border-border bg-surface pl-9 pr-8 text-sm text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent transition-colors"
              aria-label="Search query history"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text rounded-full"
                aria-label="Clear search"
              >
                <X size={14} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>

        {/* Content Area */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 text-center text-text-muted gap-3">
            <Loader2 size={28} className="animate-spin text-accent" aria-hidden="true" />
            <p className="text-sm font-medium">Loading history...</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center rounded-2xl border border-border bg-surface">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-raised border border-border text-accent mb-3 shadow-xs">
              <History size={24} aria-hidden="true" />
            </div>
            <p className="text-base font-semibold text-text">No queries yet</p>
            <p className="text-sm text-text-muted mt-1 max-w-sm">
              {searchQuery
                ? 'No queries matched your search filter. Try clearing the search box.'
                : 'Ask something in Chat.'}
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {groups.map((group) => (
              <section key={group.title} className="space-y-3">
                {/* Group Heading */}
                <div className="flex items-center gap-2">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                    {group.title}
                  </h2>
                  <span className="text-[11px] font-medium text-text-muted/70 bg-surface-raised border border-border px-2 py-0.5 rounded-full">
                    {group.items.length}
                  </span>
                </div>

                {/* Cards List */}
                <div className="space-y-3">
                  {group.items.map((item) => (
                    <article
                      key={item.id}
                      className="group rounded-2xl border border-border bg-surface p-4 sm:p-5 shadow-xs hover:border-accent/40 transition-colors flex flex-col gap-3"
                    >
                      {/* Top Row: Question + Actions */}
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm sm:text-base font-semibold text-text leading-snug break-words flex-1">
                          {item.question}
                        </p>

                        <div className="flex items-center gap-2 shrink-0">
                          {/* Ask again button */}
                          <button
                            type="button"
                            onClick={() => handleAskAgain(item.question)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/10 text-accent font-semibold text-xs hover:bg-accent/20 active:scale-95 transition-all min-h-[36px] cursor-pointer"
                            title="Ask again in Chat Assistant"
                          >
                            <RotateCcw size={13} aria-hidden="true" />
                            <span>Ask again</span>
                          </button>

                          {/* Delete button */}
                          <button
                            type="button"
                            onClick={() => handleDelete(item.id)}
                            disabled={deletingId === item.id}
                            className="flex items-center justify-center h-9 w-9 rounded-lg border border-border text-text-muted hover:text-danger hover:border-danger/40 hover:bg-danger/10 active:scale-95 disabled:opacity-40 transition-all cursor-pointer"
                            aria-label="Delete query history"
                            title="Delete this query entry"
                          >
                            {deletingId === item.id ? (
                              <Loader2 size={14} className="animate-spin text-danger" />
                            ) : (
                              <Trash2 size={15} aria-hidden="true" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Bottom Row: Metadata Badges */}
                      <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-text-muted pt-1">
                        {/* Time stamp */}
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-text-muted">
                          <Clock size={12} aria-hidden="true" />
                          <span>
                            {group.title === 'Earlier'
                              ? `${formatDate(item.created_at)} at ${formatTime(item.created_at)}`
                              : formatTime(item.created_at)}
                          </span>
                        </span>

                        <span className="opacity-40">•</span>

                        {/* Outcome Badge: Green Answered or Amber Refused */}
                        {item.outcome === 'answered' ? (
                          <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800">
                            <CheckCircle2 size={12} className="text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                            <span>Answered</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800">
                            <AlertTriangle size={12} className="text-amber-600 dark:text-amber-400" aria-hidden="true" />
                            <span>Refused</span>
                          </span>
                        )}

                        <span className="opacity-40">•</span>

                        {/* Source Count */}
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-text-muted">
                          <FileText size={12} aria-hidden="true" />
                          <span>
                            {item.source_count} {item.source_count === 1 ? 'source' : 'sources'}
                          </span>
                        </span>

                        {/* Admin Only: User Name and Department */}
                        {isAdmin && (item.user_name || item.department) && (
                          <>
                            <span className="opacity-40">•</span>
                            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-surface-raised border border-border text-[11px] font-medium text-text">
                              <User size={12} className="text-accent shrink-0" aria-hidden="true" />
                              <span className="font-semibold">{item.user_name || 'Unknown User'}</span>
                              {item.department && (
                                <span className="text-text-muted">({item.department})</span>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ))}

            {/* Load More Button */}
            {hasMore && (
              <div className="flex justify-center pt-2 pb-6">
                <button
                  type="button"
                  onClick={handleLoadMore}
                  disabled={isLoadingMore}
                  className="w-full sm:w-auto px-6 py-2.5 rounded-xl border border-border bg-surface text-sm font-semibold text-text hover:bg-surface-raised hover:border-accent active:scale-95 disabled:opacity-50 transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isLoadingMore ? (
                    <>
                      <Loader2 size={16} className="animate-spin text-accent" />
                      <span>Loading more...</span>
                    </>
                  ) : (
                    <span>Load more</span>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
