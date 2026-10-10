import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiClientError } from '../api/client';
import { DocumentItem, DocumentKind, DocumentStatus, CitationItem } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { useChat } from '../chat/ChatContext';
import { CitationPanel } from '../components/CitationPanel';
import { ShareDialog } from '../components/ShareDialog';
import { ErrorBanner } from '../components/ErrorBanner';
import { Skeleton } from '../components/Skeleton';
import {
  Upload,
  FileText,
  FileSpreadsheet,
  FileImage,
  FileCode,
  File,
  Share2,
  Trash2,
  MessageSquare,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
  X,
  Shield,
  FolderOpen,
  Users,
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

function getFileIcon(kind: DocumentKind) {
  switch (kind) {
    case 'pdf':
      return <FileText className="text-red-500" size={18} aria-hidden="true" />;
    case 'csv':
      return <FileSpreadsheet className="text-green-600" size={18} aria-hidden="true" />;
    case 'image':
      return <FileImage className="text-blue-500" size={18} aria-hidden="true" />;
    case 'text':
      return <FileCode className="text-amber-500" size={18} aria-hidden="true" />;
    default:
      return <File className="text-text-muted" size={18} aria-hidden="true" />;
  }
}

function StatusChip({ status, reasonCode }: { status: DocumentStatus; reasonCode: string | null }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
        <CheckCircle2 size={12} aria-hidden="true" />
        Ready
      </span>
    );
  }
  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
        <Loader2 size={12} className="animate-spin" aria-hidden="true" />
        Processing
      </span>
    );
  }
  if (status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-semibold text-blue-600 dark:text-blue-400">
        <Clock size={12} aria-hidden="true" />
        Queued
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-semibold text-red-600 dark:text-red-400"
      title={reasonCode ? `Reason: ${reasonCode}` : undefined}
    >
      <AlertCircle size={12} aria-hidden="true" />
      Failed{reasonCode ? `: ${reasonCode}` : ''}
    </span>
  );
}

