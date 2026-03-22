"use client";

import React, { useState, useEffect, useRef } from 'react';

import { BaseIdentity, EnrichedProfile, SocialPlatformMetrics } from '@/types/api';
import DiscoveryProgress from './DiscoveryProgress';

interface DashboardData {
    businessLocation?: { lat: number; lng: number } | null;
    competitors?: { name: string; category: string; cuisine: string; distanceM: number; lat?: number; lng?: number }[];
    stats?: { population?: string | null; medianIncome?: string | null; city?: string | null; state?: string | null; county?: string | null; competitorCount?: number; localNewspaper?: string | null; patchUrl?: string | null };
    events?: { what: string; when: string }[];
    communityBuzz?: string | null;
    pulseHeadline?: string | null;
    topInsights?: { title: string; recommendation: string }[];
    confirmedSources?: number;
}

interface MapVisualizerProps {
    lat: number;
    lng: number;
    businessName: string;
    business?: BaseIdentity | EnrichedProfile;
    isDiscovering?: boolean;
    dashboard?: DashboardData | null;
}

type ActiveTab = 'overview' | 'profile' | 'theme' | 'contact' | 'social' | 'menu' | 'competitors';

export default function MapVisualizer({ lat, lng, businessName, business, isDiscovering = false, dashboard }: MapVisualizerProps) {
    const [zoomLevel, setZoomLevel] = useState<number>(15);
    const [resetKey, setResetKey] = useState(0);
    const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
    const [logoError, setLogoError] = useState(false);
    const [profileCollapsed, setProfileCollapsed] = useState(false);

    const getUrl = () => {
        // Google Maps embed — no API key needed for this format, avoids 403 referrer issues
        const query = business?.address
            ? `${businessName}, ${business.address}`
            : `${lat},${lng}`;
        return `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=${zoomLevel}&output=embed`;
    };

    const getMapStyle = () => {
        return {
            filter: 'invert(90%) hue-rotate(180deg) brightness(1.05) contrast(90%) saturate(110%)',
            border: 0,
            opacity: 1
        };
    };

    const handleZoom = (delta: number) => {
        setZoomLevel(prev => Math.min(Math.max(prev + delta, 13), 18));
    }

    useEffect(() => {
        setResetKey(prev => prev + 1);
    }, [lat, lng]);

    const profile = business as EnrichedProfile;
    const isEnriched = !isDiscovering && business && 'phone' in business;

    // Determine which tabs have actual data (hide empty tabs once enrichment is done)
    const hasTheme = isDiscovering || !!(profile?.logoUrl || profile?.favicon || profile?.primaryColor || profile?.persona);
    const hasContact = isDiscovering || !!(profile?.phone || profile?.email || profile?.hours);
    const hasSocial = isDiscovering || !!(
        profile?.socialLinks?.instagram || profile?.socialLinks?.facebook ||
        profile?.socialLinks?.twitter || profile?.socialLinks?.yelp ||
        profile?.socialLinks?.tiktok || profile?.googleMapsUrl ||
        profile?.socialProfileMetrics?.summary
    );
    const hasMenu = isDiscovering || !!(
        profile?.menuUrl ||
        profile?.socialLinks?.grubhub ||
        profile?.socialLinks?.doordash ||
        profile?.socialLinks?.ubereats ||
        profile?.socialLinks?.seamless ||
        profile?.socialLinks?.toasttab
    );
    const hasCompetitors = isDiscovering || !!(profile?.competitors?.length);
    const hasOverview = isDiscovering || !!(profile?.aiOverview?.summary);

    const ALL_TABS: { id: ActiveTab; label: string; hasData: boolean }[] = [
        { id: 'overview', label: 'Overview', hasData: hasOverview },
        { id: 'profile', label: 'Profile', hasData: true },
        { id: 'theme', label: 'Theme', hasData: hasTheme },
        { id: 'contact', label: 'Contact', hasData: hasContact },
        { id: 'social', label: 'Social', hasData: hasSocial },
        { id: 'menu', label: 'Menu', hasData: hasMenu },
        { id: 'competitors', label: 'Rivals', hasData: hasCompetitors },
    ];
    const TABS = ALL_TABS.filter(t => t.hasData);

    // Auto-select first available tab when enrichment completes
    useEffect(() => {
        if (!isDiscovering && TABS.length && !TABS.find(t => t.id === activeTab)) {
            setActiveTab(TABS[0].id);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDiscovering]);

    return (
        <div className="relative w-full h-full bg-slate-800 overflow-hidden group">
            {/* NATIVE MAP INTERACTION ENABLED */}
            <iframe
                key={`${resetKey}-${zoomLevel}`}
                className="w-full h-full transition-all duration-500 pointer-events-auto"
                style={getMapStyle()}
                src={getUrl()}
                allowFullScreen
                loading="lazy"
                referrerPolicy="no-referrer"
                title="Traffic Intelligence Map"
                tabIndex={-1}
            ></iframe>

            {/* CONTROLS (Right Side) */}
            <div className="absolute bottom-20 right-6 z-30 flex flex-col items-center gap-4">
                <button
                    onClick={() => setResetKey(p => p + 1)}
                    className="w-10 h-10 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center font-bold shadow-lg border border-indigo-400/50"
                    title="Re-Center Map"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                </button>
                <div className="flex flex-col gap-1">
                    <button onClick={() => handleZoom(1)} className="bg-white text-gray-700 w-11 h-11 md:w-10 md:h-10 rounded-t-lg shadow-lg hover:bg-gray-100 font-bold flex items-center justify-center border-b border-gray-200 text-lg">+</button>
                    <button onClick={() => handleZoom(-1)} className="bg-white text-gray-700 w-11 h-11 md:w-10 md:h-10 rounded-b-lg shadow-lg hover:bg-gray-100 font-bold flex items-center justify-center text-lg">-</button>
                </div>
            </div>

            {/* VISUALIZATION OVERLAY */}
            <div className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center animate-fade-in">
                <div className="absolute inset-0 pointer-events-none mix-blend-screen overflow-visible flex items-center justify-center">
                    <div className="absolute z-20 pointer-events-none">
                        <div className="relative flex items-center justify-center">
                            <div className="absolute w-12 h-12 bg-indigo-500 rounded-full animate-ping opacity-40"></div>
                            <div className="relative w-4 h-4 bg-indigo-400 rounded-full border-2 border-white shadow-[0_0_20px_rgba(255,255,255,0.9)]"></div>
                            <div className={`absolute top-full mt-2 text-indigo-100 font-bold text-sm bg-slate-900/90 px-3 py-1.5 rounded-md border border-indigo-500/50 shadow backdrop-blur whitespace-nowrap max-w-[200px] truncate`}>
                                {businessName}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* GLASSMORPHISM DISCOVERY OVERLAY */}
            {business && (
                <div className="absolute top-6 left-6 right-6 z-40 max-w-xl animate-fade-in-up flex flex-col gap-4" style={{ animationDelay: '0.5s' }}>
                    <div className="bg-slate-900/85 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl overflow-hidden">

                        {/* HEADER */}
                        <div className={`p-6 ${profileCollapsed ? 'pb-5' : 'pb-4'} ${profileCollapsed ? '' : 'border-b border-white/10'}`}>
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center border border-indigo-500/50 shrink-0">
                                    <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                                </div>
                                <div className="min-w-0 flex-1">
                                    <h2 className="text-white font-bold text-lg leading-tight truncate">{business.name}</h2>
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="all" variant="inline" />
                                    ) : (
                                        <p className="text-indigo-300 text-xs font-medium uppercase tracking-wider flex items-center gap-1 mt-0.5">
                                            <svg className="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                                            Profile Enriched
                                        </p>
                                    )}
                                </div>
                                {/* Collapse toggle */}
                                <button
                                    onClick={() => setProfileCollapsed(v => !v)}
                                    className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors shrink-0"
                                    title={profileCollapsed ? 'Expand profile' : 'Collapse profile'}
                                >
                                    <svg
                                        className={`w-4 h-4 text-slate-400 transition-transform duration-300 ${profileCollapsed ? 'rotate-180' : ''}`}
                                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                    >
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
                                    </svg>
                                </button>
                            </div>

                            {/* TABS — 6 tabs, compact */}
                            <div className={`flex gap-0.5 p-1 bg-black/40 rounded-lg overflow-x-auto scrollbar-hide transition-all duration-300 ${profileCollapsed ? 'max-h-0 opacity-0 overflow-hidden mt-0 p-0' : 'max-h-20 opacity-100 mt-4'}`}>
                                {TABS.map(tab => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex-1 py-2 md:py-1 text-[11px] md:text-[10px] font-bold rounded-md transition-colors leading-tight flex-shrink-0 ${activeTab === tab.id ? 'bg-indigo-500 text-white shadow' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* TAB CONTENT */}
                        <div className={`space-y-4 transition-all duration-300 ${profileCollapsed ? 'max-h-0 opacity-0 overflow-hidden p-0' : 'max-h-[600px] opacity-100 p-6 pt-4'}`}>

                            {/* OVERVIEW TAB: AI Overview summary */}
                            {activeTab === 'overview' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[140px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="overview" variant="dots" />
                                    ) : profile?.aiOverview ? (
                                        <>
                                            <TruncatedText text={profile.aiOverview.summary} />

                                            {profile.aiOverview.highlights?.length > 0 && (
                                                <div className="flex flex-wrap gap-1.5">
                                                    {profile.aiOverview.highlights.map((h, i) => (
                                                        <span key={i} className="px-2 py-1 rounded-full bg-indigo-500/15 text-indigo-300 text-[11px] font-medium border border-indigo-500/20">
                                                            {h}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}

                                            <div className="flex flex-wrap gap-2">
                                                {profile.aiOverview.business_type && (
                                                    <div className="flex items-center gap-1.5 bg-black/20 px-2.5 py-1.5 rounded-lg border border-white/5">
                                                        <span className="text-[10px] font-bold text-slate-500 uppercase">Type</span>
                                                        <span className="text-xs text-white font-semibold">{profile.aiOverview.business_type}</span>
                                                    </div>
                                                )}
                                                {profile.aiOverview.price_range && (
                                                    <div className="flex items-center gap-1.5 bg-black/20 px-2.5 py-1.5 rounded-lg border border-white/5">
                                                        <span className="text-[10px] font-bold text-slate-500 uppercase">Price</span>
                                                        <span className="text-xs text-emerald-400 font-semibold">{profile.aiOverview.price_range}</span>
                                                    </div>
                                                )}
                                                {profile.aiOverview.established && (
                                                    <div className="flex items-center gap-1.5 bg-black/20 px-2.5 py-1.5 rounded-lg border border-white/5">
                                                        <span className="text-[10px] font-bold text-slate-500 uppercase">Est.</span>
                                                        <span className="text-xs text-white font-semibold">{profile.aiOverview.established}</span>
                                                    </div>
                                                )}
                                                {profile.aiOverview.reputation_signals && profile.aiOverview.reputation_signals !== 'unknown' && (
                                                    <div className="flex items-center gap-1.5 bg-black/20 px-2.5 py-1.5 rounded-lg border border-white/5">
                                                        <span className={`w-2 h-2 rounded-full ${
                                                            profile.aiOverview.reputation_signals === 'positive' ? 'bg-emerald-400' :
                                                            profile.aiOverview.reputation_signals === 'mixed' ? 'bg-yellow-400' : 'bg-red-400'
                                                        }`} />
                                                        <span className="text-xs text-slate-300 capitalize">{profile.aiOverview.reputation_signals}</span>
                                                    </div>
                                                )}
                                            </div>

                                            {profile.aiOverview.notable_mentions && profile.aiOverview.notable_mentions.length > 0 && (
                                                <div className="bg-black/20 p-2.5 rounded-xl border border-white/5">
                                                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">Notable Mentions</p>
                                                    <ul className="space-y-1">
                                                        {profile.aiOverview.notable_mentions.map((m, i) => (
                                                            <li key={i} className="text-xs text-slate-400 flex items-start gap-1.5">
                                                                <span className="text-indigo-400 mt-0.5 shrink-0">-</span>
                                                                {m}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="w-full p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-slate-400 text-sm text-center">
                                            No AI overview available.
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* PROFILE TAB: address + website only */}
                            {activeTab === 'profile' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[100px]">
                                    <div className="flex items-start gap-3 text-slate-300 bg-black/20 p-3 rounded-xl border border-white/5">
                                        <svg className="w-4 h-4 mt-0.5 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                        <p className="text-sm leading-snug">{business.address}</p>
                                    </div>
                                    <div className="flex items-center gap-3 text-slate-300 bg-black/20 p-3 rounded-xl border border-white/5">
                                        <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                                        <a href={business.officialUrl} target="_blank" rel="noreferrer" className="text-sm text-indigo-400 hover:text-indigo-300 truncate underline decoration-indigo-500/30 underline-offset-2">
                                            {business.officialUrl.replace(/^https?:\/\/(www\.)?/, '')}
                                        </a>
                                    </div>
                                </div>
                            )}

                            {/* THEME TAB: logo, favicon, colors, persona */}
                            {activeTab === 'theme' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[140px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="theme" variant="dots" />
                                    ) : (
                                        <>
                                            {/* Logo preview */}
                                            <div className="w-full rounded-xl overflow-hidden border border-white/10 bg-black/20 flex items-center justify-center" style={{ minHeight: '80px' }}>
                                                {profile.logoUrl && !logoError ? (
                                                    <img
                                                        src={profile.logoUrl}
                                                        alt="Logo"
                                                        className="w-full object-contain max-h-24 p-2"
                                                        onError={() => setLogoError(true)}
                                                    />
                                                ) : (
                                                    <div className="flex items-center justify-center w-full h-20">
                                                        <span className="text-2xl font-bold text-slate-400 tracking-wider">
                                                            {business.name.split(' ').map((w: string) => w[0]).slice(0, 2).join('').toUpperCase()}
                                                        </span>
                                                    </div>
                                                )}
                                            </div>

                                            {/* Favicon + Colors + Persona row */}
                                            <div className="flex items-center gap-3 bg-black/20 p-3 rounded-xl border border-white/5">
                                                {profile.favicon && (
                                                    <img src={profile.favicon} alt="favicon" className="w-5 h-5 rounded shrink-0" onError={(e) => (e.currentTarget.style.display = 'none')} />
                                                )}
                                                {profile.primaryColor && (
                                                    <div className="flex items-center gap-1.5 shrink-0">
                                                        <span className="w-4 h-4 rounded-full border border-white/20 shrink-0" style={{ backgroundColor: profile.primaryColor }}></span>
                                                        <span className="text-[10px] font-mono text-slate-400">{profile.primaryColor}</span>
                                                    </div>
                                                )}
                                                {profile.secondaryColor && (
                                                    <div className="flex items-center gap-1.5 shrink-0">
                                                        <span className="w-4 h-4 rounded-full border border-white/20 shrink-0" style={{ backgroundColor: profile.secondaryColor }}></span>
                                                        <span className="text-[10px] font-mono text-slate-400">{profile.secondaryColor}</span>
                                                    </div>
                                                )}
                                            </div>

                                            {profile.persona && (
                                                <div className="flex items-center gap-2 bg-black/20 p-3 rounded-xl border border-white/5">
                                                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider shrink-0">Persona</span>
                                                    <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-semibold border border-indigo-500/30">{profile.persona}</span>
                                                </div>
                                            )}

                                            {!profile.logoUrl && !profile.favicon && !profile.primaryColor && !profile.persona && (
                                                <div className="w-full p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-slate-400 text-sm text-center">
                                                    No theme assets found.
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            )}

                            {/* CONTACT TAB: phone, email, hours */}
                            {activeTab === 'contact' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[100px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="contact" variant="dots" />
                                    ) : (
                                        <>
                                            {profile.phone && (
                                                <div className="flex items-center gap-3 text-slate-300 bg-black/20 p-3 rounded-xl border border-white/5">
                                                    <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path></svg>
                                                    <a href={`tel:${profile.phone}`} className="text-sm hover:text-indigo-300 transition-colors">{profile.phone}</a>
                                                </div>
                                            )}
                                            {profile.email && (
                                                <div className="flex items-center gap-3 text-slate-300 bg-black/20 p-3 rounded-xl border border-white/5">
                                                    <svg className="w-4 h-4 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
                                                    <a href={`mailto:${profile.email}`} className="text-sm text-indigo-400 hover:text-indigo-300 truncate">{profile.email}</a>
                                                </div>
                                            )}
                                            {profile.hours && (
                                                <div className="flex items-start gap-3 text-slate-300 bg-black/20 p-3 rounded-xl border border-white/5">
                                                    <svg className="w-4 h-4 mt-0.5 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                                    <p className="text-sm leading-snug">{profile.hours}</p>
                                                </div>
                                            )}
                                            {!profile.phone && !profile.email && !profile.hours && (
                                                <div className="w-full p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-slate-400 text-sm text-center">
                                                    No contact details found.
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            )}

                            {/* SOCIAL TAB: social icons + Google Maps */}
                            {activeTab === 'social' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[100px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="social" variant="dots" />
                                    ) : (
                                        <>
                                            <div className="flex flex-wrap gap-2">
                                                {profile.socialLinks?.instagram && (
                                                    <a href={profile.socialLinks.instagram} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-pink-500/10 text-pink-400 hover:bg-pink-500/20 border border-pink-500/20 transition-colors text-sm font-semibold" title="Instagram">
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" /></svg>
                                                        Instagram
                                                    </a>
                                                )}
                                                {profile.socialLinks?.facebook && (
                                                    <a href={profile.socialLinks.facebook} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20 transition-colors text-sm font-semibold" title="Facebook">
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z" /></svg>
                                                        Facebook
                                                    </a>
                                                )}
                                                {profile.socialLinks?.twitter && (
                                                    <a href={profile.socialLinks.twitter} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-600/20 text-slate-300 hover:bg-slate-600/40 border border-slate-500/20 transition-colors text-sm font-semibold" title="X (Twitter)">
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.738l7.726-8.84-8.162-10.66h7.082l4.259 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z" /></svg>
                                                        Twitter / X
                                                    </a>
                                                )}
                                                {profile.socialLinks?.yelp && (
                                                    <a href={profile.socialLinks.yelp} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors text-sm font-semibold" title="Yelp">
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20.16 12.594l-4.995 1.433c-.96.275-1.638-.8-1.017-1.582l3.122-3.937c.602-.76 1.762-.404 1.84.546l.05 3.54zm-8.85 5.797l1.658 4.754c.36 1.03-.675 1.985-1.652 1.49L7.46 22.15c-.977-.496-1.017-1.844-.065-2.396l3.93-2.408c.91-.555 1.952.21 1.985 1.046zm-5.527-2.4c-.273.96-1.453 1.22-2.07.47L.928 12.55c-.617-.75-.235-1.882.702-2.095l4.898-1.117c.936-.213 1.73.787 1.312 1.65L5.784 15.99zm1.86-7.88L4.917 3.624c-.616-.75-.2-1.882.734-2.098l5.025-1.16c.934-.215 1.727.782 1.31 1.646L9.44 7.06c-.427.863-1.587.924-2.108.166l-.02-.026a1.18 1.18 0 01-.12-.49zm8.22.22c.078-.95 1.237-1.307 1.84-.547L21.6 12.1c.603.76.063 1.87-.895 1.75l-5.046-.62c-.958-.118-1.322-1.298-.596-1.945l1.792-1.764z" /></svg>
                                                        Yelp
                                                    </a>
                                                )}
                                                {profile.socialLinks?.tiktok && (
                                                    <a href={profile.socialLinks.tiktok} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-700/30 text-slate-200 hover:bg-slate-700/50 border border-slate-600/30 transition-colors text-sm font-semibold" title="TikTok">
                                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.87a8.17 8.17 0 004.77 1.52V6.95a4.85 4.85 0 01-1-.26z" /></svg>
                                                        TikTok
                                                    </a>
                                                )}
                                                {profile.googleMapsUrl && (
                                                    <a href={profile.googleMapsUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20 transition-colors text-sm font-semibold">
                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                                        Google Maps
                                                    </a>
                                                )}
                                            </div>
                                            {/* SOCIAL METRICS — shown when socialProfileMetrics is available */}
                                            {profile.socialProfileMetrics?.summary && (
                                                <div className="space-y-2 mt-1">
                                                    {/* Presence score bar */}
                                                    <div className="bg-black/20 p-3 rounded-xl border border-white/5">
                                                        <div className="flex items-center justify-between mb-1.5">
                                                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Social Presence</span>
                                                            <span className="text-xs font-bold text-white">{profile.socialProfileMetrics.summary.overallPresenceScore}<span className="text-slate-500 font-normal">/100</span></span>
                                                        </div>
                                                        <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                                                            <div
                                                                className="h-full rounded-full transition-all duration-500"
                                                                style={{
                                                                    width: `${Math.min(100, profile.socialProfileMetrics.summary.overallPresenceScore)}%`,
                                                                    backgroundColor: profile.socialProfileMetrics.summary.overallPresenceScore >= 60 ? '#22c55e' : profile.socialProfileMetrics.summary.overallPresenceScore >= 30 ? '#eab308' : '#ef4444',
                                                                }}
                                                            />
                                                        </div>
                                                        <div className="flex items-center justify-between mt-1.5">
                                                            <span className="text-[10px] text-slate-500">{profile.socialProfileMetrics.summary.totalFollowers?.toLocaleString()} followers</span>
                                                            <span className="text-[10px] text-slate-500 capitalize">{profile.socialProfileMetrics.summary.postingFrequency} posts</span>
                                                        </div>
                                                    </div>

                                                    {/* Per-platform mini-cards */}
                                                    <div className="grid grid-cols-2 gap-1.5">
                                                        {(['instagram', 'facebook', 'tiktok', 'yelp'] as const).map(platform => {
                                                            const data = profile.socialProfileMetrics?.[platform] as SocialPlatformMetrics | null | undefined;
                                                            if (!data || data.error) return null;
                                                            const engagement = data.engagementIndicator;
                                                            const dotColor = engagement === 'high' ? 'bg-emerald-400' : engagement === 'moderate' ? 'bg-yellow-400' : engagement === 'low' ? 'bg-red-400' : 'bg-slate-500';
                                                            return (
                                                                <div key={platform} className="bg-black/20 p-2 rounded-lg border border-white/5">
                                                                    <div className="flex items-center gap-1.5 mb-0.5">
                                                                        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
                                                                        <span className="text-[10px] font-bold text-slate-400 uppercase">{platform}</span>
                                                                    </div>
                                                                    <p className="text-xs text-white font-semibold">
                                                                        {platform === 'yelp' && data.rating
                                                                            ? `${data.rating}/5 (${data.reviewCount ?? 0} reviews)`
                                                                            : `${(data.followerCount ?? 0).toLocaleString()} followers`}
                                                                    </p>
                                                                    {data.lastPostRecency && (
                                                                        <p className="text-[10px] text-slate-500 mt-0.5">{data.lastPostRecency}</p>
                                                                    )}
                                                                </div>
                                                            );
                                                        })}
                                                    </div>

                                                    {/* Recommendation */}
                                                    {profile.socialProfileMetrics.summary.recommendation && (
                                                        <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-2.5">
                                                            <p className="text-[11px] text-indigo-300 leading-snug">{profile.socialProfileMetrics.summary.recommendation}</p>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {!profile.socialLinks?.instagram && !profile.socialLinks?.facebook && !profile.socialLinks?.twitter && !profile.socialLinks?.yelp && !profile.socialLinks?.tiktok && !profile.googleMapsUrl && !profile.socialProfileMetrics?.summary && (
                                                <div className="w-full p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-slate-400 text-sm text-center">
                                                    No social profiles found.
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            )}

                            {/* MENU TAB: menu link + delivery platforms */}
                            {activeTab === 'menu' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[140px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="menu" variant="dots" />
                                    ) : (
                                        <>
                                            {profile.menuUrl && (
                                                <a
                                                    href={profile.menuUrl}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="flex items-center gap-3 w-full px-4 py-3 rounded-xl bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 border border-indigo-500/20 transition-colors font-semibold"
                                                >
                                                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                                                    <span className="text-sm truncate">View Menu</span>
                                                    <svg className="w-3 h-3 ml-auto shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                                </a>
                                            )}
                                            {(profile.socialLinks?.grubhub || profile.socialLinks?.doordash || profile.socialLinks?.ubereats || profile.socialLinks?.seamless || profile.socialLinks?.toasttab) && (
                                                <>
                                                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-1">Order Online</p>
                                                    <div className="flex flex-wrap gap-2">
                                                        {profile.socialLinks?.grubhub && (
                                                            <a href={profile.socialLinks.grubhub} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-orange-500/10 text-orange-400 hover:bg-orange-500/20 border border-orange-500/20 transition-colors text-sm font-semibold">
                                                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
                                                                Grubhub
                                                            </a>
                                                        )}
                                                        {profile.socialLinks?.doordash && (
                                                            <a href={profile.socialLinks.doordash} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors text-sm font-semibold">
                                                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>
                                                                DoorDash
                                                            </a>
                                                        )}
                                                        {profile.socialLinks?.ubereats && (
                                                            <a href={profile.socialLinks.ubereats} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 border border-emerald-500/20 transition-colors text-sm font-semibold">
                                                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 4a6 6 0 110 12A6 6 0 0112 6z"/></svg>
                                                                Uber Eats
                                                            </a>
                                                        )}
                                                        {profile.socialLinks?.seamless && (
                                                            <a href={profile.socialLinks.seamless} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-violet-500/10 text-violet-400 hover:bg-violet-500/20 border border-violet-500/20 transition-colors text-sm font-semibold">
                                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                                                                Seamless
                                                            </a>
                                                        )}
                                                        {profile.socialLinks?.toasttab && (
                                                            <a href={profile.socialLinks.toasttab} target="_blank" rel="noreferrer" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 border border-amber-500/20 transition-colors text-sm font-semibold">
                                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                                                                Toast
                                                            </a>
                                                        )}
                                                    </div>
                                                </>
                                            )}
                                            {!profile.menuUrl && !profile.socialLinks?.grubhub && !profile.socialLinks?.doordash && !profile.socialLinks?.ubereats && !profile.socialLinks?.seamless && !profile.socialLinks?.toasttab && (
                                                <div className="w-full p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-slate-400 text-sm text-center">
                                                    <svg className="w-6 h-6 text-slate-500 mb-2 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                                                    No menu or ordering links found.
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            )}

                            {/* RIVALS TAB: unchanged */}
                            {activeTab === 'competitors' && (
                                <div className="space-y-3 animate-fade-in relative min-h-[140px]">
                                    {isDiscovering ? (
                                        <DiscoveryProgress phase="competitors" variant="dots" />
                                    ) : profile.competitors?.length ? (
                                        <div className="space-y-2">
                                            {profile.competitors.map((comp, i) => (
                                                <div key={i} className="flex flex-col gap-1.5 p-3 rounded-lg bg-black/30 border border-white/5 hover:border-indigo-500/30 transition-colors">
                                                    <span className="text-sm font-bold text-white leading-tight">{comp.name}</span>
                                                    {comp.url && (
                                                        <a href={comp.url} target="_blank" rel="noreferrer"
                                                            className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline truncate">
                                                            ↗ {comp.url.replace(/^https?:\/\/(www\.)?/, '')}
                                                        </a>
                                                    )}
                                                    {comp.reason && <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{comp.reason}</p>}
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="w-full p-4 flex flex-col items-center text-center justify-center rounded-xl bg-slate-800/50 border border-slate-700 min-h-[140px]">
                                            <svg className="w-6 h-6 text-slate-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                                            <p className="text-xs text-slate-400 font-medium whitespace-pre-wrap">No direct comparable rivals found{'\n'}in geographic boundary.</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* MARKET DASHBOARD OVERLAY (bottom) */}
            {dashboard && !isDiscovering && (
                <div className="absolute bottom-0 left-0 right-0 z-20 pointer-events-auto">
                    <div className="bg-gradient-to-t from-slate-900 via-slate-900/95 to-transparent pt-8 pb-4 px-4">
                        {/* Stat pills row */}
                        <div className="flex flex-wrap gap-2 mb-3">
                            {dashboard.stats?.medianIncome && (
                                <span className="text-[11px] px-2.5 py-1 rounded-full bg-white/10 text-white/90 font-medium backdrop-blur-sm border border-white/10">
                                    {dashboard.stats.medianIncome} income
                                </span>
                            )}
                            {dashboard.stats?.population && (
                                <span className="text-[11px] px-2.5 py-1 rounded-full bg-white/10 text-white/90 font-medium backdrop-blur-sm border border-white/10">
                                    {dashboard.stats.population} residents
                                </span>
                            )}
                            {dashboard.stats?.competitorCount !== undefined && (
                                <span className="text-[11px] px-2.5 py-1 rounded-full bg-white/10 text-white/90 font-medium backdrop-blur-sm border border-white/10">
                                    {dashboard.stats.competitorCount} competitors nearby
                                </span>
                            )}
                            {dashboard.confirmedSources ? (
                                <span className="text-[11px] px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 font-medium backdrop-blur-sm border border-indigo-400/20">
                                    {dashboard.confirmedSources} data sources active
                                </span>
                            ) : null}
                        </div>

                        {/* Competitors strip */}
                        {dashboard.competitors && dashboard.competitors.length > 0 && (
                            <div className="mb-3">
                                <span className="text-[10px] font-bold text-white/40 uppercase tracking-wider">Nearby Competitors</span>
                                <div className="flex gap-2 mt-1.5 overflow-x-auto pb-1 scrollbar-hide">
                                    {dashboard.competitors.slice(0, 6).map((c, i) => (
                                        <div key={i} className="flex-shrink-0 px-2.5 py-1.5 rounded-lg bg-white/5 border border-white/10 backdrop-blur-sm">
                                            <div className="text-xs font-semibold text-white/90 whitespace-nowrap">{c.name}</div>
                                            <div className="text-[10px] text-white/50">{c.cuisine || c.category} &middot; {c.distanceM}m</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Local buzz from pulse */}
                        {dashboard.pulseHeadline && (
                            <div className="px-3 py-2 rounded-lg bg-indigo-500/10 border border-indigo-400/20 backdrop-blur-sm">
                                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">This Week</span>
                                <p className="text-xs text-white/80 mt-0.5 leading-relaxed">{dashboard.pulseHeadline}</p>
                                {dashboard.events && dashboard.events.length > 0 && (
                                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                                        {dashboard.events.slice(0, 3).map((ev, i) => (
                                            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/60 border border-white/10">
                                                {ev.what}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function TruncatedText({ text }: { text: string }) {
    const [expanded, setExpanded] = useState(false);
    const [overflows, setOverflows] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const el = ref.current;
        if (el) setOverflows(el.scrollHeight > el.clientHeight + 2);
    }, [text]);

    return (
        <div className="relative bg-black/20 p-3 rounded-xl border border-white/5">
            <div
                ref={ref}
                className={`text-sm text-slate-300 leading-relaxed ${expanded ? '' : 'line-clamp-2'}`}
            >
                {text}
            </div>
            {overflows && (
                <button
                    onClick={() => setExpanded(v => !v)}
                    className="mt-1.5 flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                    {expanded ? 'Show less' : 'Read more'}
                    <svg
                        className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                </button>
            )}
        </div>
    );
}
