'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

/** Check if the current path is the login page (works with or without /admin prefix). */
function isLoginPath(pathname: string): boolean {
  return pathname === '/login' || pathname.endsWith('/login');
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublicPath = isLoginPath(pathname);

  useEffect(() => {
    if (loading) return;

    if (!user && !isPublicPath) {
      // Detect if we're behind the /admin/ gateway prefix
      const prefix = typeof window !== 'undefined' && window.location.pathname.startsWith('/admin') ? '/admin' : '';
      window.location.replace(`${prefix}/login`);
    }
  }, [user, loading, isPublicPath, router]);

  // Always render public paths immediately (don't wait for Firebase)
  if (isPublicPath) {
    return <>{children}</>;
  }

  // Show loading spinner while auth state resolves (protected paths only)
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    );
  }

  // Block protected paths if not authenticated
  if (!user) {
    return null; // will redirect via useEffect
  }

  return <>{children}</>;
}
