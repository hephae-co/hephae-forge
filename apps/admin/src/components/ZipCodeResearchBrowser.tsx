'use client';

import { useState, useEffect, useCallback } from 'react';
import {
    Globe, ChevronDown, ChevronRight, Loader2, Trash2, RefreshCw,
    MapPin, Users, Home, Building2, TrendingUp, ShoppingCart, Train, Flame,
    BookOpen, Layers,
} from 'lucide-react';

interface RunSummary {
    id: string;
    zipCode: string;
    sectionCount: number;
    summarySnippet: string;
    createdAt: string;
}

interface ReportSection {
    title: string;
    content: string;
    key_facts: string[];
}

interface FullRun {
    zipCode: string;
    report: {
        summary: string;
        zip_code: string;
        sections: Record<string, ReportSection>;
        sources?: { short_id: string; title: string; url: string; domain: string }[];
        source_count?: number;
    };
    createdAt: string;
}

const SECTION_ICONS: Record<string, React.ReactNode> = {
    geography: <MapPin className="w-4 h-4" />,
    demographics: <Users className="w-4 h-4" />,
    census_housing: <Home className="w-4 h-4" />,
    business_landscape: <Building2 className="w-4 h-4" />,
    economic_indicators: <TrendingUp className="w-4 h-4" />,
    consumer_market: <ShoppingCart className="w-4 h-4" />,
    infrastructure: <Train className="w-4 h-4" />,
    trending: <Flame className="w-4 h-4" />,
};

interface ZipCodeResearchBrowserProps {
    refreshKey?: number;
}

