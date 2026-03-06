"use client";

import React, { useEffect, useState } from 'react';

interface ExplainerModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function ExplainerModal({ isOpen, onClose }: ExplainerModalProps) {
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
    }, [isOpen]);

    if (!mounted || !isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-fade-in-up">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm cursor-pointer"
                onClick={onClose}
            ></div>

            {/* Modal Content */}
            <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-white rounded-3xl shadow-[0_20px_60px_-15px_rgba(0,0,0,0.3)] border border-slate-100 flex flex-col">

                {/* Header */}
                <div className="sticky top-0 z-10 flex items-center justify-between px-8 py-6 bg-white/80 backdrop-blur-xl border-b border-slate-50">
                    <div>
                        <h2 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-3">
                            <span className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                            </span>
                            Agent Swarm Architecture
                        </h2>
                        <p className="text-sm font-medium text-slate-500 mt-1">Understanding Hephae Hub's Cognitive Engine</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                    >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>

                {/* Body */}
                <div className="p-8 space-y-12">
                    {/* The Swarm Concept */}
                    <section>
                        <p className="text-lg text-slate-600 leading-relaxed mb-6">
                            Hephae Hub isn't a traditional application. It's an **Agentic Orchestrator** powered by the **Hephae ADK (Agentic Development Kit)**. When you submit a request, it triggers a specialized "swarm" of AI agents that execute complex capabilities completely autonomously.
                        </p>
                    </section>

                    {/* Discovery Swarm */}
                    <section className="relative">
                        <div className="absolute left-6 top-0 bottom-0 w-px bg-indigo-100"></div>
                        <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-3 relative z-10">
                            <span className="w-12 h-12 rounded-2xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-lg shadow-indigo-500/20">Phase 1</span>
                            Parallel Discovery
                        </h3>
                        <div className="ml-16 grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="p-5 rounded-2xl bg-white border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center"><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div>
                                    <h4 className="font-bold text-slate-900">LocatorAgent</h4>
                                </div>
                                <p className="text-sm text-slate-500">Uses natural language processing and Google Search APIs to accurately identify the physical business, rendering the initial Map UI.</p>
                            </div>
                            <div className="p-5 rounded-2xl bg-indigo-50 border border-indigo-100 shadow-sm">
                                <div className="flex items-center gap-3 mb-2">
                                    <div className="w-8 h-8 rounded-full bg-indigo-200 text-indigo-700 flex items-center justify-center"><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg></div>
                                    <h4 className="font-bold text-indigo-900">The Discovery Sub-Agents</h4>
                                </div>
                                <p className="text-sm text-indigo-700 leading-relaxed">
                                    Once located, an orchestrator launches 3 agents simultaneously:
                                    <br />• <strong>MenuAgent</strong>: Uses Playwright to organically click through the site and screenshot the true menu.
                                    <br />• <strong>SocialAgent</strong>: Mines social footprints (IG/FB).
                                    <br />• <strong>MapsAgent</strong>: Establishes official Google Maps link.
                                </p>
                            </div>
                        </div>
                    </section>


                    {/* Margin Surgery Swarm */}
                    <section className="relative">
                        <div className="absolute left-6 top-0 bottom-0 w-px bg-rose-100"></div>
                        <h3 className="text-xl font-bold text-slate-900 mb-6 flex items-center gap-3 relative z-10">
                            <span className="w-12 h-12 rounded-2xl bg-rose-500 text-white flex items-center justify-center text-lg shadow-lg shadow-rose-500/20">Phase 2</span>
                            Execute Playbook: Menu Margins
                        </h3>
                        <div className="ml-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <div className="p-5 rounded-2xl bg-white border border-slate-100 shadow-sm">
                                <h4 className="font-bold text-slate-900 text-sm mb-1 uppercase tracking-wider">Vision Intake</h4>
                                <p className="text-sm text-slate-500">Passes the crawled Menu screenshot to Gemini 2.5 Flash to perfectly extract items, descriptions, and current pricing.</p>
                            </div>
                            <div className="p-5 rounded-2xl bg-white border border-slate-100 shadow-sm">
                                <h4 className="font-bold text-slate-900 text-sm mb-1 uppercase tracking-wider">Benchmarker</h4>
                                <p className="text-sm text-slate-500">Cross-references every single menu item against 10 similar restaurants in the same zip code using live Google Search data.</p>
                            </div>
                            <div className="p-5 rounded-2xl bg-white border border-slate-100 shadow-sm">
                                <h4 className="font-bold text-slate-900 text-sm mb-1 uppercase tracking-wider">Commodity Watchdog</h4>
                                <p className="text-sm text-slate-500">Retrieves real-time macroeconomic inflation data (e.g. eggs, coffee) to adjust profitability curves.</p>
                            </div>
                        </div>
                        <div className="ml-16 mt-4 p-5 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl text-white">
                            <div className="flex items-center gap-3 mb-2">
                                <div className="w-8 h-8 rounded-full bg-slate-800 text-emerald-400 flex items-center justify-center"><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg></div>
                                <h4 className="font-bold">The Surgeon (Synthesis)</h4>
                            </div>
                            <p className="text-sm text-slate-300">Synthesizes all 3 parallel datastreams to calculate the exact structural profit leakage, outputting the final dashboard.</p>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
