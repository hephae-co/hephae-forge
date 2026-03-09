import { useAuth } from '@/contexts/AuthContext';
import { useCallback } from 'react';

/**
 * Returns an `apiFetch` function that auto-attaches the X-Firebase-Token header
 * when the user is authenticated. Falls through to regular fetch for guests.
 */
export function useApiClient() {
  const { getIdToken } = useAuth();

  const apiFetch = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const token = await getIdToken();
      const headers = new Headers(init?.headers);

      if (token) {
        headers.set('X-Firebase-Token', token);
      }

      return fetch(input, { ...init, headers });
    },
    [getIdToken],
  );

  return { apiFetch };
}
