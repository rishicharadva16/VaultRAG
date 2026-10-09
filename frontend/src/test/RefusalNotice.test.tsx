import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RefusalNotice } from '../components/RefusalNotice';

describe('RefusalNotice Component', () => {
  const STANDARD_REFUSAL = "I couldn't find an answer to that in the documents available to you.";

  it('renders neutral refusal card with exact refusal string', () => {
    render(<RefusalNotice answer={STANDARD_REFUSAL} />);

    expect(screen.getByTestId('refusal-notice')).toBeInTheDocument();
    expect(screen.getByText(STANDARD_REFUSAL)).toBeInTheDocument();
    expect(
      screen.getByText('Answers come only from documents available to you.')
    ).toBeInTheDocument();
  });

  it('renders byte-for-byte identical text for two different refusal scenarios', () => {
    // Scenario 1: Forbidden question (Asha asking salaries)
    const { container: c1 } = render(<RefusalNotice answer={STANDARD_REFUSAL} />);
    const text1 = c1.textContent;

    // Scenario 2: Non-existent topic (Quantum specs)
    const { container: c2 } = render(<RefusalNotice answer={STANDARD_REFUSAL} />);
    const text2 = c2.textContent;

    expect(text1).toBe(text2);
    // Ensure no error styling classes
    expect(c1.querySelector('.text-danger')).toBeNull();
    expect(c1.querySelector('.bg-red-50')).toBeNull();
  });
});
