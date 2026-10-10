import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DocumentsPage } from '../pages/DocumentsPage';
import { api } from '../api/client';
import * as AuthContextModule from '../auth/AuthContext';
import { DocumentItem, User } from '../api/types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('DocumentsPage Component', () => {
  const dummyUser: User = {
    id: 'u-1',
    name: 'Asha Patel',
    email: 'asha.patel@northwind.example',
    roles: ['employee'],
    employee_id: 'E1004',
    department: 'Engineering',
    external_id: 'u_asha',
  };

  const sampleDocReady: DocumentItem = {
    id: 'doc-123',
    filename: 'quarterly_report.pdf',
    kind: 'pdf',
    status: 'ready',
    reason_code: null,
    size_bytes: 1024 * 50,
    created_at: new Date().toISOString(),
    owner: { id: 'u-1', name: 'Asha Patel' },
    shared_with_count: 2,
    can_manage: true,
  };

  const sampleDocProcessing: DocumentItem = {
    id: 'doc-456',
    filename: 'policy_update.pdf',
    kind: 'pdf',
    status: 'processing',
    reason_code: null,
    size_bytes: 1024 * 10,
    created_at: new Date().toISOString(),
    owner: { id: 'u-1', name: 'Asha Patel' },
    shared_with_count: 0,
    can_manage: true,
  };

  const sampleDocXss: DocumentItem = {
    id: 'doc-789',
    filename: '<b id="injected-html">Sensitive</b>.pdf',
    kind: 'pdf',
    status: 'ready',
    reason_code: null,
    size_bytes: 2048,
    created_at: new Date().toISOString(),
    owner: { id: 'u-1', name: 'Asha Patel' },
    shared_with_count: 0,
    can_manage: true,
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    mockNavigate.mockReset();
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: dummyUser,
      isLoading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
      switchDemoUser: vi.fn(),
      clearError: vi.fn(),
      setError: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('1. validates upload file type and rejects disallowed extensions', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([sampleDocReady]);

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('quarterly_report.pdf').length).toBeGreaterThan(0);
    });

    // Pick an invalid file (e.g. .exe)
    const file = new File(['binarycontent'], 'malicious.exe', { type: 'application/x-msdownload' });
    const input = document.getElementById('file-upload-input') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [file] } });

    expect(
      screen.getByText('Unsupported file type. Allowed: PDF, PNG, JPG, JPEG, CSV, TXT, MD')
    ).toBeInTheDocument();
  });

  it('2. validates upload file size limit (rejects files > 20 MB)', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([sampleDocReady]);

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('quarterly_report.pdf').length).toBeGreaterThan(0);
    });

    // Create a 25 MB mock file
    const largeFile = new File([new ArrayBuffer(25 * 1024 * 1024)], 'too_large.pdf', {
      type: 'application/pdf',
    });
    const input = document.getElementById('file-upload-input') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [largeFile] } });

    expect(screen.getByText('File exceeds maximum upload size (20 MB)')).toBeInTheDocument();
  });

  it('3. handles upload progress and supports cancelling in-flight upload', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([]);

    let progressCb: ((p: number) => void) | undefined;
    vi.spyOn(api, 'uploadDocument').mockImplementation(
      (_file, _sens, onProgress, cancelRef) =>
        new Promise((_resolve, reject) => {
          progressCb = onProgress;
          if (cancelRef) {
            cancelRef.abort = () => {
              reject(new Error('Upload cancelled.'));
            };
          }
        })
    );

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    const validFile = new File(['valid pdf content'], 'report.pdf', { type: 'application/pdf' });
    const input = document.getElementById('file-upload-input') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [validFile] } });

    const uploadBtn = screen.getByTestId('confirm-upload-button');
    fireEvent.click(uploadBtn);

    // Simulate progress event
    act(() => {
      if (progressCb) progressCb(45);
    });

    await waitFor(() => {
      expect(screen.getByText('Uploading... 45%')).toBeInTheDocument();
    });

    // Click Cancel
    const cancelBtn = screen.getByTestId('cancel-upload-button');
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.getByText('Upload cancelled.')).toBeInTheDocument();
    });
  });

  it('4. polls status every 2 seconds while documents are queued/processing and stops when ready', async () => {
    vi.useFakeTimers();

    const listSpy = vi
      .spyOn(api, 'listDocuments')
      .mockResolvedValueOnce([sampleDocProcessing]) // initial load
      .mockResolvedValueOnce([sampleDocReady]); // after poll

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    // Initial load resolution
    await act(async () => {
      await Promise.resolve();
    });

    expect(listSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Auto-updating...')).toBeInTheDocument();

    // Advance 2 seconds
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(listSpy).toHaveBeenCalledTimes(2);

    // After ready doc is loaded, advance another 2 seconds: polling should NOT fire again
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(listSpy).toHaveBeenCalledTimes(2);
  });

  it('5. opens delete confirmation dialog and deletes document on confirm', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([sampleDocReady]);
    const deleteSpy = vi.spyOn(api, 'deleteDocument').mockResolvedValue(undefined);

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`document-row-${sampleDocReady.id}`)).toBeInTheDocument();
    });

    const deleteBtn = screen.getByTestId(`delete-doc-button-${sampleDocReady.id}`);
    fireEvent.click(deleteBtn);

    // Verify modal statement
    expect(
      screen.getByText(/It will be removed for everyone it was shared with/i)
    ).toBeInTheDocument();

    const confirmBtn = screen.getByTestId('confirm-delete-button');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(deleteSpy).toHaveBeenCalledWith(sampleDocReady.id);
      expect(screen.queryByTestId(`document-row-${sampleDocReady.id}`)).toBeNull();
    });
  });

  it('6. navigates to chat with source_ids when "Ask" is clicked', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([sampleDocReady]);

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId(`document-row-${sampleDocReady.id}`)).toBeInTheDocument();
    });

    const askBtn = screen.getByTestId(`ask-doc-button-${sampleDocReady.id}`);
    fireEvent.click(askBtn);

    expect(mockNavigate).toHaveBeenCalledWith('/chat', {
      state: {
        source_ids: [sampleDocReady.id],
        source_filename: sampleDocReady.filename,
      },
    });
  });

  it('7. renders document filenames containing HTML as plain text only (no XSS injection)', async () => {
    vi.spyOn(api, 'listDocuments').mockResolvedValue([sampleDocXss]);

    render(
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('<b id="injected-html">Sensitive</b>.pdf').length).toBeGreaterThan(0);
    });

    // Verify no DOM element with id="injected-html" was created
    expect(document.getElementById('injected-html')).toBeNull();
  });
});
