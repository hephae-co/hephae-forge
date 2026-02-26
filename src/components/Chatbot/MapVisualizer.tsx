"use client";

import React, { useState, useEffect } from 'react';

import { BaseIdentity, EnrichedProfile } from '@/lib/agents/core/types';

interface MapVisualizerProps {
    lat: number;
    lng: number;
    businessName: string;
    business?: BaseIdentity | EnrichedProfile;
    isDiscovering?: boolean;
}

export default function MapVisualizer({ lat, lng, businessName, business, isDiscovering = false }: MapVisualizerProps) {
    const [zoomLevel, setZoomLevel] = useState<number>(15);
    const [resetKey, setResetKey] = useState(0);

    const getUrl = () => {
        const baseEmbed = `https://maps.google.com/maps?ie=UTF8&iwloc=&output=embed`;
        return `${baseEmbed}&z=${zoomLevel}&q=${lat},${lng}&t=m`;
    };

    const getMapStyle = () => {
        return {
            filter: 'invert(85%) hue-rotate(180deg) brightness(1.1) contrast(95%) saturate(120%)',
            border: 0,
            opacity: 1
        };
    };

    const handleZoom = (delta: number) => {
        setZoomLevel(prev => Math.min(Math.max(prev + delta, 13), 18));
    }

    // Effect to re-center when coordinates change
    useEffect(() => {
        setResetKey(prev => prev + 1);
    }, [lat, lng]);

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
                title="Traffic Intelligence Map"
                tabIndex={-1}
            ></iframe>

            {/* CONTROLS (Right Side) */}
            <div className="absolute bottom-20 right-6 z-30 flex flex-col items-center gap-4">
                {/* Reset View Button */}
                <button
                    onClick={() => setResetKey(p => p + 1)}
                    className="w-10 h-10 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center font-bold shadow-lg border border-indigo-400/50"
                    title="Re-Center Map"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                </button>

                {/* Zoom Controls */}
                <div className="flex flex-col gap-1">
                    <button onClick={() => handleZoom(1)} className="bg-white text-gray-700 w-10 h-10 rounded-t-lg shadow-lg hover:bg-gray-100 font-bold flex items-center justify-center border-b border-gray-200 text-lg">+</button>
                    <button onClick={() => handleZoom(-1)} className="bg-white text-gray-700 w-10 h-10 rounded-b-lg shadow-lg hover:bg-gray-100 font-bold flex items-center justify-center text-lg">-</button>
                </div>
            </div>

            {/* VISUALIZATION OVERLAY - STATIC CENTERED */}
            <div className="absolute inset-0 pointer-events-none z-10 flex items-center justify-center animate-fade-in">
                <div className="absolute inset-0 pointer-events-none mix-blend-screen overflow-visible flex items-center justify-center">

                    {/* Center Pin */}
                    <div className="absolute z-20 pointer-events-none">
                        <div className="relative flex items-center justify-center">
                            <div className="absolute w-12 h-12 bg-indigo-500 rounded-full animate-ping opacity-40"></div>
                            <div className="relative w-4 h-4 bg-indigo-400 rounded-full border-2 border-white shadow-[0_0_20px_rgba(255,255,255,0.9)]"></div>

                            <div className={`absolute top-full mt-2 text-indigo-100 font-bold text-sm bg-slate-900/90 px-3 py-1.5 rounded-md border border-indigo-500/50 shadow backdrop-blur whitespace-nowrap`}>
                                {businessName}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* GLASSMORPHISM DISCOVERY OVERLAY */}
            {business && (
                <div className="absolute top-8 left-8 z-40 animate-fade-in-up" style={{ animationDelay: '0.5s' }}>
                    <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 shadow-2xl rounded-2xl p-6 max-w-sm">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center border border-indigo-500/50">
                                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path></svg>
                            </div>
                            <div>
                                <h2 className="text-white font-bold text-lg leading-tight">{business.name}</h2>
                                {isDiscovering ? (
                                    <p className="text-amber-400 text-xs font-medium uppercase tracking-wider animate-pulse flex items-center gap-1 mt-0.5">
                                        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                        Running Sub-Agents...
                                    </p>
                                ) : (
                                    <p className="text-indigo-300 text-xs font-medium uppercase tracking-wider flex items-center gap-1 mt-0.5">
                                        <svg className="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                                        Profile Enriched
                                    </p>
                                )}
                            </div>
                        </div>

                        <div className="space-y-3">
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

                        {/* SOCIAL LINKS (Only show if enriched) */}
                        {!isDiscovering && 'socialLinks' in business && (
                            <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between">
                                <div className="flex gap-2">
                                    {(business as EnrichedProfile).socialLinks?.instagram && (
                                        <a href={(business as EnrichedProfile).socialLinks!.instagram} target="_blank" rel="noreferrer" className="w-8 h-8 rounded-full bg-pink-500/20 text-pink-400 hover:bg-pink-500/40 flex items-center justify-center transition-colors shadow-sm border border-pink-500/30" title="Instagram">
                                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" /></svg>
                                        </a>
                                    )}
                                    {(business as EnrichedProfile).socialLinks?.facebook && (
                                        <a href={(business as EnrichedProfile).socialLinks!.facebook} target="_blank" rel="noreferrer" className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 hover:bg-blue-500/40 flex items-center justify-center transition-colors shadow-sm border border-blue-500/30" title="Facebook">
                                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M9 8h-3v4h3v12h5v-12h3.642l.358-4h-4v-1.667c0-.955.192-1.333 1.115-1.333h2.885v-5h-3.808c-3.596 0-5.192 1.583-5.192 4.615v3.385z" /></svg>
                                        </a>
                                    )}
                                    {(business as EnrichedProfile).socialLinks?.twitter && (
                                        <a href={(business as EnrichedProfile).socialLinks!.twitter} target="_blank" rel="noreferrer" className="w-8 h-8 rounded-full bg-sky-500/20 text-sky-400 hover:bg-sky-500/40 flex items-center justify-center transition-colors shadow-sm border border-sky-500/30" title="X / Twitter">
                                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                                        </a>
                                    )}
                                </div>

                                {(business as EnrichedProfile).googleMapsUrl && (
                                    <a href={(business as EnrichedProfile).googleMapsUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full text-xs font-semibold transition-colors">
                                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
                                        View Map
                                    </a>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