export const DocumentsPage: React.FC = () => {
  const { user } = useAuth();
  const { hasActiveConversation, handleNewChat, setSourceFilter } = useChat();
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
    if (hasActiveConversation) {
      const confirmed = window.confirm('Start a new chat for this document?');
      if (!confirmed) {
        return;
      }
      handleNewChat();
    }
    setSourceFilter({
      source_ids: [doc.id],
      filename: doc.filename,
    });
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

  return (
    <div className="flex h-full w-full overflow-hidden relative">
      <div className="flex-1 flex flex-col h-full overflow-y-auto p-4 md:p-6 items-center min-w-0">
        <div className="w-full max-w-5xl space-y-6">
          {/* Page Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-text">My Documents</h1>
              <p className="text-xs text-text-muted mt-1">
                Upload and securely share documents with row-level and column-level access controls.
              </p>
            </div>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover transition-colors shrink-0 self-start sm:self-auto cursor-pointer focus-visible:ring-2 focus-visible:ring-accent outline-none"
              data-testid="upload-document-button"
            >
              <Upload size={16} aria-hidden="true" />
              <span>Upload Document</span>
            </button>
          </div>

          {/* Upload Card / Dropzone */}
          <div className="rounded-card border border-border bg-surface p-5 shadow-xs space-y-4">
            <h2 className="text-sm font-semibold text-text flex items-center gap-2">
              <Upload size={16} className="text-accent" aria-hidden="true" />
              Upload Document
            </h2>

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
                isDragging
                  ? 'border-accent bg-accent/5'
                  : 'border-border bg-surface-raised/40 hover:bg-surface-raised'
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
              <Upload size={28} className="text-text-muted mb-2" aria-hidden="true" />
              <p className="text-xs font-medium text-text">
                Drag & drop your file here, or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-accent underline hover:text-accent-hover font-semibold focus:outline-none"
                  data-testid="browse-files-button"
                >
                  browse files
                </button>
              </p>
              <p className="text-[11px] text-text-muted mt-1">
                Supported formats: PDF, PNG, JPG, JPEG, CSV, TXT, MD (Max 20 MB)
              </p>
            </div>

            {/* Selected File Details & Actions */}
            {selectedFile && (
              <div className="rounded-md border border-border bg-surface p-3 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 truncate">
                    <FileText size={16} className="text-accent shrink-0" aria-hidden="true" />
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
                      className="p-1 text-text-muted hover:text-text rounded"
                      aria-label="Remove selected file"
                    >
                      <X size={14} aria-hidden="true" />
                    </button>
                  )}
                </div>

                {/* CSV Sensitive Column Detection */}
                {csvHeaders.length > 0 && (
                  <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 space-y-2 text-xs">
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
                            className="h-3.5 w-3.5 rounded border-border text-accent focus:ring-accent"
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
                    <button
                      type="button"
                      onClick={handleStartUpload}
                      className="inline-flex items-center gap-2 rounded-btn bg-accent px-4 py-2 text-xs font-semibold text-accent-contrast shadow-xs hover:bg-accent-hover transition-colors"
                      data-testid="confirm-upload-button"
                    >
                      <Upload size={14} aria-hidden="true" />
                      <span>Upload & Ingest</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Upload notifications */}
            {uploadError && (
              <div
                className="rounded-md border border-danger/40 bg-danger/10 p-3 text-xs text-danger flex items-center gap-2"
                role="alert"
                data-testid="upload-error-message"
              >
                <AlertCircle size={15} className="shrink-0" aria-hidden="true" />
                <span>{uploadError}</span>
              </div>
            )}

            {uploadSuccessMessage && (
              <div
                className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2"
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
              className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300 flex items-center justify-between"
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
                className="p-1 text-text-muted hover:text-text rounded"
                aria-label="Dismiss banner"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          )}

          {/* Tabs: My uploads vs Shared with me */}
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-1">
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => setActiveTab('mine')}
                  className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 ${
                    activeTab === 'mine'
                      ? 'border-accent text-accent'
                      : 'border-transparent text-text-muted hover:text-text'
                  }`}
                  data-testid="tab-my-uploads"
                >
                  My uploads
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('shared')}
                  className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 ${
                    activeTab === 'shared'
                      ? 'border-accent text-accent'
                      : 'border-transparent text-text-muted hover:text-text'
                  }`}
                  data-testid="tab-shared-with-me"
                >
                  Shared with me
                </button>
              </div>

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
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            )}

            {/* Empty State */}
            {!isLoading && documents.length === 0 && (
              <div
                className="rounded-card border border-border bg-surface p-8 text-center"
                data-testid="empty-documents-state"
              >
                <div className="inline-flex rounded-full bg-surface-raised p-3 text-text-muted border border-border mb-3">
                  <FolderOpen size={24} aria-hidden="true" />
                </div>
                <h3 className="text-sm font-semibold text-text">
                  {activeTab === 'mine' ? 'No documents uploaded yet' : 'No documents shared with you'}
                </h3>
                <p className="text-xs text-text-muted max-w-sm mx-auto mt-1">
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
                <div className="hidden md:block overflow-hidden rounded-card border border-border bg-surface shadow-xs">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-border bg-surface-raised text-text-muted font-semibold uppercase tracking-wider">
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
                          className="hover:bg-surface-raised/50 transition-colors"
                          data-testid={`document-row-${doc.id}`}
                        >
                          <td className="py-3 px-4 font-medium text-text">
                            <div className="flex items-center gap-2 max-w-xs truncate">
                              {getFileIcon(doc.kind)}
                              <span className="truncate" title={doc.filename}>
                                {doc.filename}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-3 text-text-muted whitespace-nowrap">
                            {formatBytes(doc.size_bytes)}
                          </td>
                          <td className="py-3 px-3 text-text-muted whitespace-nowrap">
                            {formatDate(doc.created_at)}
                          </td>
                          <td className="py-3 px-3 whitespace-nowrap">
                            <StatusChip status={doc.status} reasonCode={doc.reason_code} />
                          </td>
                          <td className="py-3 px-3 text-text-muted whitespace-nowrap">
                            {activeTab === 'mine' ? (
                              doc.shared_with_count && doc.shared_with_count > 0 ? (
                                <span className="inline-flex items-center gap-1 font-medium text-text">
                                  <Users size={12} className="text-accent" aria-hidden="true" />
                                  Shared ({doc.shared_with_count})
                                </span>
                              ) : (
                                <span>Private</span>
                              )
                            ) : (
                              <span>{doc.owner.name}</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              {/* Ask about this document */}
                              <button
                                type="button"
                                onClick={() => handleAskAboutDocument(doc)}
                                disabled={doc.status !== 'ready'}
                                className="inline-flex items-center gap-1 rounded-btn px-2 py-1 text-xs font-medium text-text-muted hover:bg-surface-raised hover:text-accent disabled:opacity-30 transition-colors"
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
                                className="inline-flex items-center gap-1 rounded-btn px-2 py-1 text-xs font-medium text-text-muted hover:bg-surface-raised hover:text-text disabled:opacity-30 transition-colors"
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
                                  className="inline-flex items-center gap-1 rounded-btn px-2 py-1 text-xs font-medium text-text-muted hover:bg-surface-raised hover:text-text transition-colors"
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
                                  className="inline-flex items-center gap-1 rounded-btn px-2 py-1 text-xs font-medium text-danger hover:bg-red-50 hover:text-danger dark:hover:bg-red-950/40 transition-colors"
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
                      className="rounded-card border border-border bg-surface p-4 shadow-xs space-y-3"
                      data-testid={`document-card-${doc.id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2 truncate">
                          {getFileIcon(doc.kind)}
                          <div className="truncate">
                            <h4 className="font-semibold text-xs text-text truncate">
                              {doc.filename}
                            </h4>
                            <p className="text-[11px] text-text-muted">
                              {formatBytes(doc.size_bytes)} • {formatDate(doc.created_at)}
                            </p>
                          </div>
                        </div>
                        <StatusChip status={doc.status} reasonCode={doc.reason_code} />
                      </div>

                      <div className="flex items-center justify-between border-t border-border-subtle pt-2 text-xs text-text-muted">
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
                            className="p-1.5 text-text-muted hover:text-accent rounded min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                            title="Ask about this document"
                            aria-label="Ask about this document"
                          >
                            <MessageSquare size={16} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenDocument(doc)}
                            disabled={doc.status !== 'ready'}
                            className="p-1.5 text-text-muted hover:text-text rounded min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
                            title="Open in Source Viewer"
                            aria-label="Open in Source Viewer"
                          >
                            <ExternalLink size={16} aria-hidden="true" />
                          </button>
                          {doc.can_manage && (
                            <button
                              type="button"
                              onClick={() => setSharingDoc(doc)}
                              className="p-1.5 text-text-muted hover:text-text rounded min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
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
                              className="p-1.5 text-danger rounded min-h-[40px] min-w-[40px] flex items-center justify-center transition-colors"
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div className="w-full max-w-md rounded-card border border-border bg-surface p-5 shadow-raised space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 text-danger">
                <AlertCircle size={20} aria-hidden="true" />
                <h3 id="delete-dialog-title" className="text-sm font-bold text-text">
                  Delete Document
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setDeleteDoc(null)}
                className="p-1 text-text-muted hover:text-text rounded"
                aria-label="Close dialog"
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>

            <p className="text-xs text-text-muted leading-relaxed">
              Are you sure you want to delete{' '}
              <strong className="text-text font-semibold">{deleteDoc.filename}</strong>? It will
              be removed for everyone it was shared with.
            </p>

            {deleteError && (
              <div
                className="rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger"
                role="alert"
              >
                {deleteError}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDeleteDoc(null)}
                className="rounded-btn border border-border px-3 py-1.5 text-xs font-semibold text-text hover:bg-surface-raised transition-colors"
                disabled={isDeleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="inline-flex items-center gap-1.5 rounded-btn bg-danger px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-danger-hover disabled:opacity-40 transition-colors"
                data-testid="confirm-delete-button"
              >
                {isDeleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                <span>Delete</span>
              </button>
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
