'use client';

import { useState, useEffect, useCallback } from 'react';
import {
    Map, ChevronDown, ChevronRight, Loader2, Trash2, RefreshCw,
    CheckCircle2, XCircle, Pause,
} from 'lucide-react';

type AreaPhase = 'resolving' | 'researching' | 'industry_intel' | 'local_sector_analysis' | 'summarizing' | 'completed' | 'failed';

interface AreaRun {
    id: string;
    area: string;
    businessType: string;
    areaKey?: string;
    zipCodes: string[];
    completedZipCodes: string[];
    failedZipCodes: string[];
    phase: AreaPhase;
    summary?: any;
    createdAt: string;
    updatedAt: string;
    lastError?: string;
}

function phaseBadge(phase: AreaPhase) {
    switch (phase) {
        case 'completed':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-200"><CheckCircle2 className="w-3 h-3" /> Done</span>;
        case 'failed':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200"><XCircle className="w-3 h-3" /> Failed</span>;
        case 'summarizing':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200"><Pause className="w-3 h-3" /> Synthesizing</span>;
        case 'industry_intel':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-cyan-50 text-cyan-600 border border-cyan-200"><Loader2 className="w-3 h-3 animate-spin" /> Industry Intel</span>;
        case 'local_sector_analysis':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 border border-violet-200"><Loader2 className="w-3 h-3 animate-spin" /> Sector Analysis</span>;
        default:
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200"><Loader2 className="w-3 h-3 animate-spin" /> {phase}</span>;
    }
}

const ACTIVE_PHASES: AreaPhase[] = ['resolving', 'researching', 'industry_intel', 'local_sector_analysis', 'summarizing'];

