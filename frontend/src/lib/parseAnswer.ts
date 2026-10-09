export type AnswerSegment =
  | { type: 'text'; content: string }
  | { type: 'citation'; citationId: number; raw: string };

/**
 * Parses an untrusted LLM answer string into safe text and citation marker segments.
 *
 * Requirements:
 * - Only markers whose `n` matches a returned citation ID are turned into citations.
 * - Handles single markers [1], adjacent markers [1][2], and comma-separated markers [1, 2].
 * - Unmatched markers remain as plain text.
 * - No HTML or markdown is evaluated.
 */
export function parseAnswer(answer: string, validCitationIds: Set<number> | number[]): AnswerSegment[] {
  if (!answer) return [];

  const validSet = validCitationIds instanceof Set ? validCitationIds : new Set(validCitationIds);
  const segments: AnswerSegment[] = [];

  // Matches bracketed numbers like [1] or comma-separated lists [1, 2] or [1,2,3]
  const markerRegex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = markerRegex.exec(answer)) !== null) {
    const matchStart = match.index;
    const matchEnd = markerRegex.lastIndex;
    const fullMatchText = match[0];
    const innerContent = match[1];

    // Push leading text before this marker
    if (matchStart > lastIndex) {
      segments.push({
        type: 'text',
        content: answer.slice(lastIndex, matchStart),
      });
    }

    // Split inner numbers by comma
    const rawNums = innerContent.split(',').map((s) => s.trim());
    const parsedNums = rawNums.map((s) => parseInt(s, 10));

    // Check if at least one number in this bracket is valid
    const anyValid = parsedNums.some((num) => validSet.has(num));

    if (!anyValid) {
      // If none of the numbers are valid citations, keep entire bracket as plain text
      segments.push({
        type: 'text',
        content: fullMatchText,
      });
    } else {
      // If there are multiple numbers in bracket, process each
      for (let i = 0; i < parsedNums.length; i++) {
        const num = parsedNums[i];
        if (validSet.has(num)) {
          segments.push({
            type: 'citation',
            citationId: num,
            raw: `[${num}]`,
          });
        } else {
          segments.push({
            type: 'text',
            content: `[${num}]`,
          });
        }

        if (i < parsedNums.length - 1) {
          segments.push({
            type: 'text',
            content: ', ',
          });
        }
      }
    }

    lastIndex = matchEnd;
  }

  // Push remaining trailing text
  if (lastIndex < answer.length) {
    segments.push({
      type: 'text',
      content: answer.slice(lastIndex),
    });
  }

  // Merge adjacent text segments
  const merged: AnswerSegment[] = [];
  for (const seg of segments) {
    if (seg.type === 'text') {
      const prev = merged[merged.length - 1];
      if (prev && prev.type === 'text') {
        prev.content += seg.content;
      } else {
        merged.push({ ...seg });
      }
    } else {
      merged.push(seg);
    }
  }

  return merged;
}
