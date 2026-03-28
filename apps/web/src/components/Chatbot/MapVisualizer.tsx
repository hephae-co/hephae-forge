"use client";

import React, { useState, useEffect, useRef } from 'react';

import { BaseIdentity, EnrichedProfile, SocialPlatformMetrics } from '@/types/api';
import DiscoveryProgress from './DiscoveryProgress';
import ProfileBuilder from './ProfileBuilder';

// Data intelligence sources powering the pulse analysis
const INTELLIGENCE_SOURCES = [
    { name: 'BLS', label: 'Price Index', desc: 'Consumer Price Index for food & services', url: 'https://www.bls.gov/cpi/', tw: 'blue' },
    { name: 'USDA', label: 'Commodities', desc: 'Commodity price outlooks & food cost data', url: 'https://www.ers.usda.gov/data-products/food-price-outlook/', tw: 'green' },
    { name: 'Census', label: 'Demographics', desc: 'Population, income & poverty statistics', url: 'https://www.census.gov/topics/income-poverty.html', tw: 'violet' },
    { name: 'NWS', label: 'Weather', desc: 'National Weather Service 7-day forecasts', url: 'https://www.weather.gov/', tw: 'sky' },
    { name: 'FDA', label: 'Food Safety', desc: 'Food recalls & enforcement actions', url: 'https://www.fda.gov/food/recalls-outbreaks-emergencies', tw: 'red' },
    { name: 'SBA', label: 'Lending', desc: 'Small business loan activity by zip code', url: 'https://www.sba.gov/funding-programs/loans', tw: 'amber' },
    { name: 'OSM', label: 'Local Map', desc: 'OpenStreetMap competitor density', url: 'https://www.openstreetmap.org/', tw: 'emerald' },
    { name: 'Trends', label: 'Search', desc: 'Google Trends for local search demand', url: 'https://trends.google.com/', tw: 'orange' },
    { name: 'CDC', label: 'Health', desc: 'PLACES local health & lifestyle metrics', url: 'https://www.cdc.gov/places/', tw: 'teal' },
    { name: 'IRS', label: 'Income', desc: 'IRS SOI adjusted gross income by zip', url: 'https://www.irs.gov/statistics/soi-tax-stats-individual-income-tax-statistics', tw: 'slate' },
    { name: 'QCEW', label: 'Employment', desc: 'Quarterly Census of Employment & Wages', url: 'https://www.bls.gov/cew/', tw: 'indigo' },
    { name: 'News', label: 'Local News', desc: 'RSS feeds: local papers, Patch, TAPinto', url: 'https://patch.com/', tw: 'rose' },
] as const;

// Colour map for TW classes (can't use dynamic tw class names)
const SOURCE_STYLES: Record<string, { badge: string; text: string; border: string }> = {
    blue:   { badge: 'bg-blue-500/10',   text: 'text-blue-300',   border: 'border-blue-500/25' },
    green:  { badge: 'bg-green-500/10',  text: 'text-green-300',  border: 'border-green-500/25' },
    violet: { badge: 'bg-violet-500/10', text: 'text-violet-300', border: 'border-violet-500/25' },
    sky:    { badge: 'bg-sky-500/10',    text: 'text-sky-300',    border: 'border-sky-500/25' },
    red:    { badge: 'bg-red-500/10',    text: 'text-red-300',    border: 'border-red-500/25' },
    amber:  { badge: 'bg-amber-500/10',  text: 'text-amber-300',  border: 'border-amber-500/25' },
    emerald:{ badge: 'bg-emerald-500/10',text: 'text-emerald-300',border: 'border-emerald-500/25' },
    orange: { badge: 'bg-orange-500/10', text: 'text-orange-300', border: 'border-orange-500/25' },
    teal:   { badge: 'bg-teal-500/10',   text: 'text-teal-300',   border: 'border-teal-500/25' },
    slate:  { badge: 'bg-slate-500/10',  text: 'text-slate-300',  border: 'border-slate-500/25' },
    indigo: { badge: 'bg-indigo-500/10', text: 'text-indigo-300', border: 'border-indigo-500/25' },
    rose:   { badge: 'bg-rose-500/10',   text: 'text-rose-300',   border: 'border-rose-500/25' },
};

