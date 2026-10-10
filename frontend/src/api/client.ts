import {
  AdminQueryLog,
  AdminUploadItem,
  AdminUser,
  AskResponse,
  AuditSummary,
  ChunkResponse,
  CreateAdminUserPayload,
  CreateSharePayload,
  DocumentDetail,
  DocumentItem,
  DocumentShare,
  DocumentUploadResponse,
  HealthResponse,
  HighlightSpan,
  PatchAdminUserPayload,
  SearchResponse,
  SharingTargets,
  SourcePagesResponse,
  SourceViewResponse,
  TokenResponse,
  User,
} from './types';

const TOKEN_KEY = 'vaultrag_token';

let inMemoryToken: string | null = null;
let onUnauthorizedHandler: (() => void) | null = null;

export class ApiClientError extends Error {
  status: number;
  isNetworkError: boolean;

  constructor(status: number, message: string, isNetworkError = false) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

export function setOnUnauthorized(handler: () => void) {
  onUnauthorizedHandler = handler;
}

export function setAuthToken(token: string | null) {
  inMemoryToken = token;
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_KEY);
  }
}

export function getAuthToken(): string | null {
  if (inMemoryToken) {
    return inMemoryToken;
  }
  const saved = sessionStorage.getItem(TOKEN_KEY);
  if (saved) {
    inMemoryToken = saved;
    return saved;
  }
  return null;
}

export function clearSession() {
  inMemoryToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

function getBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL as string) || 'http://127.0.0.1:8000';
}

interface RequestOptions extends RequestInit {
  requiresAuth?: boolean;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { requiresAuth = true, headers = {}, ...rest } = options;
  const baseUrl = getBaseUrl().replace(/\/+$/, '');
  const url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string>),
  };

  if (requiresAuth) {
    const token = getAuthToken();
    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
    });
  } catch (err: unknown) {
    // Check if error was caused by abort
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw err;
    }
    // Network / server connection error
    throw new ApiClientError(
      0,
      'Cannot reach the VaultRAG server. Is the backend running?',
      true
    );
  }

  if (response.ok) {
    return response.json() as Promise<T>;
  }

  // Handle errors
  const status = response.status;
  let detailMessage = '';
  try {
    const errorBody = await response.json();
    if (errorBody && typeof errorBody.detail === 'string') {
      detailMessage = errorBody.detail;
    }
  } catch {
    // Non-JSON response
  }

  if (status === 401) {
    clearSession();
    if (onUnauthorizedHandler) {
      onUnauthorizedHandler();
    }
    // If login attempt failed vs expired session
    if (endpoint.includes('/auth/login')) {
      throw new ApiClientError(401, detailMessage || 'Invalid email or password');
    }
    throw new ApiClientError(401, 'Your session expired. Please sign in again.');
  }

  if (status === 404) {
    throw new ApiClientError(404, detailMessage || 'Resource not found');
  }

  if (status === 422) {
    throw new ApiClientError(422, detailMessage || 'Invalid input.');
  }

  if (status === 429) {
    throw new ApiClientError(429, 'You are asking too quickly. Wait a moment and try again.');
  }

  if (status === 503) {
    throw new ApiClientError(503, 'The AI service is busy or unavailable. Try again shortly.');
  }

  throw new ApiClientError(status, detailMessage || `Request failed with status ${status}`);
}

// ── Public API ───────────────────────────────────────────────

