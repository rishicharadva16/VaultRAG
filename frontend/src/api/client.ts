import {
  AskResponse,
  ChunkResponse,
  HealthResponse,
  SearchResponse,
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
    throw new ApiClientError(422, 'Invalid input.');
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
    data: { question: string; top_k?: number },
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
    data: { query: string; top_k?: number; rerank?: boolean },
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

  getHealth: async (): Promise<HealthResponse> => {
    return request<HealthResponse>('/health', {
      method: 'GET',
      requiresAuth: false,
    });
  },
};
