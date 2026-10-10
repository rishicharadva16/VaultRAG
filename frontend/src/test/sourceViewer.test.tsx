import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CitationPanel, clearCitationViewCache } from '../components/CitationPanel';
import { CitationItem, SourceViewResponse, SourcePagesResponse } from '../api/types';

describe('Source Viewer Component (CitationPanel)', () => {
  const originalFetch = globalThis.fetch;

  const mockCitation1: CitationItem = {
    id: 1,
    chunk_id: 'pdf:contracts.pdf:p2:c1',
    source_id: 'pdf:contracts.pdf',
    file: 'contracts.pdf',
    page: 2,
    snippet: 'The annual maintenance fee is $45,000.',
    highlights: [{ start: 0, end: 38 }],
    highlight_text: 'The annual maintenance fee is $45,000.',
  };

  const mockCitation2: CitationItem = {
    id: 2,
    chunk_id: 'pdf:contracts.pdf:p3:c1',
    source_id: 'pdf:contracts.pdf',
    file: 'contracts.pdf',
    page: 3,
    snippet: 'Payment shall be made within thirty days.',
    highlights: [{ start: 0, end: 40 }],
    highlight_text: 'Payment shall be made within thirty days.',
  };

  const mockViewResponsePdf: SourceViewResponse = {
    kind: 'pdf_text',
    file: 'contracts.pdf',
    page: 2,
    row_id: null,
    page_width: 612,
    page_height: 792,
    rects: [{ x: 0.125, y: 0.35, w: 0.55, h: 0.025 }],
    match: 'exact',
    text: 'The annual maintenance fee is $45,000 payable on invoice.',
    page_image_url: '/source/pdf:contracts.pdf:p2:c1/page.png',
  };

  const mockPagesResponse: SourcePagesResponse = {
    page_count: 5,
    readable_pages: [1, 2, 3],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    clearCitationViewCache();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:http://localhost/fake-blob');
    globalThis.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('1. calculates overlay positioning percentages correctly from normalized rects', async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/view')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockViewResponsePdf,
        } as Response;
      }
      if (url.includes('/pages')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockPagesResponse,
        } as Response;
      }
      if (url.includes('/page.png')) {
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob(['fake-img'], { type: 'image/png' }),
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(
      <CitationPanel
        citation={mockCitation1}
        onClose={vi.fn()}
      />
    );

    // Wait for the highlight rect to render
    const rectEl = await screen.findByTestId('highlight-rect');
    expect(rectEl).toBeInTheDocument();

    // Verify percentages: x=0.125 -> 12.5%, y=0.35 -> 35%, w=0.55 -> 55%, h=0.025 -> 2.5%
    expect(rectEl.style.left).toBe('12.5%');
    expect(rectEl.style.top).toBe('35%');
    expect(rectEl.style.width).toBe('55%');
    expect(rectEl.style.height).toBe('2.5%');
  });

  it('2. automatically falls back to text view when match is "none"', async () => {
    const noneMatchResponse = {
      ...mockViewResponsePdf,
      rects: [],
      match: 'none',
    };

    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/view')) {
        return {
          ok: true,
          status: 200,
          json: async () => noneMatchResponse,
        } as Response;
      }
      if (url.includes('/pages')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockPagesResponse,
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(
      <CitationPanel
        citation={{ ...mockCitation1, chunk_id: 'pdf:contracts.pdf:p2:c_none' }}
        onClose={vi.fn()}
      />
    );

    // Text view should be active automatically
    await waitFor(() => {
      expect(screen.getByTestId('chunk-text-view')).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Document layout coordinates unavailable for this segment/i)
    ).toBeInTheDocument();
  });

  it('3. revokes created blob URLs on unmount/close to prevent memory leaks', async () => {
    const fakeBlobUrl = 'blob:http://localhost/test-blob-uuid-3';
    (globalThis.URL.createObjectURL as any).mockReturnValue(fakeBlobUrl);
    const revokeMock = vi.fn();
    globalThis.URL.revokeObjectURL = revokeMock;

    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/view')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockViewResponsePdf,
        } as Response;
      }
      if (url.includes('/pages')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockPagesResponse,
        } as Response;
      }
      if (url.includes('/page.png')) {
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob(['fake-img'], { type: 'image/png' }),
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    const { unmount } = render(
      <CitationPanel
        citation={{ ...mockCitation1, chunk_id: 'pdf:contracts.pdf:p2:c_revoke' }}
        onClose={vi.fn()}
      />
    );

    // Wait for blob creation
    await waitFor(() => {
      expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    });

    // Unmount component (simulating close)
    unmount();

    expect(revokeMock).toHaveBeenCalledWith(fakeBlobUrl);
  });

  it('4. navigates to next and previous citations when buttons are clicked', async () => {
    globalThis.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes('/view')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockViewResponsePdf,
        } as Response;
      }
      if (url.includes('/pages')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockPagesResponse,
        } as Response;
      }
      if (url.includes('/page.png')) {
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob(['fake-img'], { type: 'image/png' }),
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    const onNavigate = vi.fn();
    const citations = [mockCitation1, mockCitation2];

    const { rerender } = render(
      <CitationPanel
        citation={mockCitation1}
        citations={citations}
        currentIndex={0}
        onNavigate={onNavigate}
        onClose={vi.fn()}
      />
    );

    // Citation 1 of 2 indicator
    expect(screen.getByText('1 of 2')).toBeInTheDocument();

    const prevButton = screen.getByRole('button', { name: /previous citation/i });
    const nextButton = screen.getByRole('button', { name: /next citation/i });

    // Prev should be disabled at index 0
    expect(prevButton).toBeDisabled();
    expect(nextButton).not.toBeDisabled();

    // Click Next
    fireEvent.click(nextButton);
    expect(onNavigate).toHaveBeenCalledWith(mockCitation2, 1);

    // Re-render as index 1
    rerender(
      <CitationPanel
        citation={mockCitation2}
        citations={citations}
        currentIndex={1}
        onNavigate={onNavigate}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('2 of 2')).toBeInTheDocument();
    const nextButtonAfter = screen.getByRole('button', { name: /next citation/i });
    expect(nextButtonAfter).toBeDisabled();
  });

  it('5. triggers onClose when Escape key is pressed', () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    });

    const onClose = vi.fn();
    render(
      <CitationPanel
        citation={mockCitation1}
        onClose={onClose}
      />
    );

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('6. displays identical "This source is no longer available." error on 404 response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Chunk not found' }),
    });

    render(
      <CitationPanel
        citation={{ ...mockCitation1, chunk_id: 'pdf:contracts.pdf:p2:c_404' }}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('citation-error')).toBeInTheDocument();
    });

    expect(screen.getByText('This source is no longer available.')).toBeInTheDocument();
  });
});
