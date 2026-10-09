import { HighlightSpan } from '../api/types';

export interface TextSegment {
  text: string;
  isHighlighted: boolean;
}

/**
 * Splits source text into highlighted and plain segments based on character offset spans.
 *
 * Requirements:
 * - Robust: Never throws on negative, reversed, empty, or out-of-bounds offsets.
 * - Merges overlapping and abutting ranges.
 * - Correctly handles Unicode characters.
 */
export function splitHighlightedText(
  text: string,
  highlights: HighlightSpan[] = []
): TextSegment[] {
  if (!text) return [];
  if (!highlights || highlights.length === 0) {
    return [{ text, isHighlighted: false }];
  }

  const textLength = text.length;

  // 1. Sanitize & clamp ranges
  const validRanges: HighlightSpan[] = [];
  for (const h of highlights) {
    if (typeof h.start !== 'number' || typeof h.end !== 'number') continue;
    if (isNaN(h.start) || isNaN(h.end)) continue;

    // Normalize start/end if reversed
    const rawStart = Math.min(h.start, h.end);
    const rawEnd = Math.max(h.start, h.end);

    const start = Math.max(0, Math.min(textLength, rawStart));
    const end = Math.max(0, Math.min(textLength, rawEnd));

    if (start < end) {
      validRanges.push({ start, end });
    }
  }

  if (validRanges.length === 0) {
    return [{ text, isHighlighted: false }];
  }

  // 2. Sort by start ascending, then end descending
  validRanges.sort((a, b) => a.start - b.start || b.end - a.end);

  // 3. Merge overlapping and adjacent ranges
  const merged: HighlightSpan[] = [validRanges[0]];
  for (let i = 1; i < validRanges.length; i++) {
    const current = validRanges[i];
    const prev = merged[merged.length - 1];

    if (current.start <= prev.end) {
      // Overlap or abutting -> extend previous end
      prev.end = Math.max(prev.end, current.end);
    } else {
      merged.push({ ...current });
    }
  }

  // 4. Construct segments
  const segments: TextSegment[] = [];
  let currentIndex = 0;

  for (const span of merged) {
    if (span.start > currentIndex) {
      segments.push({
        text: text.slice(currentIndex, span.start),
        isHighlighted: false,
      });
    }

    segments.push({
      text: text.slice(span.start, span.end),
      isHighlighted: true,
    });

    currentIndex = span.end;
  }

  if (currentIndex < textLength) {
    segments.push({
      text: text.slice(currentIndex),
      isHighlighted: false,
    });
  }

  return segments;
}