export default function AreaResearchBrowser() {
    const [runs, setRuns] = useState<AreaRun[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [rerunning, setRerunning] = useState<string | null>(null);

    const fetchRuns = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/area-research');
            if (res.ok) setRuns(await res.json());
        } catch { /* silent */ }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchRuns(); }, [fetchRuns]);

    const handleDelete = async (areaId: string) => {
        setDeletingId(areaId);
        try {
            const res = await fetch(`/api/area-research/${areaId}`, { method: 'DELETE' });
            if (res.ok) {
                setRuns(prev => prev.filter(r => r.id !== areaId));
                if (expandedId === areaId) setExpandedId(null);
            } else {
                const err = await res.json();
                alert(err.error || 'Delete failed');
            }
        } catch { /* silent */ }
        finally { setDeletingId(null); setConfirmingId(null); }
    };

    const handleRerun = async (run: AreaRun) => {
        setRerunning(run.id);
        try {
            const res = await fetch('/api/area-research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ area: run.area, businessType: run.businessType }),
            });
            if (res.ok) {
                await fetchRuns();
            }
        } catch { /* silent */ }
        finally { setRerunning(null); }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    <Map className="w-5 h-5 text-indigo-500" />
                    Area / County Research Runs
                </h3>
                <button onClick={fetchRuns} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded border border-gray-200 hover:border-gray-300 transition-colors flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> Refresh
                </button>
            </div>

            {loading && (
                <div className="text-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                </div>
            )}

            {!loading && runs.length === 0 && (
                <div className="text-center py-12 border border-dashed border-gray-300 rounded-xl text-gray-400">
                    <Map className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>No area research runs yet.</p>
                </div>
            )}

            {!loading && runs.length > 0 && (
                <div className="space-y-2">
                    {runs.map(run => {
                        const isExpanded = expandedId === run.id;
                        const isConfirming = confirmingId === run.id;
                        const isDeleting = deletingId === run.id;
                        const isActive = ACTIVE_PHASES.includes(run.phase);

                        return (
                            <div
                                key={run.id}
                                className={`relative bg-white border rounded-lg transition-all ${
                                    isConfirming ? 'border-red-200 bg-red-50' : 'border-gray-200 hover:shadow-md hover:border-gray-300'
                                }`}
                            >
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : run.id)}
                                    className="w-full text-left p-4"
                                    disabled={isConfirming || isDeleting}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            {isExpanded
                                                ? <ChevronDown className="w-4 h-4 text-gray-400" />
                                                : <ChevronRight className="w-4 h-4 text-gray-400" />
                                            }
                                            <span className="text-sm font-semibold text-gray-800">{run.area}</span>
                                            <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">
                                                {run.businessType}
                                            </span>
                                            {phaseBadge(run.phase)}
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                                {run.zipCodes.length} zips
                                            </span>
                                            <span className="text-xs text-gray-400">
                                                {new Date(run.createdAt).toLocaleDateString()} {new Date(run.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                    </div>
                                    {run.lastError && (
                                        <p className="text-xs text-red-500 mt-1 ml-7 truncate">{run.lastError}</p>
                                    )}
                                </button>

                                {/* Action buttons */}
                                <div className="absolute top-4 right-4 flex items-center gap-1">
                                    {!isActive && !isConfirming && !isDeleting && (
                                        <>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleRerun(run); }}
                                                disabled={rerunning === run.id}
                                                className="p-1.5 text-gray-300 hover:text-indigo-500 hover:bg-indigo-50 rounded transition-colors"
                                                title="Re-run"
                                            >
                                                <RefreshCw className={`w-4 h-4 ${rerunning === run.id ? 'animate-spin' : ''}`} />
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setConfirmingId(run.id); }}
                                                className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                                title="Delete run"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </>
                                    )}
                                </div>

                                {/* Delete confirmation */}
                                {isConfirming && !isDeleting && (
                                    <div className="mx-4 mb-4 flex items-center gap-3 pt-3 border-t border-red-200">
                                        <span className="text-xs text-red-500">Delete this area research?</span>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(run.id); }}
                                            className="px-3 py-1 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-500 transition-colors"
                                        >
                                            Confirm
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); setConfirmingId(null); }}
                                            className="px-3 py-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                )}

                                {isDeleting && (
                                    <div className="mx-4 mb-4 flex items-center gap-2 pt-3 border-t border-red-200">
                                        <Loader2 className="w-3 h-3 animate-spin text-red-500" />
                                        <span className="text-xs text-red-500">Deleting...</span>
                                    </div>
                                )}

                                {/* Expanded summary */}
                                {isExpanded && run.summary && (
                                    <div className="px-4 pb-4 border-t border-gray-100">
                                        <div className="mt-4 space-y-3">
                                            {/* Market Opportunity */}
                                            <div className="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-lg">
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="text-xs font-semibold text-indigo-600 uppercase tracking-wider">Market Opportunity</span>
                                                    <span className="text-sm font-bold text-indigo-700">{run.summary.marketOpportunity?.score}/100</span>
                                                </div>
                                                <p className="text-sm text-gray-700">{run.summary.marketOpportunity?.narrative}</p>
                                            </div>

                                            {/* Key metrics row */}
                                            <div className="grid grid-cols-3 gap-2">
                                                <div className="p-2 bg-gray-50 rounded-lg text-center">
                                                    <div className="text-xs text-gray-500">Demographic Fit</div>
                                                    <div className="text-lg font-bold text-gray-800">{run.summary.demographicFit?.score || '—'}</div>
                                                </div>
                                                <div className="p-2 bg-gray-50 rounded-lg text-center">
                                                    <div className="text-xs text-gray-500">Competitive</div>
                                                    <div className="text-lg font-bold text-gray-800">{run.summary.competitiveLandscape?.score || '—'}</div>
                                                </div>
                                                <div className="p-2 bg-gray-50 rounded-lg text-center">
                                                    <div className="text-xs text-gray-500">Saturation</div>
                                                    <div className="text-sm font-semibold text-gray-700 capitalize">{run.summary.competitiveLandscape?.saturationLevel || '—'}</div>
                                                </div>
                                            </div>

                                            {/* Industry Intelligence */}
                                            {run.summary.industryIntelligence && (
                                                <div className="p-3 bg-gradient-to-r from-cyan-50 to-blue-50 border border-cyan-100 rounded-lg">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-xs font-semibold text-cyan-600 uppercase tracking-wider">Industry Intelligence</span>
                                                        <span className="text-sm font-bold text-cyan-700">{run.summary.industryIntelligence.score}/100</span>
                                                    </div>
                                                    <p className="text-sm text-gray-700">{run.summary.industryIntelligence.narrative}</p>
                                                    {run.summary.industryIntelligence.topChallenges?.length > 0 && (
                                                        <div className="mt-2">
                                                            <span className="text-xs text-cyan-600 font-medium">Challenges: </span>
                                                            <span className="text-xs text-gray-600">{run.summary.industryIntelligence.topChallenges.join(' | ')}</span>
                                                        </div>
                                                    )}
                                                    {run.summary.industryIntelligence.topOpportunities?.length > 0 && (
                                                        <div className="mt-1">
                                                            <span className="text-xs text-cyan-600 font-medium">Opportunities: </span>
                                                            <span className="text-xs text-gray-600">{run.summary.industryIntelligence.topOpportunities.join(' | ')}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Event Impact & Seasonal Patterns row */}
                                            {(run.summary.eventImpact || run.summary.seasonalPatterns) && (
                                                <div className="grid grid-cols-2 gap-2">
                                                    {run.summary.eventImpact && (
                                                        <div className="p-3 bg-orange-50 border border-orange-100 rounded-lg">
                                                            <span className="text-xs font-semibold text-orange-600 uppercase tracking-wider">Events & Foot Traffic</span>
                                                            <p className="text-xs text-gray-700 mt-1">{run.summary.eventImpact.narrative}</p>
                                                            {run.summary.eventImpact.upcomingEvents?.length > 0 && (
                                                                <div className="mt-2 flex flex-wrap gap-1">
                                                                    {run.summary.eventImpact.upcomingEvents.slice(0, 4).map((ev: string, i: number) => (
                                                                        <span key={i} className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded">{ev}</span>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                    {run.summary.seasonalPatterns && (
                                                        <div className="p-3 bg-sky-50 border border-sky-100 rounded-lg">
                                                            <span className="text-xs font-semibold text-sky-600 uppercase tracking-wider">Seasonal Patterns</span>
                                                            <p className="text-xs text-gray-700 mt-1">{run.summary.seasonalPatterns.narrative}</p>
                                                            {run.summary.seasonalPatterns.peakSeasons?.length > 0 && (
                                                                <div className="mt-2">
                                                                    <span className="text-xs text-sky-600 font-medium">Peak: </span>
                                                                    <span className="text-xs text-gray-600">{run.summary.seasonalPatterns.peakSeasons.join(', ')}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Pricing Environment */}
                                            {run.summary.pricingEnvironment && (
                                                <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-lg">
                                                    <span className="text-xs font-semibold text-emerald-600 uppercase tracking-wider">Pricing & Input Costs</span>
                                                    <p className="text-xs text-gray-700 mt-1">{run.summary.pricingEnvironment.narrative}</p>
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {run.summary.pricingEnvironment.risingCosts?.map((c: string, i: number) => (
                                                            <span key={i} className="text-xs bg-red-100 text-red-600 px-1.5 py-0.5 rounded">{c}</span>
                                                        ))}
                                                        {run.summary.pricingEnvironment.stableCosts?.map((c: string, i: number) => (
                                                            <span key={i} className="text-xs bg-green-100 text-green-600 px-1.5 py-0.5 rounded">{c}</span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Regulatory & Safety */}
                                            {run.summary.regulatoryAndSafety && (
                                                <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg">
                                                    <span className="text-xs font-semibold text-amber-600 uppercase tracking-wider">Regulatory & Safety</span>
                                                    <p className="text-xs text-gray-700 mt-1">{run.summary.regulatoryAndSafety.narrative}</p>
                                                    {run.summary.regulatoryAndSafety.recallAlerts?.length > 0 && (
                                                        <div className="mt-2">
                                                            <span className="text-xs text-amber-600 font-medium">Recall Alerts: </span>
                                                            <span className="text-xs text-gray-600">{run.summary.regulatoryAndSafety.recallAlerts.join(' | ')}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Recommendations */}
                                            {run.summary.recommendations?.topZipCodes?.length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Top Zip Codes</h4>
                                                    <div className="flex flex-wrap gap-2">
                                                        {run.summary.recommendations.topZipCodes.map((z: any) => (
                                                            <span key={z.zipCode} className="text-xs bg-green-50 text-green-600 px-2 py-1 rounded-full border border-green-200">
                                                                {z.zipCode} ({z.score})
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Zip code list */}
                                            <div className="text-xs text-gray-500">
                                                <span className="font-medium">Zips:</span> {run.zipCodes.join(', ')}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {isExpanded && !run.summary && run.phase === 'completed' && (
                                    <div className="px-4 pb-4 border-t border-gray-100">
                                        <p className="text-sm text-gray-400 mt-4">No summary available.</p>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
