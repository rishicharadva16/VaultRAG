import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import {
  AuditSummary,
  AdminQueryLog,
  AdminUploadItem,
  DocumentKind,
} from '../api/types';
import { Skeleton } from '../components/Skeleton';
import { ErrorBanner } from '../components/ErrorBanner';
import {
  ShieldAlert,
  Users,
  AlertOctagon,
  RotateCcw,
  CheckCircle,
  XCircle,
  FileText,
  FileSpreadsheet,
  FileImage,
  FileCode,
  File,
  Filter,
  BarChart3,
} from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function getFileIcon(kind: DocumentKind) {
  switch (kind) {
    case 'pdf':
      return <FileText className="text-red-500" size={16} aria-hidden="true" />;
    case 'csv':
      return <FileSpreadsheet className="text-green-600" size={16} aria-hidden="true" />;
    case 'image':
      return <FileImage className="text-blue-500" size={16} aria-hidden="true" />;
    case 'text':
      return <FileCode className="text-amber-500" size={16} aria-hidden="true" />;
    default:
      return <File className="text-text-muted" size={16} aria-hidden="true" />;
  }
}

export const AdminDashboardPage: React.FC = () => {
  const [periodDays, setPeriodDays] = useState<number>(7);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [queries, setQueries] = useState<AdminQueryLog[]>([]);
  const [uploads, setUploads] = useState<AdminUploadItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries pagination & filters
  const [isLoadingMoreQueries, setIsLoadingMoreQueries] = useState<boolean>(false);
  const [hasMoreQueries, setHasMoreQueries] = useState<boolean>(true);
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'answered' | 'refused'>('all');
  const [eventFilter, setEventFilter] = useState<'all' | 'ask' | 'search'>('all');

  // Chart fallback view
  const [showChartTableFallback, setShowChartTableFallback] = useState<boolean>(false);

  // Auto-refresh 10s
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState<boolean>(false);
  const autoRefreshTimerRef = useRef<number | null>(null);

  const fetchDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    setErrorMessage(null);

    try {
      const [sumData, qData, uData] = await Promise.all([
        api.getAdminAuditSummary(periodDays),
        api.getAdminQueries(50),
        api.getAdminUploads(),
      ]);

      setSummary(sumData);
      setQueries(qData);
      setUploads(uData);
      setHasMoreQueries(qData.length === 50);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to load admin monitoring data.');
      }
    } finally {
      if (!isSilent) setIsLoading(false);
    }
  }, [periodDays]);

  // Load on mount and period change
  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Handle 10-second auto-refresh
  useEffect(() => {
    if (autoRefreshEnabled) {
      autoRefreshTimerRef.current = window.setInterval(() => {
        fetchDashboardData(true);
      }, 10000);
    } else {
      if (autoRefreshTimerRef.current !== null) {
        clearInterval(autoRefreshTimerRef.current);
        autoRefreshTimerRef.current = null;
      }
    }

    return () => {
      if (autoRefreshTimerRef.current !== null) {
        clearInterval(autoRefreshTimerRef.current);
        autoRefreshTimerRef.current = null;
      }
    };
  }, [autoRefreshEnabled, fetchDashboardData]);

  // Cursor pagination for queries
  const handleLoadMoreQueries = async () => {
    if (queries.length === 0 || isLoadingMoreQueries) return;
    setIsLoadingMoreQueries(true);
    const oldestTimestamp = queries[queries.length - 1].time;

    try {
      const olderQueries = await api.getAdminQueries(50, oldestTimestamp);
      if (olderQueries.length === 0) {
        setHasMoreQueries(false);
      } else {
        setQueries((prev) => [...prev, ...olderQueries]);
        setHasMoreQueries(olderQueries.length === 50);
      }
    } catch (err) {
      // Silently stop pagination or set hasMore false
      setHasMoreQueries(false);
    } finally {
      setIsLoadingMoreQueries(false);
    }
  };

  // Filtered queries list
  const filteredQueries = queries.filter((q) => {
    if (outcomeFilter === 'answered' && q.refused === true) return false;
    if (outcomeFilter === 'refused' && q.refused !== true) return false;
    if (eventFilter !== 'all' && q.event_type !== eventFilter) return false;
    return true;
  });

  // Calculate SVG Chart Dimensions & Data
  const series = summary?.per_day_series || [];
  const maxAskRefuse = Math.max(
    ...series.map((s) => Math.max(s.asks, s.refusals)),
    5
  );

  const chartWidth = 700;
  const chartHeight = 180;
  const paddingX = 40;
  const paddingY = 25;
  const innerWidth = chartWidth - paddingX * 2;
  const innerHeight = chartHeight - paddingY * 2;

  const getX = (idx: number, count: number) => {
    if (count <= 1) return paddingX + innerWidth / 2;
    return paddingX + (idx / (count - 1)) * innerWidth;
  };

  const getY = (val: number) => {
    return paddingY + innerHeight - (val / maxAskRefuse) * innerHeight;
  };

  const asksPath = series.length > 0
    ? series
        .map((s, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx, series.length)} ${getY(s.asks)}`)
        .join(' ')
    : '';

  const refusedPath = series.length > 0
    ? series
        .map((s, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx, series.length)} ${getY(s.refusals)}`)
        .join(' ')
    : '';

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full overflow-y-auto px-4 py-6 items-center min-w-0">
        <div className="w-full max-w-6xl space-y-6">
          {/* Header & Controls */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
            <div>
              <div className="flex items-center gap-2">
                <ShieldAlert className="text-accent" size={22} aria-hidden="true" />
                <h1 className="text-xl font-bold tracking-tight text-text">Admin Dashboard</h1>
              </div>
              <p className="text-xs text-text-muted mt-1">
                Audit overview, system performance, access control enforcement, and uploads.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Period selector */}
              <div className="flex items-center rounded-btn border border-border bg-surface p-0.5 text-xs">
                {[1, 7, 30].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setPeriodDays(d)}
                    className={`rounded-btn px-2.5 py-1 font-semibold transition-colors ${
                      periodDays === d
                        ? 'bg-accent text-accent-contrast shadow-xs'
                        : 'text-text-muted hover:text-text'
                    }`}
                    data-testid={`period-selector-${d}`}
                  >
                    {d} {d === 1 ? 'day' : 'days'}
                  </button>
                ))}
              </div>

              {/* 10s Auto-refresh toggle */}
              <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoRefreshEnabled}
                  onChange={(e) => setAutoRefreshEnabled(e.target.checked)}
                  className="h-3.5 w-3.5 rounded border-border text-accent focus:ring-accent"
                  data-testid="admin-auto-refresh-toggle"
                />
                <span>Auto-refresh (10s)</span>
              </label>

              {/* Refresh button */}
              <button
                type="button"
                onClick={() => fetchDashboardData()}
                disabled={isLoading}
                className="inline-flex items-center gap-1.5 rounded-btn border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text hover:bg-surface-raised transition-colors disabled:opacity-40"
                data-testid="admin-refresh-button"
              >
                <RotateCcw size={13} className={isLoading ? 'animate-spin' : ''} aria-hidden="true" />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <ErrorBanner
              message={errorMessage}
              onRetry={() => fetchDashboardData()}
              onDismiss={() => setErrorMessage(null)}
            />
          )}

          {/* Skeletons while initial loading */}
          {isLoading && !summary && (
            <div className="space-y-4 pt-2" aria-live="polite">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-24 w-full" />
                ))}
              </div>
              <Skeleton className="h-60 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}

          {summary && (
            <>
              {/* 1. Top KPI Tiles */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {/* Total Asks */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-total-asks"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Total Asks
                  </span>
                  <div className="text-xl font-bold text-text">{summary.totals.asks}</div>
                  <div className="text-[10px] text-text-muted">
                    +{summary.totals.searches} direct searches
                  </div>
                </div>

                {/* Refusal Rate */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-refusal-rate"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Refusal Rate
                  </span>
                  <div className="text-xl font-bold text-text">
                    {(summary.totals.refusal_rate * 100).toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-text-muted">
                    {summary.totals.refusals} queries refused
                  </div>
                </div>

                {/* Avg Latency */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-avg-latency"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Avg Latency
                  </span>
                  <div className="text-xl font-bold text-text font-mono">
                    {Math.round(summary.totals.avg_latency_ms)} ms
                  </div>
                  <div className="text-[10px] text-text-muted">mean response time</div>
                </div>

                {/* P95 Latency */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-p95-latency"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    P95 Latency
                  </span>
                  <div className="text-xl font-bold text-text font-mono">
                    {Math.round(summary.totals.p95_latency_ms)} ms
                  </div>
                  <div className="text-[10px] text-text-muted">95th percentile</div>
                </div>

                {/* Total Uploads */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-uploads"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Uploads
                  </span>
                  <div className="text-xl font-bold text-text">{summary.totals.uploads}</div>
                  <div className="text-[10px] text-text-muted">files ingested</div>
                </div>

                {/* Active Users */}
                <div
                  className="rounded-card border border-border bg-surface p-3.5 shadow-xs space-y-1"
                  data-testid="kpi-active-users"
                >
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                    Active Users
                  </span>
                  <div className="text-xl font-bold text-text">{summary.totals.active_users}</div>
                  <div className="text-[10px] text-text-muted">in last {periodDays} days</div>
                </div>
              </div>

              {/* 2. Asks per day with Refused overlay Chart */}
              <div className="rounded-card border border-border bg-surface p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BarChart3 size={16} className="text-accent" aria-hidden="true" />
                    <h2 className="text-sm font-semibold text-text">Activity Overview (Per Day)</h2>
                  </div>

                  <div className="flex items-center gap-4 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-accent" />
                      <span className="text-text-muted">Asks</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                      <span className="text-text-muted">Refused</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowChartTableFallback(!showChartTableFallback)}
                      className="text-accent underline text-xs ml-2 hover:text-accent-hover"
                      data-testid="toggle-chart-table-button"
                    >
                      {showChartTableFallback ? 'Show chart view' : 'Show accessible table view'}
                    </button>
                  </div>
                </div>

                {/* Accessible Table Fallback */}
                {showChartTableFallback ? (
                  <div className="overflow-x-auto rounded border border-border bg-background p-2">
                    <table
                      className="w-full text-left text-xs"
                      aria-label="Daily asks and refusals activity table"
                    >
                      <thead className="border-b border-border text-text-muted">
                        <tr>
                          <th className="py-2 px-3">Date</th>
                          <th className="py-2 px-3">Asks</th>
                          <th className="py-2 px-3">Refusals</th>
                          <th className="py-2 px-3">Searches</th>
                          <th className="py-2 px-3">Uploads</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {series.map((row) => (
                          <tr key={row.date} className="hover:bg-surface-raised/40">
                            <td className="py-2 px-3 font-medium text-text">{row.date}</td>
                            <td className="py-2 px-3 text-accent font-semibold">{row.asks}</td>
                            <td className="py-2 px-3 text-danger font-semibold">{row.refusals}</td>
                            <td className="py-2 px-3 text-text-muted">{row.searches}</td>
                            <td className="py-2 px-3 text-text-muted">{row.uploads}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  /* Pure Inline SVG Chart */
                  <div className="w-full overflow-x-auto">
                    <svg
                      viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                      className="w-full h-44 overflow-visible font-sans"
                      aria-label="Activity timeline chart showing daily asks and refusals"
                      role="img"
                    >
                      {/* Grid lines */}
                      {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                        const y = paddingY + innerHeight * (1 - pct);
                        const val = Math.round(maxAskRefuse * pct);
                        return (
                          <g key={pct}>
                            <line
                              x1={paddingX}
                              y1={y}
                              x2={chartWidth - paddingX}
                              y2={y}
                              stroke="currentColor"
                              strokeDasharray="3 3"
                              className="text-border"
                            />
                            <text
                              x={paddingX - 8}
                              y={y + 3}
                              textAnchor="end"
                              className="text-[9px] fill-current text-text-muted font-mono"
                            >
                              {val}
                            </text>
                          </g>
                        );
                      })}

                      {/* Asks Line & Points */}
                      {series.length > 0 && (
                        <>
                          <path
                            d={asksPath}
                            fill="none"
                            stroke="var(--color-accent, #3b82f6)"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          {series.map((s, idx) => (
                            <circle
                              key={`ask-${idx}`}
                              cx={getX(idx, series.length)}
                              cy={getY(s.asks)}
                              r="3.5"
                              fill="var(--color-accent, #3b82f6)"
                              className="hover:r-5 transition-all"
                            >
                              <title>{`${s.date}: ${s.asks} asks`}</title>
                            </circle>
                          ))}
                        </>
                      )}

                      {/* Refused Line & Points */}
                      {series.length > 0 && (
                        <>
                          <path
                            d={refusedPath}
                            fill="none"
                            stroke="#ef4444"
                            strokeWidth="2"
                            strokeDasharray="4 2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          {series.map((s, idx) => (
                            <circle
                              key={`ref-${idx}`}
                              cx={getX(idx, series.length)}
                              cy={getY(s.refusals)}
                              r="3"
                              fill="#ef4444"
                            >
                              <title>{`${s.date}: ${s.refusals} refused`}</title>
                            </circle>
                          ))}
                        </>
                      )}

                      {/* X-axis labels */}
                      {series.map((s, idx) => {
                        // Show label on every step or interval if series is large
                        if (series.length > 14 && idx % 3 !== 0) return null;
                        const x = getX(idx, series.length);
                        return (
                          <text
                            key={`lbl-${idx}`}
                            x={x}
                            y={chartHeight - 6}
                            textAnchor="middle"
                            className="text-[9px] fill-current text-text-muted"
                          >
                            {s.date.slice(5)}
                          </text>
                        );
                      })}
                    </svg>
                  </div>
                )}
              </div>

              {/* 3. Breakdown Sections: Top Users & Refusals by Reason */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Top Users */}
                <div className="rounded-card border border-border bg-surface p-4 shadow-xs space-y-3">
                  <div className="flex items-center gap-2">
                    <Users size={16} className="text-accent" aria-hidden="true" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-text">
                      Top Active Users
                    </h3>
                  </div>
                  {summary.top_users.length === 0 ? (
                    <p className="text-xs text-text-muted py-2">No user query activity recorded.</p>
                  ) : (
                    <div className="divide-y divide-border-subtle">
                      {summary.top_users.map((u, i) => (
                        <div
                          key={u.name + i}
                          className="flex items-center justify-between py-2 text-xs"
                        >
                          <span className="font-medium text-text">{u.name}</span>
                          <span className="font-mono text-text-muted bg-surface-raised px-2 py-0.5 rounded border border-border-subtle">
                            {u.count} queries
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Refusals by Reason */}
                <div className="rounded-card border border-border bg-surface p-4 shadow-xs space-y-3">
                  <div className="flex items-center gap-2">
                    <AlertOctagon size={16} className="text-danger" aria-hidden="true" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-text">
                      Refusals by Reason Code
                    </h3>
                  </div>
                  {Object.keys(summary.counts_by_reason_code).length === 0 ? (
                    <p className="text-xs text-text-muted py-2">No refusals recorded in period.</p>
                  ) : (
                    <div className="divide-y divide-border-subtle">
                      {Object.entries(summary.counts_by_reason_code).map(([code, count]) => (
                        <div key={code} className="flex items-center justify-between py-2 text-xs">
                          <span className="font-mono text-text">{code}</span>
                          <span className="font-mono text-danger bg-red-500/10 px-2 py-0.5 rounded font-semibold">
                            {count}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* 4. Recent Queries Table (Zero question text leaks) */}
              <div className="rounded-card border border-border bg-surface p-5 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-text">Recent Queries (Audit Log)</h2>
                    <p className="text-[11px] text-text-muted mt-0.5">
                      Privacy-preserving: displays question hash and length only; never logs or requests question text.
                    </p>
                  </div>

                  {/* Filters for outcome and event */}
                  <div className="flex items-center gap-2 text-xs">
                    <div className="flex items-center gap-1">
                      <Filter size={13} className="text-text-muted" aria-hidden="true" />
                      <label htmlFor="outcome-filter" className="text-text-muted">
                        Outcome:
                      </label>
                      <select
                        id="outcome-filter"
                        value={outcomeFilter}
                        onChange={(e) =>
                          setOutcomeFilter(e.target.value as 'all' | 'answered' | 'refused')
                        }
                        className="rounded-input border border-border bg-surface px-2 py-1 text-xs text-text focus:border-accent outline-none"
                        data-testid="filter-outcome-select"
                      >
                        <option value="all">All</option>
                        <option value="answered">Answered</option>
                        <option value="refused">Refused</option>
                      </select>
                    </div>

                    <div className="flex items-center gap-1">
                      <label htmlFor="event-filter" className="text-text-muted">
                        Event:
                      </label>
                      <select
                        id="event-filter"
                        value={eventFilter}
                        onChange={(e) =>
                          setEventFilter(e.target.value as 'all' | 'ask' | 'search')
                        }
                        className="rounded-input border border-border bg-surface px-2 py-1 text-xs text-text focus:border-accent outline-none"
                        data-testid="filter-event-select"
                      >
                        <option value="all">All</option>
                        <option value="ask">ask</option>
                        <option value="search">search</option>
                      </select>
                    </div>
                  </div>
                </div>

                {filteredQueries.length === 0 ? (
                  <p className="text-xs text-text-muted py-4 text-center">
                    No queries matching the current filter.
                  </p>
                ) : (
                  <div className="overflow-x-auto rounded border border-border">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-border bg-surface-raised text-text-muted font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="py-2.5 px-3">Time</th>
                          <th className="py-2.5 px-3">User</th>
                          <th className="py-2.5 px-3">Event</th>
                          <th className="py-2.5 px-3">Outcome</th>
                          <th className="py-2.5 px-3">Reason Code</th>
                          <th className="py-2.5 px-3">Latency</th>
                          <th className="py-2.5 px-3">Chunks</th>
                          <th className="py-2.5 px-3">Admin</th>
                          <th className="py-2.5 px-3">Question Hash (Len)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {filteredQueries.map((q, idx) => (
                          <tr
                            key={q.time + idx}
                            className="hover:bg-surface-raised/40 transition-colors"
                            data-testid={`query-log-row-${idx}`}
                          >
                            <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                              {formatDateTime(q.time)}
                            </td>
                            <td className="py-2.5 px-3 font-medium text-text whitespace-nowrap">
                              {q.user_name}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted whitespace-nowrap">
                              {q.event_type}
                            </td>
                            <td className="py-2.5 px-3 whitespace-nowrap">
                              {q.refused ? (
                                <span className="inline-flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-danger">
                                  <XCircle size={11} aria-hidden="true" />
                                  Refused
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                                  <CheckCircle size={11} aria-hidden="true" />
                                  Answered
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted whitespace-nowrap">
                              {q.reason_code || '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted whitespace-nowrap">
                              {q.latency_ms !== null ? `${Math.round(q.latency_ms)} ms` : '—'}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted whitespace-nowrap">
                              {q.chunk_count !== null ? q.chunk_count : '—'}
                            </td>
                            <td className="py-2.5 px-3 whitespace-nowrap">
                              {q.admin_access ? (
                                <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-bold text-accent">
                                  YES
                                </span>
                              ) : (
                                <span className="text-text-muted text-[11px]">No</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted whitespace-nowrap">
                              {q.question_hash ? (
                                <span title={`Hash: ${q.question_hash}`}>
                                  {q.question_hash.slice(0, 8)}... ({q.question_length || 0} chars)
                                </span>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Load More Button */}
                {hasMoreQueries && (
                  <div className="flex justify-center pt-2">
                    <button
                      type="button"
                      onClick={handleLoadMoreQueries}
                      disabled={isLoadingMoreQueries}
                      className="rounded-btn border border-border bg-surface px-4 py-2 text-xs font-semibold text-text hover:bg-surface-raised transition-colors disabled:opacity-40"
                      data-testid="load-more-queries-button"
                    >
                      {isLoadingMoreQueries ? 'Loading older queries...' : 'Load more'}
                    </button>
                  </div>
                )}
              </div>

              {/* 5. Uploads Management Table */}
              <div className="rounded-card border border-border bg-surface p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-text">All Uploaded Documents</h2>
                    <p className="text-[11px] text-text-muted mt-0.5">
                      Platform-wide document audit including active and deleted entries.
                    </p>
                  </div>
                  <span className="text-xs font-mono text-text-muted">
                    Total: {uploads.length} files
                  </span>
                </div>

                {uploads.length === 0 ? (
                  <p className="text-xs text-text-muted py-4 text-center">No uploads recorded yet.</p>
                ) : (
                  <div className="overflow-x-auto rounded border border-border">
                    <table className="w-full text-left text-xs">
                      <thead className="border-b border-border bg-surface-raised text-text-muted font-semibold uppercase tracking-wider">
                        <tr>
                          <th className="py-2.5 px-3">File</th>
                          <th className="py-2.5 px-3">Owner</th>
                          <th className="py-2.5 px-3">Kind</th>
                          <th className="py-2.5 px-3">Size</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3">Shared Count</th>
                          <th className="py-2.5 px-3">Deleted</th>
                          <th className="py-2.5 px-3">Uploaded</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {uploads.map((doc) => (
                          <tr
                            key={doc.id}
                            className="hover:bg-surface-raised/40 transition-colors"
                            data-testid={`admin-upload-row-${doc.id}`}
                          >
                            <td className="py-2.5 px-3 font-medium text-text">
                              <div className="flex items-center gap-1.5 max-w-xs truncate">
                                {getFileIcon(doc.kind)}
                                <span className="truncate" title={doc.filename}>
                                  {doc.filename}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                              {doc.owner.name}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-[11px] text-text-muted uppercase whitespace-nowrap">
                              {doc.kind}
                            </td>
                            <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                              {formatBytes(doc.size_bytes)}
                            </td>
                            <td className="py-2.5 px-3 whitespace-nowrap">
                              <span
                                className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                                  doc.status === 'ready'
                                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                                    : doc.status === 'processing'
                                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                                    : doc.status === 'queued'
                                    ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                                    : 'bg-red-500/10 text-red-600 dark:text-red-400'
                                }`}
                              >
                                {doc.status}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-text-muted font-mono whitespace-nowrap">
                              {doc.shared_with_count}
                            </td>
                            <td className="py-2.5 px-3 whitespace-nowrap">
                              {doc.deleted ? (
                                <span className="rounded bg-red-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger">
                                  DELETED
                                </span>
                              ) : (
                                <span className="text-text-muted text-[11px]">Active</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-text-muted whitespace-nowrap">
                              {formatDateTime(doc.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
