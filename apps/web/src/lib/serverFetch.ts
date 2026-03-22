/**
 * Server-side fetch to the backend API with Cloud Run IAM auth.
 *
 * Use this in Server Components (SSR) that need to call the backend directly.
 * It fetches an identity token from the GCE metadata server (same as the proxy).
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

async function getIdentityToken(audience: string): Promise<string | null> {
  try {
    const url = `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${audience}`;
    const res = await fetch(url, {
      headers: { 'Metadata-Flavor': 'Google' },
    });
    if (res.ok) return res.text();
    return null;
  } catch {
    return null;
  }
}

export async function serverFetch(
  path: string,
  options?: { revalidate?: number },
): Promise<Response> {
  const url = `${BACKEND_URL}${path}`;
  const token = await getIdentityToken(BACKEND_URL);

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return fetch(url, {
    headers,
    next: options?.revalidate ? { revalidate: options.revalidate } : undefined,
  });
}
