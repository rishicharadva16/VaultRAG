import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  api,
  setAuthToken,
  getAuthToken,
  setOnUnauthorized,
  ApiClientError,
} from '../api/client';

describe('API Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    sessionStorage.clear();
    setAuthToken(null);
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('401 response clears the session and triggers unauthorized callback', async () => {
    setAuthToken('expired-mock-token');
    expect(getAuthToken()).toBe('expired-mock-token');

    const unauthorizedSpy = vi.fn();
    setOnUnauthorized(unauthorizedSpy);

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    });

    await expect(api.getMe()).rejects.toThrow(ApiClientError);
    await expect(api.getMe()).rejects.toMatchObject({
      status: 401,
      message: 'Your session expired. Please sign in again.',
    });

    // Session token cleared
    expect(getAuthToken()).toBeNull();
    expect(sessionStorage.getItem('vaultrag_token')).toBeNull();
    expect(unauthorizedSpy).toHaveBeenCalled();
  });

  it('429 response maps to rate limit message', async () => {
    setAuthToken('valid-token');
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Rate limit exceeded' }),
    });

    await expect(api.ask({ question: 'Test' })).rejects.toMatchObject({
      status: 429,
      message: 'You are asking too quickly. Wait a moment and try again.',
    });
  });

  it('503 response maps to service unavailable message', async () => {
    setAuthToken('valid-token');
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Service unavailable' }),
    });

    await expect(api.ask({ question: 'Test' })).rejects.toMatchObject({
      status: 503,
      message: 'The AI service is busy or unavailable. Try again shortly.',
    });
  });

  it('network failure maps to server unreachable message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.getHealth()).rejects.toMatchObject({
      status: 0,
      isNetworkError: true,
      message: 'Cannot reach the VaultRAG server. Is the backend running?',
    });
  });
});
