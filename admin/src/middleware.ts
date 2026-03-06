import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    const url = new URL(request.url);
    const apiPath = url.pathname + url.search;
    return NextResponse.rewrite(new URL(apiPath, backendUrl));
}

export const config = {
    matcher: '/api/:path*',
};
