'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';

// This page loads a saved business profile and redirects to the forge
// with the business pre-populated. It acts as a shareable profile URL.
export default function BusinessProfilePage() {
    const params = useParams();
    const router = useRouter();
    const slug = params?.slug as string;
    const [status, setStatus] = useState<'loading' | 'found' | 'notfound'>('loading');
    const [businessName, setBusinessName] = useState('');

    useEffect(() => {
        if (!slug) return;
        fetch(`/api/b/${slug}`)
            .then(r => r.json())
            .then(data => {
                if (data?.identity?.name) {
                    setBusinessName(data.identity.name);
                    setStatus('found');
                    // Store identity in sessionStorage for the forge page to pick up
                    sessionStorage.setItem('forge_preload_slug', slug);
                    sessionStorage.setItem('forge_preload_identity', JSON.stringify(data.identity));
                    // Redirect to forge (root) which will auto-trigger overview
                    router.replace('/');
                } else {
                    setStatus('notfound');
                }
            })
            .catch(() => setStatus('notfound'));
    }, [slug, router]);

    if (status === 'loading') {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-center">
                    <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-slate-400 text-sm">Loading business profile…</p>
                </div>
            </div>
        );
    }

    if (status === 'notfound') {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-center max-w-sm">
                    <p className="text-white font-bold text-lg mb-2">Profile not found</p>
                    <p className="text-slate-400 text-sm mb-6">This business profile link may have expired or been removed.</p>
                    <a href="/" className="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors">
                        Search for a business
                    </a>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center">
            <div className="text-center">
                <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-slate-400 text-sm">Loading {businessName}…</p>
            </div>
        </div>
    );
}
