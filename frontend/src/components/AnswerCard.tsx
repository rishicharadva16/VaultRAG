import React, { useState } from 'react';
import { AskResponse, CitationItem } from '../api/types';
import { parseAnswer } from '../lib/parseAnswer';
import { CitationChip } from './CitationChip';
import { ShieldCheck, Copy, Check, Clock } from 'lucide-react';
import { formatLatency } from '../lib/format';

interface AnswerCardProps {
  response: AskResponse;
  latencyMs?: number;
  selectedCitationId?: number | null;
  onSelectCitation: (citation: CitationItem) => void;
  className?: string;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({
  response,
  latencyMs,
  selectedCitationId,
  onSelectCitation,
  className = '',
}) => {
  const [copied, setCopied] = useState(false);

  const citationMap = new Map<number, CitationItem>();
  for (const c of response.citations) {
    citationMap.set(c.id, c);
  }

  const validIds = new Set(citationMap.keys());
  const parsedSegments = parseAnswer(response.answer, validIds);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(response.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <article
      className={`rounded-card border border-border bg-surface p-4 transition-colors space-y-4 shadow-xs ${className}`}
      data-testid="answer-card"
    >
      {/* Top Header: Verification & Meta */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2">
          {response.verified ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-badge border border-emerald-300 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
              data-testid="verified-badge"
            >
              <ShieldCheck size={14} className="text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span>Verified Answer</span>
            </span>
          ) : (
            <span className="text-xs font-medium text-text-muted">Unverified Response</span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs text-text-muted">
          {latencyMs !== undefined && (
            <span className="flex items-center gap-1">
              <Clock size={12} aria-hidden="true" />
              <span>{formatLatency(latencyMs)}</span>
            </span>
          )}
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy plain answer text"
            className="flex items-center gap-1 rounded-btn px-2 py-1 text-xs font-medium text-text-muted hover:bg-surface-raised hover:text-text transition-colors"
          >
            {copied ? (
              <>
                <Check size={13} className="text-success" aria-hidden="true" />
                <span className="text-success">Copied</span>
              </>
            ) : (
              <>
                <Copy size={13} aria-hidden="true" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Answer Body - Strictly Plain Text with Interactive Citation Markers */}
      <div
        className="text-sm font-normal text-text leading-relaxed whitespace-pre-wrap"
        data-testid="answer-text"
      >
        {parsedSegments.map((seg, idx) => {
          if (seg.type === 'text') {
            // Rendered strictly as text node - safe from XSS, no markdown / HTML execution
            return <React.Fragment key={idx}>{seg.content}</React.Fragment>;
          }

          const citation = citationMap.get(seg.citationId);
          if (!citation) {
            return <React.Fragment key={idx}>{seg.raw}</React.Fragment>;
          }

          return (
            <CitationChip
              key={idx}
              citation={citation}
              variant="marker"
              isSelected={selectedCitationId === citation.id}
              onClick={onSelectCitation}
            />
          );
        })}
      </div>

      {/* Sources List */}
      {response.citations.length > 0 && (
        <div className="border-t border-border-subtle pt-3 space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Sources ({response.citations.length})
          </div>
          <div className="flex flex-wrap gap-2" data-testid="sources-list">
            {response.citations.map((cit) => (
              <CitationChip
                key={cit.id}
                citation={cit}
                variant="source"
                isSelected={selectedCitationId === cit.id}
                onClick={onSelectCitation}
              />
            ))}
          </div>
        </div>
      )}
    </article>
  );
};
