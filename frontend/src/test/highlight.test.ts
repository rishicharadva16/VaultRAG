import { describe, it, expect } from 'vitest';
import { splitHighlightedText } from '../lib/highlight';

describe('splitHighlightedText', () => {
  it('handles normal single and multiple non-overlapping ranges', () => {
    const text = 'The monthly subscription fee is 12,500 payable on the 1st of each month.';
    const highlights = [
      { start: 32, end: 38 }, // "12,500"
      { start: 54, end: 57 }, // "1st"
    ];

    const segments = splitHighlightedText(text, highlights);

    expect(segments).toEqual([
      { text: 'The monthly subscription fee is ', isHighlighted: false },
      { text: '12,500', isHighlighted: true },
      { text: ' payable on the ', isHighlighted: false },
      { text: '1st', isHighlighted: true },
      { text: ' of each month.', isHighlighted: false },
    ]);
  });

  it('merges overlapping and adjacent ranges correctly', () => {
    const text = 'Notice period for all employees is sixty days.';
    // Overlapping: [0, 13] ("Notice period") and [7, 20] ("period for all")
    // Abutting: [20, 25] (" empl")
    const highlights = [
      { start: 7, end: 20 },
      { start: 0, end: 13 },
      { start: 20, end: 25 },
    ];

    const segments = splitHighlightedText(text, highlights);

    expect(segments).toEqual([
      { text: text.slice(0, 25), isHighlighted: true },
      { text: text.slice(25), isHighlighted: false },
    ]);
  });

  it('safely handles out-of-bounds, negative, and inverted offsets without throwing', () => {
    const text = 'Confidential data.';
    const highlights = [
      { start: -10, end: 5 }, // clamped start 0..5
      { start: 20, end: 10 }, // reversed -> [10, 18] clamped
      { start: 50, end: 100 }, // beyond text length -> clamped to 18..18 -> dropped
    ];

    expect(() => splitHighlightedText(text, highlights)).not.toThrow();

    const segments = splitHighlightedText(text, highlights);
    expect(segments.length).toBeGreaterThan(0);
    // Total reconstructed text must match original
    expect(segments.map((s) => s.text).join('')).toBe(text);
  });

  it('handles empty highlights, empty text, and zero-width spans', () => {
    expect(splitHighlightedText('', [{ start: 0, end: 5 }])).toEqual([]);
    expect(splitHighlightedText('Hello world', [])).toEqual([
      { text: 'Hello world', isHighlighted: false },
    ]);
    expect(splitHighlightedText('Hello world', [{ start: 5, end: 5 }])).toEqual([
      { text: 'Hello world', isHighlighted: false },
    ]);
  });

  it('correctly slices unicode and multi-byte text', () => {
    const text = 'कर्मचारी वेतन Rs 9,49,320 🚀 approved';
    // Match "Rs 9,49,320"
    const start = text.indexOf('Rs');
    const end = start + 'Rs 9,49,320'.length;

    const segments = splitHighlightedText(text, [{ start, end }]);
    expect(segments.find((s) => s.isHighlighted)?.text).toBe('Rs 9,49,320');
    expect(segments.map((s) => s.text).join('')).toBe(text);
  });
});