export const api = {
  login: async (credentials: { email: string; password: string }): Promise<TokenResponse> => {
    const data = await request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      requiresAuth: false,
    });
    setAuthToken(data.access_token);
    return data;
  },

  getMe: async (): Promise<User> => {
    return request<User>('/auth/me', {
      method: 'GET',
      requiresAuth: true,
    });
  },



  ask: async (
    data: { question: string; top_k?: number; source_ids?: string[] },
    signal?: AbortSignal
  ): Promise<AskResponse> => {
    return request<AskResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify(data),
      signal,
      requiresAuth: true,
    });
  },

  search: async (
    data: { query: string; top_k?: number; rerank?: boolean; source_ids?: string[] },
    signal?: AbortSignal
  ): Promise<SearchResponse> => {
    return request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify(data),
      signal,
      requiresAuth: true,
    });
  },

  getCitation: async (chunkId: string, signal?: AbortSignal): Promise<ChunkResponse> => {
    const encodedId = encodeURIComponent(chunkId);
    return request<ChunkResponse>(`/citation/${encodedId}`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getSourceView: async (
    chunkId: string,
    highlights?: HighlightSpan[],
    signal?: AbortSignal
  ): Promise<SourceViewResponse> => {
    const encodedId = encodeURIComponent(chunkId);
    let url = `/source/${encodedId}/view`;
    if (highlights && highlights.length > 0) {
      const hlParam = highlights.map((h) => `${h.start}-${h.end}`).join(',');
      url += `?hl=${encodeURIComponent(hlParam)}`;
    }
    return request<SourceViewResponse>(url, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getSourcePages: async (chunkId: string, signal?: AbortSignal): Promise<SourcePagesResponse> => {
    const encodedId = encodeURIComponent(chunkId);
    return request<SourcePagesResponse>(`/source/${encodedId}/pages`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getSourcePageImageBlob: async (
    chunkId: string,
    page?: number,
    signal?: AbortSignal
  ): Promise<Blob> => {
    const encodedId = encodeURIComponent(chunkId);
    const baseUrl = getBaseUrl().replace(/\/+$/, '');
    let url = `${baseUrl}/source/${encodedId}/page.png`;
    if (page !== undefined && page !== null) {
      url += `?page=${page}`;
    }
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    let res: Response;
    try {
      res = await fetch(url, { headers, signal });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw err;
      }
      throw new ApiClientError(0, 'Cannot reach server', true);
    }
    if (!res.ok) {
      if (res.status === 404) {
        throw new ApiClientError(404, 'This source is no longer available.');
      }
      throw new ApiClientError(res.status, 'Failed to fetch page image');
    }
    return res.blob();
  },

  getHealth: async (): Promise<HealthResponse> => {
    return request<HealthResponse>('/health', {
      method: 'GET',
      requiresAuth: false,
    });
  },

  // ── Step 6: Documents & Sharing ──────────────────────────────

  uploadDocument: (
    file: File,
    sensitiveColumns?: string[],
    onProgress?: (percent: number) => void,
    cancelRef?: { abort?: () => void }
  ): Promise<DocumentUploadResponse> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      if (cancelRef) {
        cancelRef.abort = () => xhr.abort();
      }
      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable && onProgress) {
          const percent = Math.round((evt.loaded / evt.total) * 100);
          onProgress(percent);
        }
      };
      xhr.onload = () => {
        if (xhr.status === 200 || xhr.status === 202) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve({
              id: data.id,
              status: data.status,
              isDuplicate: xhr.status === 200,
            });
          } catch {
            reject(new ApiClientError(xhr.status, 'Invalid server response'));
          }
        } else {
          let detail = '';
          try {
            const err = JSON.parse(xhr.responseText);
            if (err && err.detail) detail = err.detail;
          } catch {}
          if (xhr.status === 403) {
            reject(new ApiClientError(403, 'Your role cannot upload documents'));
          } else if (xhr.status === 413) {
            reject(new ApiClientError(413, detail || 'File exceeds maximum size limit (20 MB)'));
          } else if (xhr.status === 415) {
            reject(new ApiClientError(415, detail || 'Unsupported file format or type mismatch'));
          } else if (xhr.status === 422) {
            reject(new ApiClientError(422, detail || 'Invalid or empty file'));
          } else if (xhr.status === 429) {
            reject(new ApiClientError(429, detail || 'Upload rate limit exceeded. Please try again later.'));
          } else {
            reject(new ApiClientError(xhr.status, detail || `Upload failed with status ${xhr.status}`));
          }
        }
      };
      xhr.onerror = () => {
        reject(new ApiClientError(0, 'Network error during upload. Is the backend running?', true));
      };
      xhr.onabort = () => {
        reject(new ApiClientError(0, 'Upload cancelled by user', false));
      };

      const baseUrl = getBaseUrl().replace(/\/+$/, '');
      xhr.open('POST', `${baseUrl}/documents`);
      const token = getAuthToken();
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }
      const formData = new FormData();
      formData.append('file', file);
      if (sensitiveColumns && sensitiveColumns.length > 0) {
        formData.append('sensitive_columns', JSON.stringify(sensitiveColumns));
      }
      xhr.send(formData);
    });
  },

  listDocuments: async (
    scope: 'mine' | 'shared' | 'all' = 'mine',
    signal?: AbortSignal
  ): Promise<DocumentItem[]> => {
    return request<DocumentItem[]>(`/documents?scope=${encodeURIComponent(scope)}`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getDocument: async (docId: string, signal?: AbortSignal): Promise<DocumentDetail> => {
    return request<DocumentDetail>(`/documents/${encodeURIComponent(docId)}`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  deleteDocument: async (docId: string): Promise<void> => {
    const baseUrl = getBaseUrl().replace(/\/+$/, '');
    const url = `${baseUrl}/documents/${encodeURIComponent(docId)}`;
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(url, {
      method: 'DELETE',
      headers,
    });
    if (!res.ok) {
      if (res.status === 404) {
        throw new ApiClientError(404, 'Document not found');
      }
      throw new ApiClientError(res.status, `Failed to delete document (status ${res.status})`);
    }
  },

  getDocumentShares: async (docId: string, signal?: AbortSignal): Promise<DocumentShare[]> => {
    return request<DocumentShare[]>(`/documents/${encodeURIComponent(docId)}/shares`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  createDocumentShare: async (
    docId: string,
    payload: CreateSharePayload
  ): Promise<DocumentShare> => {
    return request<DocumentShare>(`/documents/${encodeURIComponent(docId)}/shares`, {
      method: 'POST',
      body: JSON.stringify(payload),
      requiresAuth: true,
    });
  },

  deleteDocumentShare: async (docId: string, shareId: string): Promise<void> => {
    const baseUrl = getBaseUrl().replace(/\/+$/, '');
    const url = `${baseUrl}/documents/${encodeURIComponent(docId)}/shares/${encodeURIComponent(shareId)}`;
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(url, {
      method: 'DELETE',
      headers,
    });
    if (!res.ok) {
      if (res.status === 404) {
        throw new ApiClientError(404, 'Share not found');
      }
      throw new ApiClientError(res.status, `Failed to delete share (status ${res.status})`);
    }
  },

  getSharingTargets: async (query: string = '', signal?: AbortSignal): Promise<SharingTargets> => {
    const qParam = query ? `?q=${encodeURIComponent(query)}` : '';
    return request<SharingTargets>(`/sharing/targets${qParam}`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  // ── Step 6: Admin Monitoring ─────────────────────────────────

  getAdminAuditSummary: async (days: number = 7, signal?: AbortSignal): Promise<AuditSummary> => {
    return request<AuditSummary>(`/admin/audit/summary?days=${days}`, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getAdminQueries: async (
    limit: number = 50,
    before?: string,
    signal?: AbortSignal
  ): Promise<AdminQueryLog[]> => {
    let url = `/admin/queries?limit=${limit}`;
    if (before) {
      url += `&before=${encodeURIComponent(before)}`;
    }
    return request<AdminQueryLog[]>(url, {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getAdminUploads: async (signal?: AbortSignal): Promise<AdminUploadItem[]> => {
    return request<AdminUploadItem[]>('/admin/uploads', {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  getAdminUsers: async (signal?: AbortSignal): Promise<AdminUser[]> => {
    return request<AdminUser[]>('/admin/users', {
      method: 'GET',
      signal,
      requiresAuth: true,
    });
  },

  createAdminUser: async (payload: CreateAdminUserPayload): Promise<AdminUser> => {
    return request<AdminUser>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
      requiresAuth: true,
    });
  },

  patchAdminUser: async (
    userId: string,
    payload: PatchAdminUserPayload
  ): Promise<AdminUser> => {
    return request<AdminUser>(`/admin/users/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
      requiresAuth: true,
    });
  },

  deleteAdminUser: async (userId: string): Promise<void> => {
    return request<void>(`/admin/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
      requiresAuth: true,
    });
  },
};
