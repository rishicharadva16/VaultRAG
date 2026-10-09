import { describe, it, expect } from 'vitest';
import { parseAnswer } from '../lib/parseAnswer';

describe('parseAnswer', () => {
  it('parses single citation marker [1]', () => {
    const answer = 'The monthly service fee is Rs 4,00,000 [1].';
    const validIds = new Set([1]);

    const segments = parseAnswer(answer, validIds);

    expect(segments).toEqual([
      { type: 'text', content: 'The monthly service fee is Rs 4,00,000 ' },
      { type: 'citation', citationId: 1, raw: '[1]' },
      { type: 'text', content: '.' },
    ]);
  });

  it('parses adjacent citation markers [1][2]', () => {
    const answer = 'Approval requires dual authorization [1][2].';
    const validIds = new Set([1, 2]);

    const segments = parseAnswer(answer, validIds);

    expect(segments).toEqual([
      { type: 'text', content: 'Approval requires dual authorization ' },
      { type: 'citation', citationId: 1, raw: '[1]' },
      { type: 'citation', citationId: 2, raw: '[2]' },
      { type: 'text', content: '.' },
    ]);
  });

  it('parses comma-separated citation markers [1, 2]', () => {
    const answer = 'Invoices must be submitted by the 5th [1, 2].';
    const validIds = new Set([1, 2]);

    const segments = parseAnswer(answer, validIds);

    expect(segments).toEqual([
      { type: 'text', content: 'Invoices must be submitted by the 5th ' },
      { type: 'citation', citationId: 1, raw: '[1]' },
      { type: 'text', content: ', ' },
      { type: 'citation', citationId: 2, raw: '[2]' },
      { type: 'text', content: '.' },
    ]);
  });

  it('keeps unknown markers as plain text', () => {
    const answer = 'Found in document [99] and section [3].';
    // Only 3 is valid, 99 is not in validIds
    const validIds = new Set([3]);

    const segments = parseAnswer(answer, validIds);

    expect(segments).toEqual([
      { type: 'text', content: 'Found in document [99] and section ' },
      { type: 'citation', citationId: 3, raw: '[3]' },
      { type: 'text', content: '.' },
    ]);
  });

  it('handles text without any citation markers', () => {
    const answer = 'I could not find an answer to that.';
    const segments = parseAnswer(answer, new Set([1]));

    expect(segments).toEqual([{ type: 'text', content: answer }]);
  });
});
