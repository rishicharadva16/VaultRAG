import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AnswerCard } from '../components/AnswerCard';
import { AskResponse, CitationItem } from '../api/types';

describe('AnswerCard Component', () => {
  const mockCitation: CitationItem = {
    id: 1,
    chunk_id: 'hr_policy-p2-c1',
    source_id: 'pdf:hr_policy.pdf',
    file: 'hr_policy.pdf',
    page: 2,
    snippet: 'Notice period is 60 days.',
    highlights: [{ start: 0, end: 24 }],
    highlight_text: 'Notice period is 60 days.',
  };

  const mockResponse: AskResponse = {
    answer: 'The notice period for employees is 60 days [1].',
    refused: false,
    verified: true,
    citations: [mockCitation],
  };

  it('renders citation markers as clickable buttons and triggers onSelectCitation', () => {
    const onSelect = vi.fn();
    render(
      <AnswerCard
        response={mockResponse}
        onSelectCitation={onSelect}
      />
    );

    // Marker button exists
    const markerButton = screen.getByRole('button', { name: /citation \[1\]/i });
    expect(markerButton).toBeInTheDocument();

    // Clicking marker triggers callback with citation
    fireEvent.click(markerButton);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(mockCitation);
  });

  it('renders verified badge when response.verified is true', () => {
    render(
      <AnswerCard
        response={mockResponse}
        onSelectCitation={vi.fn()}
      />
    );

    expect(screen.getByTestId('verified-badge')).toBeInTheDocument();
    expect(screen.getByText('Verified Answer')).toBeInTheDocument();
  });

  it('never renders HTML or executes scripts from untrusted answer text', () => {
    const maliciousResponse: AskResponse = {
      answer: '<img src=x onerror=alert(1)> <script>window.pwned=true;</script> Hello [1]',
      refused: false,
      verified: true,
      citations: [mockCitation],
    };

    const { container } = render(
      <AnswerCard
        response={maliciousResponse}
        onSelectCitation={vi.fn()}
      />
    );

    // No actual <img> or <script> DOM elements should exist
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();

    // The tags must appear strictly as plain text content
    const answerContainer = screen.getByTestId('answer-text');
    expect(answerContainer.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(answerContainer.textContent).toContain('<script>window.pwned=true;</script>');
  });
});
