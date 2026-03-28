'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { MapPin, Star, Users, TrendingUp, ExternalLink, BarChart3 } from 'lucide-react';

interface PublicProfile {
    slug: string;
    name: string;
    address: string;
    identity: Record<string, any>;
    snapshot: Record<string, any>;
    publishedAt?: string;
}

function humanize(s: string): string {
    return s.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function BusinessProfileClient({
    slug,
    publicProfile,
}: {
    slug: string;
    publicProfile: PublicProfile | null;
}) {
    const { user } = useAuth();
    const [redirecting, setRedirecting] = useState(false);

    // Authenticated users → redirect to interactive app with preloaded data
    useEffect(() => {
        if (user && publicProfile?.identity) {
            setRedirecting(true);
            sessionStorage.setItem('forge_preload_slug', slug);
            sessionStorage.setItem('forge_preload_identity', JSON.stringify(publicProfile.identity));
            if (publicProfile.snapshot) {
                sessionStorage.setItem('forge_preload_snapshot', JSON.stringify(publicProfile.snapshot));
            }
            window.location.href = '/';
        }
    }, [user, publicProfile, slug]);

    // Also try to load via authenticated API for non-published profiles
    useEffect(() => {
        if (!publicProfile && !user) return; // Not published + not logged in = 404
        if (!publicProfile && user) {
            // Try authenticated fetch
            fetch(`/api/b/${slug}`)
                .then(r => r.json())
                .then(data => {
                    if (data?.identity?.name) {
                        setRedirecting(true);
                        sessionStorage.setItem('forge_preload_slug', slug);
                        sessionStorage.setItem('forge_preload_identity', JSON.stringify(data.identity));
                        if (data.snapshot) {
                            sessionStorage.setItem('forge_preload_snapshot', JSON.stringify(data.snapshot));
                        }
                        window.location.href = '/';
                    }
                })
                .catch(() => {});
        }
    }, [publicProfile, user, slug]);

    if (redirecting) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-center">
                    <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-slate-400 text-sm">Loading {publicProfile?.name || 'profile'}…</p>
                </div>
            </div>
        );
    }

    // Not published and not logged in → 404
    if (!publicProfile) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <div className="text-center max-w-sm">
                    <p className="text-white font-bold text-lg mb-2">Profile not found</p>
                    <p className="text-slate-400 text-sm mb-6">This business profile hasn't been published yet.</p>
                    <a href="/" className="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors">
                        Search for a business
                    </a>
                </div>
            </div>
        );
    }

    // === PUBLIC READ-ONLY PAGE ===
    const { name, address, snapshot } = publicProfile;
    const overview = snapshot?.overview || {};
    const bs = overview.businessSnapshot || {};
    const mp = overview.marketPosition || {};
    const le = overview.localEconomy || {};
    const dash = overview.dashboard || {};
    const insights = dash.topInsights || [];
    const opps = overview.keyOpportunities || [];
    const competitors = dash.competitors || [];

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
            {/* Header */}
            <header className="border-b border-white/5 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
                <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
                    <a href="/" className="text-sm font-bold text-indigo-400 hover:text-indigo-300">Hephae</a>
                    <a href="/" className="text-xs text-slate-500 hover:text-indigo-400 transition-colors">
                        Analyze your business →
                    </a>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-4 py-8">
                {/* Business Header */}
                <div className="mb-8">
                    <h1 className="text-2xl md:text-3xl font-black text-white tracking-tight">{name}</h1>
                    <div className="flex items-center gap-3 mt-2 flex-wrap">
                        <span className="flex items-center gap-1 text-sm text-slate-400">
                            <MapPin className="w-3.5 h-3.5" /> {address}
                        </span>
                        {bs.rating && (
                            <span className="flex items-center gap-1 text-sm text-amber-400">
                                <Star className="w-3.5 h-3.5 fill-amber-400" /> {bs.rating}/5
                                {bs.reviewCount && <span className="text-slate-500">({bs.reviewCount})</span>}
                            </span>
                        )}
                        {bs.category && (
                            <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">{bs.category}</span>
                        )}
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                    {mp.competitorCount !== undefined && (
                        <div className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-1">
                                <Users className="w-4 h-4 text-orange-400" />
                                <span className="text-xs text-slate-500 font-semibold uppercase">Competitors</span>
                            </div>
                            <p className="text-xl font-bold text-white">{mp.competitorCount}</p>
                            {mp.saturationLevel && <p className="text-xs text-slate-500 capitalize">{mp.saturationLevel} market</p>}
                        </div>
                    )}
                    {le.medianIncome && (
                        <div className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-1">
                                <BarChart3 className="w-4 h-4 text-emerald-400" />
                                <span className="text-xs text-slate-500 font-semibold uppercase">Median Income</span>
                            </div>
                            <p className="text-xl font-bold text-white">{le.medianIncome}</p>
                        </div>
                    )}
                    {le.population && (
                        <div className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-1">
                                <Users className="w-4 h-4 text-blue-400" />
                                <span className="text-xs text-slate-500 font-semibold uppercase">Population</span>
                            </div>
                            <p className="text-xl font-bold text-white">{le.population}</p>
                        </div>
                    )}
                    {dash.confirmedSources > 0 && (
                        <div className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-1">
                                <TrendingUp className="w-4 h-4 text-indigo-400" />
                                <span className="text-xs text-slate-500 font-semibold uppercase">Data Sources</span>
                            </div>
                            <p className="text-xl font-bold text-white">{dash.confirmedSources}</p>
                        </div>
                    )}
                </div>

                {/* Weekly Intelligence */}
                {insights.length > 0 && (
                    <section className="mb-8">
                        <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
                            <TrendingUp className="w-5 h-5 text-indigo-400" /> Weekly Intelligence
                        </h2>
                        <div className="space-y-2">
                            {insights.map((insight: any, i: number) => (
                                <div key={i} className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                                    <h3 className="text-sm font-bold text-white mb-1">{humanize(insight.title)}</h3>
                                    <p className="text-xs text-slate-400 leading-relaxed">{insight.recommendation}</p>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Key Opportunities */}
                {opps.length > 0 && (
                    <section className="mb-8">
                        <h2 className="text-lg font-bold text-white mb-3">Opportunities</h2>
                        <div className="space-y-2">
                            {opps.map((opp: any, i: number) => (
                                <div key={i} className="bg-slate-800/50 border border-white/5 rounded-xl p-4">
                                    <h3 className="text-sm font-bold text-white mb-1">{humanize(opp.title)}</h3>
                                    <p className="text-xs text-slate-400">{opp.detail}</p>
                                    {opp.dataPoint && <p className="text-xs text-indigo-400 mt-1">{opp.dataPoint}</p>}
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Nearby Competitors */}
                {competitors.length > 0 && (
                    <section className="mb-8">
                        <h2 className="text-lg font-bold text-white mb-3">Nearby Competitors</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            {competitors.slice(0, 6).map((c: any, i: number) => (
                                <div key={i} className="bg-slate-800/50 border border-white/5 rounded-xl p-3 flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-semibold text-white">{c.name}</p>
                                        {c.category && <p className="text-xs text-slate-500">{c.category}</p>}
                                    </div>
                                    {c.distanceM && <span className="text-xs text-slate-500">{Math.round(c.distanceM)}m</span>}
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* CTA */}
                <div className="bg-gradient-to-r from-indigo-600 to-violet-600 rounded-2xl p-6 text-center">
                    <h3 className="text-lg font-bold text-white mb-2">Get This Analysis For Your Business</h3>
                    <p className="text-sm text-white/80 mb-4">Hephae runs this analysis on any local business in minutes — for free.</p>
                    <a href="/" className="inline-block px-6 py-2.5 bg-white text-indigo-600 font-bold text-sm rounded-full hover:bg-gray-100 transition-colors">
                        Analyze Your Business →
                    </a>
                </div>

                {/* Footer */}
                <footer className="mt-12 pt-6 border-t border-white/5 text-center">
                    <p className="text-xs text-slate-600">
                        Data sourced from BLS, Census, USDA, OSM, and Google.
                        Analysis powered by <a href="/" className="text-indigo-500 hover:text-indigo-400">Hephae AI</a>.
                        {publicProfile.publishedAt && ` Published ${new Date(publicProfile.publishedAt).toLocaleDateString()}.`}
                    </p>
                </footer>
            </main>
        </div>
    );
}
