'use client';

import { useState, useEffect, useCallback } from 'react';
import { Layers, ChevronDown, ChevronRight, Loader2, Trash2, RefreshCw } from 'lucide-react';

interface CombinedContextItem {
    id: string;
    sourceRunIds: string[];
    sourceZipCodes: string[];
    context: {
        summary: string;
        keySignals: string[];
        demographicHighlights: string[];
        marketGaps: string[];
        trendingTerms: string[];
    };
    createdAt: string;
}

export default function CombinedContextList() {
    const [contexts, setContexts] = useState<CombinedContextItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);

    const fetchContexts = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/combined-context?limit=10');
            if (res.ok) setContexts(await res.json());
        } catch { /* silent */ }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchContexts(); }, [fetchContexts]);

    const handleDelete = async (id: string) => {
        setDeletingId(id);
        try {
            const res = await fetch(`/api/combined-context/${id}`, { method: 'DELETE' });
            if (res.ok) {
                setContexts(prev => prev.filter(c => c.id !== id));
                if (expandedId === id) setExpandedId(null);
            }
        } catch { /* silent */ }
        finally { setDeletingId(null); setConfirmingId(null); }
    };

    if (!loading && contexts.length === 0) return null;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    <Layers className="w-5 h-5 text-indigo-500" />
                    Combined Contexts
                </h3>
                <button onClick={fetchContexts} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded border border-gray-200 hover:border-gray-300 transition-colors flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> Refresh
                </button>
            </div>

            {loading && (
                <div className="text-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-400" />
                </div>
            )}

            {!loading && contexts.length > 0 && (
                <div className="space-y-2">
                    {contexts.map(ctx => {
                        const isExpanded = expandedId === ctx.id;
                        const isConfirming = confirmingId === ctx.id;
                        const isDeleting = deletingId === ctx.id;

                        return (
                            <div
                                key={ctx.id}
                                className={`relative bg-white border rounded-lg transition-all ${
                                    isConfirming ? 'border-red-200 bg-red-50' : 'border-gray-200 hover:shadow-md hover:border-gray-300'
                                }`}
                            >
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : ctx.id)}
                                    className="w-full text-left p-4"
                                    disabled={isConfirming || isDeleting}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            {isExpanded
                                                ? <ChevronDown className="w-4 h-4 text-gray-400" />
                                                : <ChevronRight className="w-4 h-4 text-gray-400" />
                                            }
                                            <div className="flex items-center gap-2 flex-wrap">
                                                {ctx.sourceZipCodes.map(zip => (
                                                    <span key={zip} className="text-xs font-mono bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">
                                                        {zip}
                                                    </span>
                                                ))}
                                            </div>
                                            <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                                {ctx.sourceRunIds.length} runs
                                            </span>
                                        </div>
                                        <span className="text-xs text-gray-400">
                                            {new Date(ctx.createdAt).toLocaleDateString()} {new Date(ctx.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    </div>
                                </button>

                                {/* Delete button */}
                                {!isConfirming && !isDeleting && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setConfirmingId(ctx.id); }}
                                        className="absolute top-4 right-4 p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                        title="Delete context"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}

                                {isConfirming && !isDeleting && (
                                    <div className="mx-4 mb-4 flex items-center gap-3 pt-3 border-t border-red-200">
                                        <span className="text-xs text-red-500">Delete this combined context?</span>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(ctx.id); }}
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

                                {/* Expanded detail */}
                                {isExpanded && ctx.context && (
                                    <div className="px-4 pb-4 border-t border-gray-100 space-y-3 mt-3">
                                        {/* Summary */}
                                        <div className="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-lg">
                                            <p className="text-sm text-gray-700 leading-relaxed">{ctx.context.summary}</p>
                                        </div>

                                        {/* Key Signals */}
                                        {ctx.context.keySignals?.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Key Signals</h4>
                                                <div className="flex flex-wrap gap-2">
                                                    {ctx.context.keySignals.map((s, i) => (
                                                        <span key={i} className="text-xs bg-green-50 text-green-600 px-2 py-1 rounded-full border border-green-200">
                                                            {s}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Demographic Highlights */}
                                        {ctx.context.demographicHighlights?.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Demographics</h4>
                                                <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
                                                    {ctx.context.demographicHighlights.map((d, i) => (
                                                        <li key={i}>{d}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}

                                        {/* Market Gaps */}
                                        {ctx.context.marketGaps?.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Market Gaps</h4>
                                                <div className="flex flex-wrap gap-2">
                                                    {ctx.context.marketGaps.map((g, i) => (
                                                        <span key={i} className="text-xs bg-amber-50 text-amber-600 px-2 py-1 rounded-full border border-amber-200">
                                                            {g}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Trending Terms */}
                                        {ctx.context.trendingTerms?.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Trending</h4>
                                                <div className="flex flex-wrap gap-2">
                                                    {ctx.context.trendingTerms.map((t, i) => (
                                                        <span key={i} className="text-xs bg-purple-50 text-purple-600 px-2 py-1 rounded-full border border-purple-200">
                                                            {t}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
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
