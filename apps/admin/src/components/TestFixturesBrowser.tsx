'use client';

import { useEffect, useState, useCallback } from 'react';
import { TestFixture, FixtureType } from '@/lib/fixtures/types';
import {
    Database, ChevronDown, ChevronRight, Trash2, Loader2,
    CheckCircle2, AlertTriangle, BookmarkCheck,
} from 'lucide-react';

type FilterMode = 'all' | 'grounding' | 'failure_case';

function typeBadge(fixtureType: FixtureType) {
    if (fixtureType === 'grounding') {
        return (
            <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-200">
                <CheckCircle2 className="w-3 h-3" /> Grounding
            </span>
        );
    }
    return (
        <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200">
            <AlertTriangle className="w-3 h-3" /> Failure Case
        </span>
    );
}

export default function TestFixturesBrowser() {
    const [fixtures, setFixtures] = useState<TestFixture[]>([]);
    const [filter, setFilter] = useState<FilterMode>('all');
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchFixtures = useCallback(async () => {
        setLoading(true);
        try {
            const typeParam = filter !== 'all' ? `?type=${filter}` : '';
            const res = await fetch(`/api/fixtures${typeParam}`);
            if (res.ok) {
                const data = await res.json();
                setFixtures(data);
            }
        } catch { /* silent */ }
        finally { setLoading(false); }
    }, [filter]);

    useEffect(() => {
        fetchFixtures();
    }, [fetchFixtures]);

    const handleDelete = async (fixtureId: string) => {
        setDeletingId(fixtureId);
        try {
            const res = await fetch(`/api/fixtures/${fixtureId}`, { method: 'DELETE' });
            if (res.ok) {
                setFixtures(prev => prev.filter(f => f.id !== fixtureId));
                if (expandedId === fixtureId) setExpandedId(null);
            }
        } catch { /* silent */ }
        finally {
            setDeletingId(null);
            setConfirmingId(null);
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Header + Filter */}
            <div className="bg-white border border-gray-200 p-6 rounded-xl shadow-sm">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-xl font-bold text-gray-900">Test Fixtures</h3>
                        <p className="text-sm text-gray-500 mt-1">Saved grounding data and failure cases from workflow runs</p>
                    </div>
                    <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
                        {(['all', 'grounding', 'failure_case'] as FilterMode[]).map(mode => (
                            <button
                                key={mode}
                                onClick={() => setFilter(mode)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                                    filter === mode ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                                }`}
                            >
                                {mode === 'all' ? 'All' : mode === 'grounding' ? 'Grounding' : 'Failure Cases'}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Loading */}
            {loading && (
                <div className="text-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-gray-400" />
                </div>
            )}

            {/* Empty state */}
            {!loading && fixtures.length === 0 && (
                <div className="text-center py-12 border border-dashed border-gray-300 rounded-xl text-gray-400">
                    <Database className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>No test fixtures saved yet.</p>
                    <p className="text-sm mt-1">Save businesses from workflow runs using the Grounding / Failure Case buttons.</p>
                </div>
            )}

            {/* Fixture list */}
            {!loading && fixtures.length > 0 && (
                <div className="space-y-2">
                    {fixtures.map(fixture => {
                        const isExpanded = expandedId === fixture.id;
                        const isConfirming = confirmingId === fixture.id;
                        const isDeleting = deletingId === fixture.id;
                        const evaluations = fixture.businessState?.evaluations as Record<string, { score: number; isHallucinated: boolean; issues: string[] }> | undefined;
                        const evalEntries = evaluations
                            ? Object.entries(evaluations).filter(([, ev]) => ev)
                            : [];

                        return (
                            <div
                                key={fixture.id}
                                className={`relative bg-white border rounded-lg transition-all ${
                                    isConfirming ? 'border-red-200 bg-red-50' : 'border-gray-200 hover:shadow-md hover:border-gray-300'
                                }`}
                            >
                                {/* Main row */}
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : fixture.id)}
                                    className="w-full text-left p-4"
                                    disabled={isConfirming || isDeleting}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            {isExpanded
                                                ? <ChevronDown className="w-4 h-4 text-gray-400" />
                                                : <ChevronRight className="w-4 h-4 text-gray-400" />
                                            }
                                            <span className="font-medium text-sm text-gray-800">
                                                {fixture.identity?.name || (fixture.businessState?.name as string | undefined) || 'Unknown'}
                                            </span>
                                            {typeBadge(fixture.fixtureType)}
                                            {fixture.sourceZipCode && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-mono">
                                                    {fixture.sourceZipCode}
                                                </span>
                                            )}
                                            {fixture.businessType && (
                                                <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">
                                                    {fixture.businessType}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-3">
                                            {/* Evaluation scores */}
                                            {evalEntries.map(([cap, ev]) => ev && (
                                                <span key={cap} className={`text-xs px-1.5 py-0.5 rounded ${
                                                    ev.score >= 80 && !ev.isHallucinated
                                                        ? 'bg-green-50 text-green-600 border border-green-200'
                                                        : 'bg-amber-50 text-amber-600 border border-amber-200'
                                                }`}>
                                                    {cap.slice(0, 3)}: {ev.score}
                                                </span>
                                            ))}
                                            <span className="text-xs text-gray-400">
                                                {new Date(fixture.savedAt).toLocaleDateString()}
                                            </span>
                                        </div>
                                    </div>
                                    {fixture.notes && (
                                        <p className="text-xs text-gray-500 mt-1 ml-7">{fixture.notes}</p>
                                    )}
                                </button>

                                {/* Delete controls */}
                                {!isConfirming && !isDeleting && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setConfirmingId(fixture.id); }}
                                        className="absolute top-4 right-4 p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                        title="Delete fixture"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}

                                {isConfirming && !isDeleting && (
                                    <div className="mx-4 mb-4 flex items-center gap-3 pt-3 border-t border-red-200">
                                        <span className="text-xs text-red-500">Delete this fixture?</span>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(fixture.id); }}
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
                                {isExpanded && (
                                    <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
                                        {/* Identity */}
                                        <div className="mt-4">
                                            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Identity</h4>
                                            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 space-y-1">
                                                <div><span className="font-medium">Name:</span> {fixture.identity?.name}</div>
                                                <div><span className="font-medium">Address:</span> {fixture.identity?.address}</div>
                                                {fixture.identity?.email && <div><span className="font-medium">Email:</span> {fixture.identity.email}</div>}
                                                <div><span className="font-medium">Doc ID:</span> <span className="font-mono text-gray-500">{fixture.identity?.docId}</span></div>
                                                {fixture.identity?.socialLinks && Object.keys(fixture.identity.socialLinks).length > 0 && (
                                                    <div><span className="font-medium">Social:</span> {Object.entries(fixture.identity.socialLinks).map(([k, v]) => `${k}: ${v}`).join(', ')}</div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Evaluation Results */}
                                        {evalEntries.length > 0 && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Evaluations</h4>
                                                <div className="grid gap-2 grid-cols-1 md:grid-cols-3">
                                                    {evalEntries.map(([cap, ev]) => ev && (
                                                        <div key={cap} className={`rounded-lg p-3 text-xs border ${
                                                            ev.score >= 80 && !ev.isHallucinated
                                                                ? 'bg-green-50 border-green-200'
                                                                : 'bg-amber-50 border-amber-200'
                                                        }`}>
                                                            <div className="font-semibold capitalize mb-1">{cap}</div>
                                                            <div>Score: {ev.score}/100</div>
                                                            <div>Hallucinated: {ev.isHallucinated ? 'Yes' : 'No'}</div>
                                                            {ev.issues.length > 0 && (
                                                                <div className="mt-1">
                                                                    <span className="font-medium">Issues:</span>
                                                                    <ul className="list-disc list-inside mt-0.5">
                                                                        {ev.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                                                                    </ul>
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Latest Outputs preview */}
                                        {fixture.latestOutputs && Object.keys(fixture.latestOutputs).some(k => (fixture.latestOutputs as any)[k]) && (
                                            <div>
                                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Latest Outputs</h4>
                                                <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono text-gray-600 max-h-48 overflow-auto">
                                                    <pre className="whitespace-pre-wrap">
                                                        {JSON.stringify(fixture.latestOutputs, null, 2)}
                                                    </pre>
                                                </div>
                                            </div>
                                        )}

                                        {/* Business State */}
                                        {fixture.businessState && (() => {
                                            const bs = fixture.businessState as Record<string, any>;
                                            return (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Business State Snapshot</h4>
                                                    <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 space-y-1">
                                                        <div><span className="font-medium">Phase:</span> {(bs.phase as string | undefined)?.replace(/_/g, ' ')}</div>
                                                        <div><span className="font-medium">Quality Passed:</span> {bs.qualityPassed ? 'Yes' : 'No'}</div>
                                                        <div><span className="font-medium">Capabilities:</span> {(bs.capabilitiesCompleted as string[] | undefined)?.join(', ') || 'none'}</div>
                                                        {((bs.capabilitiesFailed as string[] | undefined)?.length ?? 0) > 0 && (
                                                            <div><span className="font-medium text-red-600">Failed:</span> {(bs.capabilitiesFailed as string[]).join(', ')}</div>
                                                        )}
                                                        {bs.lastError && (
                                                            <div><span className="font-medium text-red-600">Error:</span> {bs.lastError as string}</div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })()}

                                        <div className="text-[10px] text-gray-400 flex gap-4">
                                            <span>Fixture ID: {fixture.id}</span>
                                            <span>Source Workflow: {fixture.sourceWorkflowId.slice(0, 8)}</span>
                                        </div>
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
