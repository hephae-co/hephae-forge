import { NextRequest } from 'next/server';
import { createHmac } from 'crypto';

export const maxDuration = 180; // 3 minutes — discovery + analyze pipelines are long-running
export const dynamic = 'force-dynamic';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';
const FORGE_API_SECRET = process.env.FORGE_API_SECRET || '';

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

  // HMAC request signing for backend auth
  if (FORGE_API_SECRET) {
    const timestamp = Math.floor(Date.now() / 1000).toString();
    const signature = createHmac('sha256', FORGE_API_SECRET)
      .update(timestamp)
      .digest('hex');
    headers.set('x-forge-timestamp', timestamp);
    headers.set('x-forge-signature', signature);
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
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}
