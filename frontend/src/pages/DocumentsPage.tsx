import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiClientError } from '../api/client';
import { DocumentItem, CitationItem } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { CitationPanel } from '../components/CitationPanel';
import { ShareDialog } from '../components/ShareDialog';
import { ErrorBanner } from '../components/ErrorBanner';
import { Skeleton } from '../components/Skeleton';
import {
  PageHeader,
  StatCard,
  SegmentedControl,
  FileTypeIcon,
  StatusPill,
  Button,
} from '../components/ui';
import {
  Upload,
  Share2,
  Trash2,
  MessageSquare,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle2,
  X,
  Shield,
  FolderOpen,
  Users,
  Lock,
} from 'lucide-react';

const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20 MB
const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'csv', 'txt', 'md'];

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export const DocumentsPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'mine' | 'shared'>('mine');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [bannerMessage, setBannerMessage] = useState<string | null>(null);

  // Upload state
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [selectedSensitiveCols, setSelectedSensitiveCols] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);

  // Cancel reference for in-flight XHR upload
  const uploadCancelRef = useRef<{ abort?: () => void }>({});

  // Active dialogs
  const [sharingDoc, setSharingDoc] = useState<DocumentItem | null>(null);
  const [deleteDoc, setDeleteDoc] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Source viewer panel
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<number | null>(null);
  const prevUserIdRef = useRef<string | null>(user?.id ?? null);

  // Fetch document list
  const loadDocuments = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.listDocuments(activeTab);
      setDocuments(data);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to load documents. Please check backend connection.');
      }
    } finally {
      if (!quiet) setIsLoading(false);
    }
  }, [activeTab]);

  // Initial load when tab changes
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Reset when user changes
  useEffect(() => {
    if (user && prevUserIdRef.current !== null && prevUserIdRef.current !== user.id) {
      setSelectedFile(null);
      setCsvHeaders([]);
      setSelectedSensitiveCols([]);
      setUploadProgress(null);
      setUploadError(null);
      setUploadSuccessMessage(null);
      setSharingDoc(null);
      setDeleteDoc(null);
      setSelectedCitation(null);
      loadDocuments();
    }
    prevUserIdRef.current = user?.id ?? null;
  }, [user, loadDocuments]);

  // Auto-refresh polling every 2s while any document is queued or processing
  useEffect(() => {
    const hasPending = documents.some(
      (d) => d.status === 'queued' || d.status === 'processing'
    );

    if (hasPending) {
      if (pollingRef.current === null) {
        pollingRef.current = window.setInterval(() => {
          loadDocuments(true);
        }, 2000);
      }
    } else {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [documents, loadDocuments]);

  // File selection & validation
  const handleFilePicked = (file: File) => {
    setUploadError(null);
    setUploadSuccessMessage(null);

    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(
        'Unsupported file type. Allowed: PDF, PNG, JPG, JPEG, CSV, TXT, MD'
      );
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError('File exceeds maximum upload size (20 MB)');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setSelectedSensitiveCols([]);

    // If CSV, read only header row to present sensitive column checkboxes
    if (ext === 'csv') {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = (e.target?.result as string) || '';
        const firstLine = text.split(/\r\n|\n|\r/)[0];
        if (firstLine) {
          const cols = firstLine
            .split(',')
            .map((c) => c.trim().replace(/^["']|["']$/g, ''))
            .filter(Boolean);
          setCsvHeaders(cols);
        } else {
          setCsvHeaders([]);
        }
      };
      reader.onerror = () => setCsvHeaders([]);
      // Read first 8KB only for header row
      reader.readAsText(file.slice(0, 8192));
    } else {
      setCsvHeaders([]);
    }
  };

  const handleStartUpload = async () => {
    if (!selectedFile) return;

    setUploadError(null);
    setUploadSuccessMessage(null);
    setUploadProgress(0);

    try {
      const resp = await api.uploadDocument(
        selectedFile,
        selectedSensitiveCols.length > 0 ? selectedSensitiveCols : undefined,
        (percent) => setUploadProgress(percent),
        uploadCancelRef.current
      );

      setUploadProgress(null);
      setSelectedFile(null);
      setCsvHeaders([]);
      setSelectedSensitiveCols([]);

      if (resp.isDuplicate) {
        setUploadSuccessMessage('You already uploaded this file.');
      } else {
        setUploadSuccessMessage('Upload submitted successfully. Ingestion in progress...');
      }

      // Reload list and switch to "My uploads" tab
      if (activeTab !== 'mine') {
        setActiveTab('mine');
      } else {
        loadDocuments(true);
      }
    } catch (err: unknown) {
      setUploadProgress(null);
      if (err instanceof ApiClientError) {
        if (err.status === 403) {
          setUploadError('Your role cannot upload documents');
        } else if (err.status === 413) {
          setUploadError('File exceeds maximum upload size (20 MB)');
        } else if (err.status === 415) {
          setUploadError('Unsupported file type. Allowed: PDF, PNG, JPG, JPEG, CSV, TXT, MD');
        } else if (err.status === 422) {
          setUploadError('Validation error: invalid document format');
        } else if (err.status === 429) {
          setUploadError('Upload rate limit reached. Please wait before uploading more files.');
        } else if (err.status === 503) {
          setUploadError('Ingestion service is temporarily unavailable.');
        } else if (err.isNetworkError) {
          setUploadError('Network error. Please check your connection and try again.');
        } else {
          setUploadError(err.message);
        }
      } else {
        setUploadError('An unexpected error occurred during upload.');
      }
    }
  };

  const handleCancelUpload = () => {
    if (uploadCancelRef.current.abort) {
      uploadCancelRef.current.abort();
    }
    setUploadProgress(null);
    setUploadError('Upload cancelled.');
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilePicked(e.dataTransfer.files[0]);
    }
  };

  // Open Document in Source Viewer
  const handleOpenDocument = (doc: DocumentItem) => {
    const citationItem: CitationItem = {
      id: 1,
      chunk_id: doc.id.startsWith('doc:') ? `${doc.id}#0` : `doc:${doc.id}#0`,
      source_id: doc.id.startsWith('doc:') ? doc.id : `doc:${doc.id}`,
      file: doc.filename,
      page: 1,
      snippet: '',
      highlights: [],
      highlight_text: '',
    };
    setSelectedCitation(citationItem);
  };

  // Ask about this document (navigates to Chat with filter chip)
  const handleAskAboutDocument = (doc: DocumentItem) => {
    navigate('/chat', {
      state: {
        source_ids: [doc.id],
        source_filename: doc.filename,
      },
    });
  };

  // Delete document
  const handleConfirmDelete = async () => {
    if (!deleteDoc) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteDocument(deleteDoc.id);
      // Immediately remove from list
      setDocuments((prev) => prev.filter((d) => d.id !== deleteDoc.id));
      setDeleteDoc(null);
      setBannerMessage(`Document "${deleteDoc.filename}" deleted successfully.`);
    } catch (err: unknown) {
      if (err instanceof ApiClientError && (err.status === 403 || err.status === 404)) {
        setDeleteError("You can't delete this document.");
      } else {
        setDeleteError('Failed to delete document. Please try again.');
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleSensitiveCol = (col: string) => {
    setSelectedSensitiveCols((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    );
  };

  const totalDocs = documents.length;
  const readyDocs = documents.filter((d) => d.status === 'ready').length;
  const sharedDocs = documents.filter((d) => (d.shared_with_count ?? 0) > 0).length;
  const privateDocs = documents.filter((d) => !d.shared_with_count || d.shared_with_count === 0).length;

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-4 md:p-6 lg:p-8 items-center min-w-0">
        <div className="w-full max-w-6xl space-y-6">
          {/* Page Header */}
          <PageHeader
            title="My Documents"
            subtitle="Upload and securely share documents with row-level and column-level access controls."
            actions={
              <Button
                variant="primary"
                size="sm"
                leadingIcon={<Upload size={14} />}
                onClick={() => fileInputRef.current?.click()}
              >
                Upload Document
              </Button>
            }
          />

          {/* Stat Cards Row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <StatCard
              label="Total Documents"
              value={totalDocs}
              icon={<FolderOpen size={18} />}
              iconBg="bg-primary-soft text-primary"
            />
            <StatCard
              label="Ready & Indexed"
              value={readyDocs}
              icon={<CheckCircle2 size={18} />}
              iconBg="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
            />
            <StatCard
              label="Shared Documents"
              value={sharedDocs}
              icon={<Users size={18} />}
              iconBg="bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
            />
            <StatCard
              label="Private Documents"
              value={privateDocs}
              icon={<Lock size={18} />}
              iconBg="bg-slate-500/10 text-slate-600 dark:text-slate-400"
            />
          </div>

          {/* Upload Card / Dropzone */}
          <div className="rounded-card border border-border bg-surface p-5 sm:p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-text flex items-center gap-2">
                <Upload size={16} className="text-accent" aria-hidden="true" />
                Upload Document
              </h2>
              <span className="text-xs text-text-muted">
                PDF, PNG, JPG, JPEG, CSV, TXT, MD (Max 20 MB)
              </span>
            </div>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center rounded-card border-2 border-dashed p-8 text-center transition-all duration-150 ${
                isDragging
                  ? 'border-accent bg-accent/10 scale-[0.99]'
                  : 'border-border bg-surface-2/60 hover:bg-surface-2 hover:border-border-subtle'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.md"
                className="hidden"
                id="file-upload-input"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFilePicked(e.target.files[0]);
                  }
                }}
              />
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-soft text-primary mb-3 shadow-xs">
                <Upload size={22} aria-hidden="true" />
              </div>
              <p className="text-xs sm:text-sm font-medium text-text">
                Drag a file here or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-primary underline hover:text-accent font-semibold focus:outline-hidden transition-colors"
                  data-testid="browse-files-button"
                >
                  browse
                </button>
              </p>
              <p className="text-[11px] text-text-muted mt-1.5">
                Supported formats: PDF, PNG, JPG, JPEG, CSV, TXT, MD (Max 20 MB)
              </p>
            </div>

            {/* Selected File Details & Actions */}
            {selectedFile && (
              <div className="rounded-btn border border-border bg-surface-2 p-3.5 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2.5 truncate">
                    <FileTypeIcon
                      kind={
                        selectedFile.name.endsWith('.pdf')
                          ? 'pdf'
                          : selectedFile.name.endsWith('.csv')
                          ? 'csv'
                          : selectedFile.name.match(/\.(png|jpe?g)$/i)
                          ? 'image'
                          : 'text'
                      }
                      size={18}
                    />
                    <span className="font-semibold text-text truncate">{selectedFile.name}</span>
                    <span className="text-text-muted">({formatBytes(selectedFile.size)})</span>
                  </div>
                  {uploadProgress === null && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedFile(null);
                        setCsvHeaders([]);
                        setSelectedSensitiveCols([]);
                        setUploadError(null);
                      }}
                      className="p-1 text-text-muted hover:text-text rounded-btn"
                      aria-label="Remove selected file"
                    >
                      <X size={14} aria-hidden="true" />
                    </button>
                  )}
                </div>

                {/* CSV Sensitive Column Detection */}
                {csvHeaders.length > 0 && (
                  <div className="rounded-btn border border-amber-500/30 bg-amber-500/10 p-3 space-y-2 text-xs">
                    <div className="flex items-center gap-1.5 font-semibold text-amber-700 dark:text-amber-400">
                      <Shield size={14} aria-hidden="true" />
                      <span>Mark as sensitive (only you and admins will see these columns):</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 pt-1">
                      {csvHeaders.map((col) => (
                        <label
                          key={col}
                          className="flex items-center gap-2 text-xs text-text cursor-pointer select-none"
                        >
                          <input
                            type="checkbox"
                            checked={selectedSensitiveCols.includes(col)}
                            onChange={() => toggleSensitiveCol(col)}
                            className="h-3.5 w-3.5 rounded border-border text-primary focus:ring-primary"
                          />
                          <span className="truncate">{col}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* Progress Bar & Cancel */}
                {uploadProgress !== null ? (
                  <div className="space-y-2" aria-live="polite">
                    <div className="flex items-center justify-between text-xs text-text-muted">
                      <span>Uploading... {uploadProgress}%</span>
                      <button
                        type="button"
                        onClick={handleCancelUpload}
                        className="text-xs font-semibold text-danger hover:underline"
                        data-testid="cancel-upload-button"
                      >
                        Cancel
                      </button>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full bg-accent transition-all duration-150"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-end pt-1">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleStartUpload}
                      leadingIcon={<Upload size={14} />}
                      data-testid="confirm-upload-button"
                    >
                      Upload & Ingest
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Upload notifications */}
            {uploadError && (
              <div
                className="rounded-btn border border-danger/40 bg-danger/10 p-3 text-xs text-danger flex items-center gap-2"
                role="alert"
                data-testid="upload-error-message"
              >
                <AlertCircle size={15} className="shrink-0" aria-hidden="true" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadSuccessMessage && (
              <div
                className="rounded-btn border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2"
                role="status"
                aria-live="polite"
                data-testid="upload-success-message"
              >
                <CheckCircle2 size={15} className="shrink-0" aria-hidden="true" />
                <span>{uploadSuccessMessage}</span>
              </div>
            )}
          </div>

          {/* Banner message */}
          {bannerMessage && (
            <div
              className="rounded-btn border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300 flex items-center justify-between"
              role="status"
              aria-live="polite"
            >
              <div className="flex items-center gap-2">
                <CheckCircle2 size={15} aria-hidden="true" />
                <span>{bannerMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setBannerMessage(null)}
                className="p-1 text-text-muted hover:text-text rounded-btn"
                aria-label="Dismiss banner"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          )}

          {/* Tabs: My uploads vs Shared with me */}
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-border pb-3">
              <SegmentedControl
                value={activeTab}
                onChange={(val) => setActiveTab(val as 'mine' | 'shared')}
                options={[
                  {
                    value: 'mine',
                    label: 'My uploads',
                    count: activeTab === 'mine' ? documents.length : undefined,
                    testId: 'tab-my-uploads',
                  },
                  {
                    value: 'shared',
                    label: 'Shared with me',
                    count: activeTab === 'shared' ? documents.length : undefined,
                    testId: 'tab-shared-with-me',
                  },
                ]}
              />

              {documents.some((d) => d.status === 'queued' || d.status === 'processing') && (
                <div className="flex items-center gap-1.5 text-xs text-text-muted">
                  <Loader2 size={13} className="animate-spin text-accent" aria-hidden="true" />
                  <span>Auto-updating...</span>
                </div>
              )}
            </div>

            {/* Error Banner */}
            {errorMessage && (
              <ErrorBanner
                message={errorMessage}
                onRetry={() => loadDocuments()}
                onDismiss={() => setErrorMessage(null)}
              />
            )}

            {/* Skeletons while loading */}
            {isLoading && (
              <div className="space-y-3 pt-2" aria-live="polite">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            )}

            {/* Empty State */}
            {!isLoading && documents.length === 0 && (
              <div
                className="rounded-card border border-border bg-surface p-10 text-center shadow-xs"
                data-testid="empty-documents-state"
              >
                <div className="inline-flex rounded-2xl bg-surface-2 p-3.5 text-text-muted border border-border mb-3 shadow-xs">
                  <FolderOpen size={26} aria-hidden="true" />
                </div>
                <h3 className="font-heading text-base font-semibold text-text">
                  {activeTab === 'mine' ? 'No documents uploaded yet' : 'No documents shared with you'}
                </h3>
                <p className="text-xs text-text-muted max-w-sm mx-auto mt-1 leading-relaxed">
                  {activeTab === 'mine'
                    ? 'Upload PDF, CSV, TXT or images above to index them into your secure knowledge vault.'
                    : 'When colleagues or teams share documents with you, they will appear here.'}
                </p>
              </div>
            )}

            {/* Documents List */}
            {!isLoading && documents.length > 0 && (
              <div className="space-y-3" aria-live="polite">
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-hidden rounded-card border border-border bg-surface shadow-sm">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-border bg-surface-2 text-text-muted font-semibold uppercase tracking-wider">
                      <tr>
                        <th className="py-3 px-4">File Name</th>
                        <th className="py-3 px-3">Size</th>
                        <th className="py-3 px-3">Uploaded</th>
                        <th className="py-3 px-3">Status</th>
                        <th className="py-3 px-3">
                          {activeTab === 'mine' ? 'Sharing' : 'Owner'}
                        </th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {documents.map((doc) => (
                        <tr
                          key={doc.id}
                          className="hover:bg-surface-2/60 transition-colors"
                          data-testid={`document-row-${doc.id}`}
                        >
                          <td className="py-3.5 px-4 font-medium text-text">
                            <div className="flex items-center gap-2.5 max-w-xs truncate">
                              <FileTypeIcon kind={doc.kind} size={18} />
                              <span className="truncate font-semibold" title={doc.filename}>
                                {doc.filename}
                              </span>
                            </div>
                          </td>
                          <td className="py-3.5 px-3 text-text-muted whitespace-nowrap">
                            {formatBytes(doc.size_bytes)}
                          </td>
                          <td className="py-3.5 px-3 text-text-muted whitespace-nowrap">
                            {formatDate(doc.created_at)}
                          </td>
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <StatusPill
                              status={doc.status}
                              reasonCode={doc.reason_code}
                              label={doc.status === 'failed' && doc.reason_code ? `Failed: ${doc.reason_code}` : undefined}
                            />
                          </td>
                          <td className="py-3.5 px-3 text-text-muted whitespace-nowrap">
                            {activeTab === 'mine' ? (
                              doc.shared_with_count && doc.shared_with_count > 0 ? (
                                <span className="inline-flex items-center gap-1.5 font-medium text-text bg-surface-2 px-2 py-0.5 rounded-badge border border-border">
                                  <Users size={12} className="text-accent" aria-hidden="true" />
                                  Shared ({doc.shared_with_count})
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 text-text-muted bg-surface-2 px-2 py-0.5 rounded-badge border border-border">
                                  <Lock size={12} aria-hidden="true" />
                                  Private
                                </span>
                              )
                            ) : (
                              <span>{doc.owner.name}</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              {/* Ask about this document */}
                              <button
                                type="button"
                                onClick={() => handleAskAboutDocument(doc)}
                                disabled={doc.status !== 'ready'}
                                className="inline-flex items-center gap-1 rounded-btn px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-surface-2 hover:text-primary disabled:opacity-30 transition-colors"
                                title="Ask questions about this document"
                                data-testid={`ask-doc-button-${doc.id}`}
                              >
                                <MessageSquare size={13} aria-hidden="true" />
                                <span>Ask</span>
                              </button>

                              {/* Open Source Viewer at Page 1 */}
                              <button
                                type="button"
                                onClick={() => handleOpenDocument(doc)}
                                disabled={doc.status !== 'ready'}
                                className="inline-flex items-center gap-1 rounded-btn px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-surface-2 hover:text-text disabled:opacity-30 transition-colors"
                                title="Open in Source Viewer"
                                data-testid={`open-doc-button-${doc.id}`}
                              >
                                <ExternalLink size={13} aria-hidden="true" />
                                <span>Open</span>
                              </button>

                              {/* Share (Owner or Admin only) */}
                              {doc.can_manage && (
                                <button
                                  type="button"
                                  onClick={() => setSharingDoc(doc)}
                                  className="inline-flex items-center gap-1 rounded-btn px-2.5 py-1 text-xs font-medium text-text-muted hover:bg-surface-2 hover:text-text transition-colors"
                                  title="Manage document access"
                                  data-testid={`share-doc-button-${doc.id}`}
                                >
                                  <Share2 size={13} aria-hidden="true" />
                                  <span>Share</span>
                                </button>
                              )}

                              {/* Delete (Owner or Admin only) */}
                              {doc.can_manage && (
                                <button
                                  type="button"
                                  onClick={() => setDeleteDoc(doc)}
                                  className="inline-flex items-center gap-1 rounded-btn px-2.5 py-1 text-xs font-medium text-danger hover:bg-rose-500/10 hover:text-danger transition-colors"
                                  title="Delete document"
                                  data-testid={`delete-doc-button-${doc.id}`}
                                >
                                  <Trash2 size={13} aria-hidden="true" />
                                  <span>Delete</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Cards View */}
                <div className="grid grid-cols-1 gap-3 md:hidden">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="rounded-card border border-border bg-surface p-4 shadow-sm space-y-3"
                      data-testid={`document-card-${doc.id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5 truncate">
                          <FileTypeIcon kind={doc.kind} size={20} />
                          <div className="truncate">
                            <h4 className="font-semibold text-xs text-text truncate">
                              {doc.filename}
                            </h4>
                            <p className="text-[11px] text-text-muted mt-0.5">
                              {formatBytes(doc.size_bytes)} • {formatDate(doc.created_at)}
                            </p>
                          </div>
                        </div>
                        <StatusPill
                          status={doc.status}
                          reasonCode={doc.reason_code}
                          label={doc.status === 'failed' && doc.reason_code ? `Failed: ${doc.reason_code}` : undefined}
                        />
                      </div>

                      <div className="flex items-center justify-between border-t border-border pt-2 text-xs text-text-muted">
                        <span>
                          {activeTab === 'mine'
                            ? doc.shared_with_count && doc.shared_with_count > 0
                              ? `Shared (${doc.shared_with_count})`
                              : 'Private'
                            : `Owner: ${doc.owner.name}`}
                        </span>

                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleAskAboutDocument(doc)}
                            disabled={doc.status !== 'ready'}
                            className="p-2 text-text-muted hover:text-primary rounded-btn min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                            title="Ask about this document"
                            aria-label="Ask about this document"
                          >
                            <MessageSquare size={16} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenDocument(doc)}
                            disabled={doc.status !== 'ready'}
                            className="p-2 text-text-muted hover:text-text rounded-btn min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                            title="Open in Source Viewer"
                            aria-label="Open in Source Viewer"
                          >
                            <ExternalLink size={16} aria-hidden="true" />
                          </button>
                          {doc.can_manage && (
                            <button
                              type="button"
                              onClick={() => setSharingDoc(doc)}
                              className="p-2 text-text-muted hover:text-text rounded-btn min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                              title="Share"
                              aria-label="Share document"
                            >
                              <Share2 size={16} aria-hidden="true" />
                            </button>
                          )}
                          {doc.can_manage && (
                            <button
                              type="button"
                              onClick={() => setDeleteDoc(doc)}
                              className="p-2 text-danger rounded-btn min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                              title="Delete"
                              aria-label="Delete document"
                            >
                              <Trash2 size={16} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Share Dialog */}
      {sharingDoc && (
        <ShareDialog
          document={sharingDoc}
          isOpen={Boolean(sharingDoc)}
          onClose={() => setSharingDoc(null)}
          onShareUpdated={() => loadDocuments(true)}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 animate-scale-in"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div className="w-full max-w-md rounded-dialog border border-border bg-surface p-6 shadow-xl space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2.5 text-danger">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-rose-500/10 text-danger shrink-0">
                  <AlertCircle size={20} aria-hidden="true" />
                </div>
                <h3 id="delete-dialog-title" className="font-heading text-base font-bold text-text">
                  Delete Document
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setDeleteDoc(null)}
                className="p-1.5 text-text-muted hover:text-text rounded-btn"
                aria-label="Close dialog"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <p className="text-xs sm:text-sm text-text-muted leading-relaxed">
              Are you sure you want to delete{' '}
              <strong className="text-text font-semibold">{deleteDoc.filename}</strong>? It will
              be removed for everyone it was shared with.
            </p>

            {deleteError && (
              <div
                className="rounded-btn border border-danger/30 bg-danger/10 p-3 text-xs text-danger"
                role="alert"
              >
                {deleteError}
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeleteDoc(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleConfirmDelete}
                loading={isDeleting}
                leadingIcon={<Trash2 size={13} />}
                data-testid="confirm-delete-button"
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Citation Slide-over Panel (Source Viewer) */}
      {selectedCitation && (
        <CitationPanel
          citation={selectedCitation}
          citations={[selectedCitation]}
          currentIndex={0}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  );
};