// OSM categories that are never relevant as nearby competitors for any business type
const IRRELEVANT_NEARBY_CATEGORIES = new Set([
    // Fuel & automotive
    'fuel', 'gas_station', 'car_wash', 'car_repair', 'car_rental', 'tyres',
    // Retail unrelated to food/service
    'supermarket', 'convenience', 'grocery', 'hardware', 'electronics',
    'clothing', 'furniture', 'department_store',
    // Finance & services
    'bank', 'atm', 'insurance', 'lawyer', 'real_estate', 'post_office',
    // Healthcare
    'pharmacy', 'drug_store', 'hospital', 'clinic', 'dentist', 'doctor', 'veterinary',
    // Other
    'school', 'library', 'place_of_worship', 'hotel', 'lodging',
    'parking', 'charging_station', 'recycling',
]);

function filterRelevantCompetitors(
    competitors: DashboardData['competitors'],
    businessType?: string,
): DashboardData['competitors'] {
    if (!competitors?.length) return competitors;
    const lowerType = (businessType || '').toLowerCase();

    return competitors.filter(c => {
        const cat = (c.cuisine || c.category || '').toLowerCase();
        // Always strip universally irrelevant categories
        if (IRRELEVANT_NEARBY_CATEGORIES.has(cat)) return false;
        // For non-food businesses, also strip pure food amenities
        const isFoodBiz = lowerType.includes('restaurant') || lowerType.includes('cafe') ||
            lowerType.includes('bakery') || lowerType.includes('bar') || lowerType.includes('diner') ||
            lowerType.includes('pizza') || lowerType.includes('grill') || lowerType.includes('food') ||
            lowerType.includes('meal') || lowerType.includes('bistro') || lowerType.includes('steak') ||
            lowerType.includes('sushi') || lowerType.includes('coffee') || lowerType.includes('kitchen');
        if (!isFoodBiz && (cat === 'fast_food' || cat === 'pub' || cat === 'bar')) return false;
        return true;
    });
}

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
    ctaSlot?: React.ReactNode;
    isAuthenticated?: boolean;
    onSignIn?: () => void;
}

type ActiveTab = 'overview' | 'profile' | 'theme' | 'contact' | 'social' | 'menu' | 'competitors';