export default function ZipCodeResearchBrowser({ refreshKey }: ZipCodeResearchBrowserProps) {
    const [runs, setRuns] = useState<RunSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [expandedRun, setExpandedRun] = useState<FullRun | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [combining, setCombining] = useState(false);
    const [combineError, setCombineError] = useState<string | null>(null);

    const fetchRuns = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/zipcode-research?limit=10');
            if (res.ok) {
                setRuns(await res.json());
            }
        } catch { /* silent */ }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchRuns(); }, [fetchRuns, refreshKey]);

    const loadRunDetail = async (runId: string) => {
        if (expandedId === runId) {
            setExpandedId(null);
            setExpandedRun(null);
            setExpandedSections(new Set());
            return;
        }
        setExpandedId(runId);
        setLoadingDetail(true);
        setExpandedSections(new Set());
        try {
            const res = await fetch(`/api/zipcode-research/runs/${runId}`);
            if (res.ok) {
                setExpandedRun(await res.json());
            }
        } catch { /* silent */ }
        finally { setLoadingDetail(false); }
    };

    const handleDelete = async (runId: string) => {
        setDeletingId(runId);
        try {
            const res = await fetch(`/api/zipcode-research/runs/${runId}`, { method: 'DELETE' });
            if (res.ok) {
                setRuns(prev => prev.filter(r => r.id !== runId));
                if (expandedId === runId) { setExpandedId(null); setExpandedRun(null); }
                setSelectedIds(prev => { const next = new Set(prev); next.delete(runId); return next; });
            }
        } catch { /* silent */ }
        finally { setDeletingId(null); setConfirmingId(null); }
    };

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const handleCombine = async () => {
        setCombining(true);
        setCombineError(null);
        try {
            const res = await fetch('/api/combined-context', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ runIds: Array.from(selectedIds) }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Failed to combine');
            }
            setSelectedIds(new Set());
        } catch (e: any) {
            setCombineError(e.message);
        } finally {
            setCombining(false);
        }
    };

    const toggleSection = (key: string) => {
        setExpandedSections(prev => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key); else next.add(key);
            return next;
        });
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                    <Globe className="w-5 h-5 text-indigo-500" />
                    Zip Code Research Runs
                </h3>
                <button onClick={fetchRuns} className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded border border-gray-200 hover:border-gray-300 transition-colors flex items-center gap-1">
                    <RefreshCw className="w-3 h-3" /> Refresh
                </button>
            </div>

            {/* Multi-select toolbar */}
            {selectedIds.size >= 2 && (
                <div className="flex items-center gap-3 p-3 bg-indigo-50 border border-indigo-200 rounded-lg">
                    <span className="text-sm font-medium text-indigo-700">{selectedIds.size} selected</span>
                    <button
                        onClick={handleCombine}
                        disabled={combining}
                        className="px-4 py-1.5 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-50 flex items-center gap-2 transition-all"
                    >
                        {combining ? <Loader2 className="w-3 h-3 animate-spin" /> : <Layers className="w-3 h-3" />}
                        {combining ? 'Combining...' : 'Combine Context'}
                    </button>
                    <button onClick={() => setSelectedIds(new Set())} className="text-xs text-indigo-500 hover:text-indigo-700">Clear</button>
                    {combineError && <span className="text-xs text-red-500">{combineError}</span>}
                </div>
            )}

            {loading && (
                <div className="text-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                </div>
            )}

            {!loading && runs.length === 0 && (
                <div className="text-center py-12 border border-dashed border-gray-300 rounded-xl text-gray-400">
                    <Globe className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>No zip code research runs yet. Use the controls above to run research.</p>
                </div>
            )}

            {!loading && runs.length > 0 && (
                <div className="space-y-2">
                    {runs.map(run => {
                        const isExpanded = expandedId === run.id;
                        const isConfirming = confirmingId === run.id;
                        const isDeleting = deletingId === run.id;
                        const isSelected = selectedIds.has(run.id);

                        return (
                            <div
                                key={run.id}
                                className={`relative bg-white border rounded-lg transition-all ${
                                    isConfirming ? 'border-red-200 bg-red-50'
                                    : isSelected ? 'border-indigo-300 bg-indigo-50/30'
                                    : 'border-gray-200 hover:shadow-md hover:border-gray-300'
                                }`}
                            >
                                <div className="flex items-center gap-3 p-4">
                                    {/* Checkbox */}
                                    <input
                                        type="checkbox"
                                        checked={isSelected}
                                        onChange={() => toggleSelect(run.id)}
                                        className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                    />

                                    {/* Main row clickable area */}
                                    <button
                                        onClick={() => loadRunDetail(run.id)}
                                        className="flex-1 text-left"
                                        disabled={isConfirming || isDeleting}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                {isExpanded
                                                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                                                    : <ChevronRight className="w-4 h-4 text-gray-400" />
                                                }
                                                <span className="text-sm font-mono font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                                                    {run.zipCode}
                                                </span>
                                                <span className="text-xs text-gray-500 truncate max-w-[300px]">
                                                    {run.summarySnippet}...
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                                    {run.sectionCount} sections
                                                </span>
                                                <span className="text-xs text-gray-400">
                                                    {new Date(run.createdAt).toLocaleDateString()} {new Date(run.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                </span>
                                            </div>
                                        </div>
                                    </button>

                                    {/* Delete button */}
                                    {!isConfirming && !isDeleting && (
                                        <button
                                            onClick={() => setConfirmingId(run.id)}
                                            className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                            title="Delete run"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    )}
                                </div>

                                {/* Delete confirmation */}
                                {isConfirming && !isDeleting && (
                                    <div className="mx-4 mb-4 flex items-center gap-3 pt-3 border-t border-red-200">
                                        <span className="text-xs text-red-500">Delete this research run?</span>
                                        <button
                                            onClick={() => handleDelete(run.id)}
                                            className="px-3 py-1 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-500 transition-colors"
                                        >
                                            Confirm
                                        </button>
                                        <button
                                            onClick={() => setConfirmingId(null)}
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
                                {isExpanded && (
                                    <div className="px-4 pb-4 border-t border-gray-100">
                                        {loadingDetail && (
                                            <div className="flex items-center gap-2 py-4 text-gray-400">
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                                <span className="text-sm">Loading full report...</span>
                                            </div>
                                        )}

                                        {!loadingDetail && expandedRun?.report && (
                                            <div className="mt-4 space-y-3">
                                                {/* Summary */}
                                                {expandedRun.report.summary && (
                                                    <div className="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-lg">
                                                        <p className="text-sm text-gray-700 leading-relaxed">{expandedRun.report.summary}</p>
                                                    </div>
                                                )}

                                                {/* Section expand/collapse controls */}
                                                <div className="flex justify-end">
                                                    <button
                                                        onClick={() => {
                                                            const keys = Object.keys(expandedRun.report.sections);
                                                            setExpandedSections(prev =>
                                                                prev.size === keys.length ? new Set() : new Set(keys)
                                                            );
                                                        }}
                                                        className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-200 hover:border-gray-300 transition-colors"
                                                    >
                                                        {expandedSections.size === Object.keys(expandedRun.report.sections).length ? 'Collapse All' : 'Expand All'}
                                                    </button>
                                                </div>

                                                {/* Sections */}
                                                {Object.entries(expandedRun.report.sections).map(([key, section]) => {
                                                    const isSectionExpanded = expandedSections.has(key);
                                                    const icon = SECTION_ICONS[key] || <BookOpen className="w-4 h-4" />;

                                                    return (
                                                        <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                                                            <button
                                                                onClick={() => toggleSection(key)}
                                                                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                                                            >
                                                                <span className="text-indigo-500">{icon}</span>
                                                                <span className="flex-1 font-semibold text-sm text-gray-800">{section.title}</span>
                                                                {section.key_facts?.length > 0 && (
                                                                    <span className="text-xs text-gray-400 mr-2">{section.key_facts.length} facts</span>
                                                                )}
                                                                {isSectionExpanded
                                                                    ? <ChevronDown className="w-4 h-4 text-gray-400" />
                                                                    : <ChevronRight className="w-4 h-4 text-gray-400" />
                                                                }
                                                            </button>
                                                            {isSectionExpanded && (
                                                                <div className="px-4 pb-4 border-t border-gray-100">
                                                                    <p className="text-sm text-gray-600 leading-relaxed mt-3 whitespace-pre-wrap">{section.content}</p>
                                                                    {section.key_facts?.length > 0 && (
                                                                        <div className="mt-3 flex flex-wrap gap-2">
                                                                            {section.key_facts.map((fact, i) => (
                                                                                <span key={i} className="text-xs bg-gray-50 text-gray-600 px-2.5 py-1 rounded-full border border-gray-200">
                                                                                    {fact}
                                                                                </span>
                                                                            ))}
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })}

                                                {/* Sources */}
                                                {expandedRun.report.sources && expandedRun.report.sources.length > 0 && (
                                                    <details className="mt-2">
                                                        <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 transition-colors">
                                                            View {expandedRun.report.sources.length} sources
                                                        </summary>
                                                        <div className="mt-2 grid gap-1">
                                                            {expandedRun.report.sources.map((src) => (
                                                                <a
                                                                    key={src.short_id}
                                                                    href={src.url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="text-xs text-indigo-500 hover:text-indigo-600 hover:underline truncate block"
                                                                >
                                                                    [{src.short_id}] {src.title || src.domain}
                                                                </a>
                                                            ))}
                                                        </div>
                                                    </details>
                                                )}
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
