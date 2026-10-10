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
      className={`relative rounded-card border border-border bg-surface p-5 transition-all shadow-soft space-y-4 before:content-[""] before:absolute before:left-0 before:top-3 before:bottom-3 before:w-1.5 before:rounded-r before:bg-brand-gradient ${className}`}
      data-testid="answer-card"
    >
      {/* Top Header Row: Verified Answer pill, Response time chip, Copy button */}
      <div className="flex items-center justify-between border-b border-border-subtle pb-3">
        <div className="flex items-center gap-2">
          {response.verified ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-badge border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300"
              data-testid="verified-badge"
            >
              <ShieldCheck size={14} className="text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span>Verified Answer</span>
            </span>
          ) : (
            <span className="text-xs font-medium text-text-muted">Grounded Response</span>
          )}
        </div>

        <div className="flex items-center gap-2.5 text-xs text-text-muted">
          {latencyMs !== undefined && (
            <span className="flex items-center gap-1 bg-surface-2 px-2 py-0.5 rounded-btn border border-border text-[11px] font-mono">
              <Clock size={11} aria-hidden="true" />
              <span>{formatLatency(latencyMs)}</span>
            </span>
          )}
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy plain answer text"
            className="flex items-center gap-1.5 rounded-btn px-2.5 py-1 text-xs font-semibold text-text-muted hover:bg-surface-2 hover:text-text transition-colors min-h-[32px]"
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
        className="text-sm sm:text-base font-normal text-text leading-relaxed whitespace-pre-wrap"
        data-testid="answer-text"
      >
        {parsedSegments.map((seg, idx) => {
          if (seg.type === 'text') {
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

      {/* Sources Section */}
      {response.citations.length > 0 && (
        <div className="border-t border-border-subtle pt-3.5 space-y-2.5">
          <div className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
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