/** Convert snake_case or kebab-case to Title Case (e.g. "dairy_margin_swap" → "Dairy Margin Swap") */
function humanize(s: string): string {
    return s.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function MapVisualizer({ lat, lng, businessName, business, isDiscovering = false, dashboard, ctaSlot, isAuthenticated = false, onSignIn }: MapVisualizerProps) {
    const [zoomLevel, setZoomLevel] = useState<number>(15);
    const [resetKey, setResetKey] = useState(0);
    const [activeTab, setActiveTab] = useState<ActiveTab>('overview');
    const [logoError, setLogoError] = useState(false);
    const [profileCollapsed, setProfileCollapsed] = useState(false);
    const [carouselIdx, setCarouselIdx] = useState(0);
    const [carouselExpanded, setCarouselExpanded] = useState(false);
    const [showSourcesPopover, setShowSourcesPopover] = useState(false);

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

    // Auto-select overview when enrichment completes (if overview has data)
    useEffect(() => {
        if (!isDiscovering) {
            if (hasOverview) {
                setActiveTab('overview');
            } else if (TABS.length && !TABS.find(t => t.id === activeTab)) {
                setActiveTab(TABS[0].id);
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isDiscovering]);

    // Build carousel items from dashboard data — each can carry source links
    type CarouselItem = { label: string; text: string; links?: { label: string; url: string }[] };
    const carouselItems: CarouselItem[] = [];
    if (dashboard) {
        if (dashboard.pulseHeadline) carouselItems.push({
            label: 'This Week',
            text: dashboard.pulseHeadline,
            links: [
                { label: 'BLS CPI', url: 'https://www.bls.gov/cpi/' },
                { label: 'USDA ERS', url: 'https://www.ers.usda.gov/data-products/food-price-outlook/' },
                { label: 'NWS Forecast', url: 'https://www.weather.gov/' },
            ],
        });
        (dashboard.topInsights || []).slice(0, 2).forEach(i =>
            carouselItems.push({
                label: 'Intelligence',
                text: `${humanize(i.title)} — ${i.recommendation}`,
                links: [
                    { label: 'BLS Data', url: 'https://www.bls.gov/cpi/' },
                    { label: 'USDA Prices', url: 'https://www.ers.usda.gov/' },
                    { label: 'SBA Loans', url: 'https://www.sba.gov/funding-programs/loans' },
                ],
            })
        );
        (dashboard.events || []).slice(0, 2).forEach(e =>
            carouselItems.push({
                label: 'Local Event',
                text: e.what + (e.when ? ` · ${e.when}` : ''),
                links: dashboard.stats?.patchUrl
                    ? [{ label: 'Patch News', url: dashboard.stats.patchUrl }]
                    : [{ label: 'Google Events', url: 'https://www.google.com/search?q=local+events+near+me' }],
            })
        );
        if (dashboard.communityBuzz) carouselItems.push({
            label: 'Community',
            text: dashboard.communityBuzz,
            links: dashboard.stats?.patchUrl
                ? [{ label: 'Patch', url: dashboard.stats.patchUrl }]
                : [{ label: 'Local News', url: 'https://patch.com/' }],
        });
    }

    // Auto-advance carousel every 5 seconds
    useEffect(() => {
        if (carouselItems.length <= 1) return;
        const timer = setInterval(() => setCarouselIdx(i => (i + 1) % carouselItems.length), 5000);
        return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [carouselItems.length]);

    return (
        <div className="relative flex flex-col w-full h-full bg-slate-900 overflow-hidden">

            {/* ── MINI MAP (fixed height) ───────────────────────────────────── */}
            <div className="flex-shrink-0 px-3 pt-3 pb-1">
            <div className="relative h-[250px] bg-slate-800 overflow-hidden rounded-2xl border border-white/10 shadow-xl">
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
                />

                {/* Business pin — centered */}
                <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                    <div className="relative flex flex-col items-center">
                        <div className="absolute w-10 h-10 bg-indigo-500 rounded-full animate-ping opacity-40" />
                        <div className="relative w-3.5 h-3.5 bg-indigo-400 rounded-full border-2 border-white shadow-[0_0_20px_rgba(255,255,255,0.9)]" />
                        <div className="mt-2 text-indigo-100 font-bold text-xs bg-slate-900/90 px-2.5 py-1 rounded-md border border-indigo-500/50 shadow backdrop-blur whitespace-nowrap max-w-[180px] truncate">
                            {businessName}
                        </div>
                    </div>
                </div>

                {/* Controls — compact, top-right of mini map */}
                <div className="absolute top-2 right-2 z-30 flex flex-col items-center gap-1.5">
                    <button
                        onClick={() => setResetKey(p => p + 1)}
                        className="w-7 h-7 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shadow-lg border border-indigo-400/50"
                        title="Re-Center Map"
                    >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                    </button>
                    <div className="flex flex-col">
                        <button onClick={() => handleZoom(1)} className="bg-white text-gray-700 w-7 h-7 rounded-t-md shadow hover:bg-gray-100 font-bold flex items-center justify-center border-b border-gray-200 text-sm">+</button>
                        <button onClick={() => handleZoom(-1)} className="bg-white text-gray-700 w-7 h-7 rounded-b-md shadow hover:bg-gray-100 font-bold flex items-center justify-center text-sm">−</button>
                    </div>
                </div>
            </div>
            </div>

            {/* ── SCROLLABLE CONTENT PANEL ─────────────────────────────────── */}
            <div className="flex-1 overflow-y-auto scrollbar-hide divide-y divide-white/5">

            {/* PROFILE CARD — inline, full width */}
            {business && (
                <div className="bg-slate-900 animate-fade-in-up">

                    {/* HEADER — compact for everyone */}
                    <div className={`px-3 pt-3 ${!isAuthenticated || profileCollapsed ? 'pb-3' : 'pb-2'} ${!isAuthenticated || profileCollapsed ? '' : 'border-b border-white/10'}`}>
                        <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center border border-indigo-500/50 shrink-0">
                                <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                            </div>
                            <div className="min-w-0 flex-1">
                                <h2 className="text-white font-bold text-sm leading-tight truncate">{business.name}</h2>
                                <p className="text-slate-400 text-[10px] leading-tight mt-0.5 truncate">{business.address}</p>
                            </div>
                            {isAuthenticated && (
                                <button
                                    onClick={() => setProfileCollapsed(v => !v)}
                                    className="w-6 h-6 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors shrink-0"
                                    title={profileCollapsed ? 'Expand' : 'Collapse'}
                                >
                                    <svg
                                        className={`w-3 h-3 text-slate-400 transition-transform duration-300 ${profileCollapsed ? 'rotate-180' : ''}`}
                                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                    >
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" />
                                    </svg>
                                </button>
                            )}
                        </div>

                        {/* GUEST: Sign-in CTA */}
                        {!isAuthenticated && !isDiscovering && (
                            <button
                                onClick={onSignIn}
                                className="w-full mt-2.5 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-500/15 border border-indigo-400/30 hover:bg-indigo-500/25 hover:border-indigo-400/50 transition-all text-left group"
                            >
                                <svg className="w-4 h-4 text-indigo-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
                                <div className="min-w-0">
                                    <p className="text-xs font-bold text-indigo-300">Sign in to build a full profile</p>
                                    <p className="text-[10px] text-slate-500 leading-tight">Discover menu, social profiles, competitors & more</p>
                                </div>
                                <svg className="w-3.5 h-3.5 text-indigo-400/50 shrink-0 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/></svg>
                            </button>
                        )}

                        {/* AUTHENTICATED: Profile tabs */}
                        {isAuthenticated && (
                            <div className={`flex gap-0.5 p-0.5 bg-black/40 rounded-lg overflow-x-auto scrollbar-hide transition-all duration-300 ${profileCollapsed ? 'max-h-0 opacity-0 overflow-hidden mt-0 p-0' : 'max-h-10 opacity-100 mt-2'}`}>
                                {TABS.map(tab => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex-1 py-1 text-[10px] font-bold rounded-md transition-colors leading-tight flex-shrink-0 ${activeTab === tab.id ? 'bg-indigo-500 text-white shadow' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        {tab.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* TAB CONTENT — authenticated users only */}
                    {isAuthenticated && (
                    <div className={`transition-all duration-300 ${profileCollapsed ? 'max-h-0 opacity-0 overflow-hidden p-0' : 'opacity-100 p-3 pt-2 space-y-2'}`}>

                            {/* OVERVIEW TAB: AI Overview summary */}
                            {activeTab === 'overview' && (
                                <div className="space-y-2 animate-fade-in relative min-h-[80px]">
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
                                <div className="space-y-2 animate-fade-in relative min-h-[60px]">
                                    <div className="flex items-start gap-2 text-slate-300 bg-black/20 px-2.5 py-2 rounded-lg border border-white/5">
                                        <svg className="w-3.5 h-3.5 mt-0.5 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                        <p className="text-xs leading-snug">{business.address}</p>
                                    </div>
                                    <div className="flex items-center gap-2 text-slate-300 bg-black/20 px-2.5 py-2 rounded-lg border border-white/5">
                                        <svg className="w-3.5 h-3.5 text-slate-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path></svg>
                                        <a href={business.officialUrl} target="_blank" rel="noreferrer" className="text-xs text-indigo-400 hover:text-indigo-300 truncate underline decoration-indigo-500/30 underline-offset-2">
                                            {business.officialUrl.replace(/^https?:\/\/(www\.)?/, '')}
                                        </a>
                                    </div>
                                </div>
                            )}

                            {/* THEME TAB: logo, favicon, colors, persona */}
                            {activeTab === 'theme' && (
                                <div className="space-y-2 animate-fade-in relative min-h-[80px]">
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
                                <div className="space-y-2 animate-fade-in relative min-h-[60px]">
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
                                <div className="space-y-2 animate-fade-in relative min-h-[60px]">
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
                                <div className="space-y-2 animate-fade-in relative min-h-[60px]">
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
                                <div className="space-y-2 animate-fade-in relative min-h-[60px]">
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
                    )}
                    </div>
            )}

            {/* PROFILE BUILDER — action buttons for authenticated users */}
            {business && isAuthenticated && !isDiscovering && (
                <ProfileBuilder business={business} />
            )}

            {/* MARKET INTELLIGENCE — inline in scroll section */}
            {dashboard && !isDiscovering && (
                <div className="p-3 space-y-2.5">

                    {/* ── Intelligence Sources Popover (absolute overlay) ── */}
                    {showSourcesPopover && (
                        <>
                            <div className="absolute inset-0 z-50" onClick={() => setShowSourcesPopover(false)} />
                            <div className="absolute bottom-0 left-3 right-3 mb-16 z-50 bg-slate-900/96 backdrop-blur-xl border border-white/10 rounded-2xl p-3 shadow-2xl animate-fade-in-up">
                                <div className="flex items-center justify-between mb-2.5">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[10px] font-bold text-white/50 uppercase tracking-wider">Intelligence Inputs</span>
                                        {dashboard.confirmedSources ? (
                                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/25">{dashboard.confirmedSources} active</span>
                                        ) : null}
                                    </div>
                                    <button onClick={() => setShowSourcesPopover(false)} className="w-5 h-5 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors">
                                        <svg className="w-2.5 h-2.5 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M6 18L18 6M6 6l12 12"/></svg>
                                    </button>
                                </div>
                                <div className="grid grid-cols-4 gap-1.5">
                                    {INTELLIGENCE_SOURCES.map(src => {
                                        const s = SOURCE_STYLES[src.tw];
                                        return (
                                            <a key={src.name} href={src.url} target="_blank" rel="noopener noreferrer" title={src.desc}
                                                className={`flex flex-col items-center px-2 py-2 rounded-xl ${s.badge} border ${s.border} hover:brightness-125 transition-all group`}>
                                                <span className={`text-[10px] font-bold ${s.text} whitespace-nowrap`}>{src.name}</span>
                                                <span className="text-[8px] text-white/35 whitespace-nowrap group-hover:text-white/55 transition-colors mt-0.5">{src.label}</span>
                                            </a>
                                        );
                                    })}
                                </div>
                            </div>
                        </>
                    )}

                    {/* ── Intelligence Carousel (expandable) ───────────── */}
                        {carouselItems.length > 0 && (() => {
                            const item = carouselItems[carouselIdx];
                            return (
                                <div className={`rounded-xl border backdrop-blur-sm transition-all duration-300 ${carouselExpanded ? 'bg-indigo-500/15 border-indigo-400/30' : 'bg-indigo-500/8 border-indigo-400/15'}`}>
                                    {/* Header row */}
                                    <div
                                        className="flex items-center justify-between px-3 pt-2.5 pb-1.5 cursor-pointer select-none"
                                        onClick={() => setCarouselExpanded(v => !v)}
                                    >
                                        <div className="flex items-center gap-1.5">
                                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse shrink-0" />
                                            <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider">{item?.label}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {carouselItems.length > 1 && (
                                                <div className="flex gap-0.5">
                                                    {carouselItems.map((_, i) => (
                                                        <span key={i} className={`w-1 h-1 rounded-full transition-colors ${i === carouselIdx ? 'bg-indigo-400' : 'bg-white/20'}`} />
                                                    ))}
                                                </div>
                                            )}
                                            <svg className={`w-3 h-3 text-indigo-400/60 transition-transform duration-200 ${carouselExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"/></svg>
                                        </div>
                                    </div>

                                    {/* Text */}
                                    <p className={`text-xs text-white/85 leading-relaxed px-3 pb-2 ${carouselExpanded ? '' : 'line-clamp-3'}`}>
                                        {item?.text}
                                    </p>

                                    {/* Expanded: source links + prev/next nav */}
                                    {carouselExpanded && item?.links && item.links.length > 0 && (
                                        <div className="flex items-center justify-between px-3 pb-2.5 pt-1 border-t border-white/5">
                                            <div className="flex flex-wrap gap-1.5">
                                                {item.links.map(link => (
                                                    <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer"
                                                        className="flex items-center gap-1 text-[10px] font-semibold text-indigo-300 hover:text-indigo-200 bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/25 px-2 py-0.5 rounded-full transition-all"
                                                        onClick={e => e.stopPropagation()}>
                                                        {link.label}
                                                        <svg className="w-2.5 h-2.5 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                                                    </a>
                                                ))}
                                            </div>
                                            {carouselItems.length > 1 && (
                                                <div className="flex gap-1 shrink-0 ml-2">
                                                    <button onClick={e => { e.stopPropagation(); setCarouselIdx(i => (i - 1 + carouselItems.length) % carouselItems.length); }}
                                                        className="w-5 h-5 rounded-full bg-white/8 hover:bg-white/15 flex items-center justify-center transition-colors">
                                                        <svg className="w-2.5 h-2.5 text-white/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"/></svg>
                                                    </button>
                                                    <button onClick={e => { e.stopPropagation(); setCarouselIdx(i => (i + 1) % carouselItems.length); }}
                                                        className="w-5 h-5 rounded-full bg-white/8 hover:bg-white/15 flex items-center justify-center transition-colors">
                                                        <svg className="w-2.5 h-2.5 text-white/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/></svg>
                                                    </button>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })()}

                        {/* ── Nearby Competitors ───────────────────────────── */}
                        {(() => {
                            const filtered = filterRelevantCompetitors(dashboard.competitors, (business as any)?.businessType || businessName);
                            if (!filtered?.length) return null;
                            return (
                                <div>
                                    <p className="text-[10px] font-bold text-white/35 uppercase tracking-wider mb-1.5">Nearby Businesses</p>
                                    <div className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide">
                                        {filtered.slice(0, 6).map((c, i) => (
                                            <div key={i} className="flex-shrink-0 px-2 py-1.5 rounded-lg bg-white/5 border border-white/10 backdrop-blur-sm">
                                                <div className="text-[11px] font-semibold text-white/90 whitespace-nowrap">{c.name}</div>
                                                <div className="text-[9px] text-white/45 mt-0.5">{(c.cuisine || c.category || '').replace(/_/g, ' ')} · {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })()}

                        {/* ── Stat pills + sources icon ─────────────────────── */}
                        <div className="flex items-center justify-between gap-2">
                            <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
                                {dashboard.stats?.city && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/8 text-white/55 font-medium border border-white/8">
                                        📍 {dashboard.stats.city}{dashboard.stats.state ? `, ${dashboard.stats.state}` : ''}
                                    </span>
                                )}
                                {dashboard.stats?.medianIncome && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300/75 font-medium border border-emerald-500/15">
                                        {dashboard.stats.medianIncome} income
                                    </span>
                                )}
                                {dashboard.stats?.population && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/8 text-white/55 font-medium border border-white/8">
                                        {dashboard.stats.population} residents
                                    </span>
                                )}
                                {dashboard.stats?.competitorCount !== undefined && (
                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-300/75 font-medium border border-red-500/15">
                                        {dashboard.stats.competitorCount} rivals nearby
                                    </span>
                                )}
                            </div>
                            {/* Sources toggle icon */}
                            <button
                                onClick={() => setShowSourcesPopover(v => !v)}
                                title="View intelligence data sources"
                                className={`flex-shrink-0 flex items-center gap-1 px-2 py-1 rounded-full border transition-all ${showSourcesPopover ? 'bg-indigo-500/20 border-indigo-400/40 text-indigo-300' : 'bg-white/5 border-white/10 text-white/40 hover:text-white/60 hover:bg-white/10'}`}
                            >
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                                <span className="text-[9px] font-bold uppercase tracking-wider">Sources</span>
                            </button>
                        </div>

                    </div>
            )}


            </div>{/* end scrollable content panel */}

            {/* ── CTA Actions — pinned to bottom of panel, outside scroll ── */}
            {ctaSlot && !isDiscovering && (
                <div className="flex-shrink-0 border-t-2 border-white/10 bg-slate-950 px-4 py-4 flex flex-wrap gap-2">
                    {ctaSlot}
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
