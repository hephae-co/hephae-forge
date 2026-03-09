import { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Fetch an identity token from the GCE metadata server.
 * Returns null when not running on GCP (local dev).
 */
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

async function proxyRequest(
  request: NextRequest,
  pathSegments: string[],
): Promise<Response> {
  const path = pathSegments.join('/');
  const target = `${BACKEND_URL}/api/${path}${request.nextUrl.search}`;

  const headers = new Headers(request.headers);
  headers.delete('host');

  // Cloud Run service-to-service auth
  const token = await getIdentityToken(BACKEND_URL);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Forward Firebase auth token from client
  const firebaseToken = request.headers.get('X-Firebase-Token');
  if (firebaseToken) {
    headers.set('X-Firebase-Token', firebaseToken);
  }

  const init: RequestInit & { duplex?: string } = {
    method: request.method,
    headers,
  };

  if (request.body && !['GET', 'HEAD'].includes(request.method)) {
    init.body = request.body;
    init.duplex = 'half';
  }

  const response = await fetch(target, init);

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxyRequest(request, params.path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxyRequest(request, params.path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxyRequest(request, params.path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxyRequest(request, params.path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxyRequest(request, params.path);
}
