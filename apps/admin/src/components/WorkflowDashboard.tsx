'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { WorkflowDocument, WorkflowPhase, ProgressEvent, BusinessWorkflowState } from '@/lib/workflow/types';
import WorkflowHistory from './WorkflowHistory';
import { FixtureType } from '@/lib/fixtures/types';
import { CAPABILITY_DISPLAY_INFO } from '@/lib/capabilities/display';
import {
    Rocket, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Loader2,
    ChevronRight, ThumbsUp, ThumbsDown, Send, RotateCcw, Trash2, MapPin, BookmarkPlus,
} from 'lucide-react';

const PHASE_STEPS: WorkflowPhase[] = ['discovery', 'analysis', 'evaluation', 'approval', 'outreach', 'completed'];

function phaseLabel(phase: WorkflowPhase): string {
    const labels: Record<WorkflowPhase, string> = {
        discovery: 'Discovery',
        analysis: 'Analysis',
        evaluation: 'Evaluation',
        approval: 'Approval',
        outreach: 'Outreach',
        completed: 'Done',
        failed: 'Failed',
    };
    return labels[phase];
}

function capabilityDot(biz: BusinessWorkflowState, cap: string) {
    const completed = biz.capabilitiesCompleted.includes(cap);
    const failed = biz.capabilitiesFailed.includes(cap);
    const evaluation = biz.evaluations[cap];

    if (evaluation) {
        const passed = evaluation.score >= 80 && !evaluation.isHallucinated;
        return (
            <span title={`${cap}: ${evaluation.score}/100${evaluation.isHallucinated ? ' (hallucinated)' : ''}`}
                className={`inline-block w-2.5 h-2.5 rounded-full ${passed ? 'bg-green-500' : 'bg-amber-400'}`} />
        );
    }
    if (completed) return <span title={`${cap}: analyzed`} className="inline-block w-2.5 h-2.5 rounded-full bg-blue-400" />;
    if (failed) return <span title={`${cap}: failed`} className="inline-block w-2.5 h-2.5 rounded-full bg-red-400" />;
    return <span title={`${cap}: pending`} className="inline-block w-2.5 h-2.5 rounded-full bg-gray-300" />;
}

type LaunchMode = 'single' | 'county';

export default function WorkflowDashboard() {
    const [launchMode, setLaunchMode] = useState<LaunchMode>('single');
    const [zipCode, setZipCode] = useState('');
    const [businessType, setBusinessType] = useState('');
    const [county, setCounty] = useState('');
    const [isLaunching, setIsLaunching] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [activeWorkflow, setActiveWorkflow] = useState<WorkflowDocument | null>(null);
    const [workflows, setWorkflows] = useState<WorkflowDocument[]>([]);
    const [approvals, setApprovals] = useState<Record<string, 'approve' | 'reject'>>({});
    const [isApproving, setIsApproving] = useState(false);
    const [isResuming, setIsResuming] = useState(false);
    const [isStopping, setIsStopping] = useState(false);
    const [confirmStop, setConfirmStop] = useState(false);
    const [stoppingHistoryId, setStoppingHistoryId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [confirmDeleteActive, setConfirmDeleteActive] = useState(false);
    const [savingFixture, setSavingFixture] = useState<Record<string, boolean>>({});
    const [savedFixtures, setSavedFixtures] = useState<Record<string, FixtureType>>({});

    const eventSourceRef = useRef<EventSource | null>(null);

    const fetchWorkflows = useCallback(async () => {
        try {
            const res = await fetch('/api/workflows');
            if (res.ok) {
                const data = await res.json();
                setWorkflows(data);
            }
        } catch { /* silent */ }
    }, []);

    const fetchWorkflow = useCallback(async (id: string) => {
        try {
            const res = await fetch(`/api/workflows/${id}`);
            if (res.ok) {
                const data = await res.json();
                setActiveWorkflow(data);
                return data as WorkflowDocument;
            }
        } catch { /* silent */ }
        return null;
    }, []);

    // Poll for active workflow state when not streaming
    useEffect(() => {
        if (!activeWorkflow) return;
        if (activeWorkflow.phase === 'completed' || activeWorkflow.phase === 'failed' || activeWorkflow.phase === 'approval') return;

        // SSE connection for live updates
        const es = new EventSource(`/api/workflows/${activeWorkflow.id}/stream`);
        eventSourceRef.current = es;

        es.onmessage = (e) => {
            try {
                const event: ProgressEvent = JSON.parse(e.data);
                setActiveWorkflow(prev => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        phase: event.phase,
                        progress: event.progress,
                    };
                });

                if (event.type === 'workflow:completed' || event.type === 'workflow:failed') {
                    es.close();
                    fetchWorkflow(activeWorkflow.id);
                    fetchWorkflows();
                }

                // When reaching approval, fetch full state for business details
                if (event.phase === 'approval') {
                    es.close();
                    fetchWorkflow(activeWorkflow.id);
                }
            } catch { /* ignore parse errors */ }
        };

        es.onerror = () => {
            es.close();
            // Fallback: poll every 5s
            const interval = setInterval(async () => {
                const wf = await fetchWorkflow(activeWorkflow.id);
                if (wf && (wf.phase === 'completed' || wf.phase === 'failed' || wf.phase === 'approval')) {
                    clearInterval(interval);
                }
            }, 5000);

            return () => clearInterval(interval);
        };

        return () => {
            es.close();
            eventSourceRef.current = null;
        };
    }, [activeWorkflow?.id, activeWorkflow?.phase]);

    useEffect(() => {
        fetchWorkflows();
    }, [fetchWorkflows]);

    const handleLaunch = async () => {
        if (launchMode === 'single') {
            if (!/^\d{5}$/.test(zipCode)) {
                setError('Enter a valid 5-digit zip code');
                return;
            }
        } else {
            if (!businessType.trim()) {
                setError('Enter a business type (e.g. Bakery, Restaurant)');
                return;
            }
            if (!county.trim()) {
                setError('Enter a county (e.g. Essex County NJ)');
                return;
            }
        }

        setIsLaunching(true);
        setError(null);

        try {
            let res: Response;

            if (launchMode === 'county') {
                res = await fetch('/api/workflows/county', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        businessType: businessType.trim(),
                        county: county.trim(),
                    }),
                });
            } else {
                const body: Record<string, string> = { zipCode };
                if (businessType.trim()) body.businessType = businessType.trim();
                res = await fetch('/api/workflows', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            }

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to start workflow');
            }

            const { workflowId } = await res.json();

            // Small delay for engine to initialize
            await new Promise(r => setTimeout(r, 500));
            await fetchWorkflow(workflowId);
            fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsLaunching(false);
        }
    };

    const handleApprove = async () => {
        if (!activeWorkflow) return;

        setIsApproving(true);
        try {
            const res = await fetch(`/api/workflows/${activeWorkflow.id}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ approvals }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Approval failed');
            }

            // Re-fetch to get updated state
            await fetchWorkflow(activeWorkflow.id);
            fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsApproving(false);
        }
    };

    const handleResume = async () => {
        if (!activeWorkflow) return;

        setIsResuming(true);
        try {
            const res = await fetch(`/api/workflows/${activeWorkflow.id}/resume`, {
                method: 'POST',
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Resume failed');
            }

            await new Promise(r => setTimeout(r, 500));
            await fetchWorkflow(activeWorkflow.id);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsResuming(false);
        }
    };

    const handleStop = async () => {
        if (!activeWorkflow) return;

        setIsStopping(true);
        try {
            const res = await fetch(`/api/workflows/${activeWorkflow.id}`, { method: 'PATCH' });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to stop workflow');
            }
            // Close SSE connection
            eventSourceRef.current?.close();
            await fetchWorkflow(activeWorkflow.id);
            fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsStopping(false);
            setConfirmStop(false);
        }
    };

    const handleStopFromHistory = async (workflowId: string) => {
        setStoppingHistoryId(workflowId);
        try {
            const res = await fetch(`/api/workflows/${workflowId}`, { method: 'PATCH' });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to stop workflow');
            }
            if (activeWorkflow?.id === workflowId) {
                eventSourceRef.current?.close();
                await fetchWorkflow(workflowId);
            }
            await fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setStoppingHistoryId(null);
        }
    };

    const handleForceDelete = async (workflowId: string) => {
        setDeletingId(workflowId);
        try {
            const res = await fetch(`/api/workflows/${workflowId}?force=true`, { method: 'DELETE' });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to delete workflow');
            }
            if (activeWorkflow?.id === workflowId) {
                eventSourceRef.current?.close();
                setActiveWorkflow(null);
                setApprovals({});
                setConfirmDeleteActive(false);
                setConfirmStop(false);
            }
            await fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setDeletingId(null);
        }
    };

    const handleSelectWorkflow = async (id: string) => {
        setApprovals({});
        setSavedFixtures({});
        await fetchWorkflow(id);
    };

    const handleSaveFixture = async (businessSlug: string, fixtureType: FixtureType) => {
        if (!activeWorkflow) return;
        const key = `${businessSlug}:${fixtureType}`;
        setSavingFixture(prev => ({ ...prev, [key]: true }));
        try {
            const res = await fetch('/api/fixtures', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflowId: activeWorkflow.id,
                    businessSlug,
                    fixtureType,
                }),
            });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to save fixture');
            }
            setSavedFixtures(prev => ({ ...prev, [key]: fixtureType }));
        } catch (e: any) {
            setError(e.message);
        } finally {
            setSavingFixture(prev => ({ ...prev, [key]: false }));
        }
    };

    const handleDelete = async (workflowId: string) => {
        setDeletingId(workflowId);
        try {
            const res = await fetch(`/api/workflows/${workflowId}`, { method: 'DELETE' });
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to delete workflow');
            }
            if (activeWorkflow?.id === workflowId) {
                setActiveWorkflow(null);
                setApprovals({});
                setConfirmDeleteActive(false);
            }
            await fetchWorkflows();
        } catch (e: any) {
            setError(e.message);
        } finally {
            setDeletingId(null);
        }
    };

    const currentPhaseIdx = activeWorkflow ? PHASE_STEPS.indexOf(activeWorkflow.phase === 'failed' ? 'discovery' : activeWorkflow.phase) : -1;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Launch Bar */}
            <div className="bg-white border border-gray-200 p-6 rounded-xl shadow-sm">
                <div className="flex items-center justify-between gap-4 mb-4">
                    <div>
                        <h3 className="text-xl font-bold text-gray-900">Research Pipeline</h3>
                        <p className="text-sm text-gray-500 mt-1">Discover, analyze, evaluate, and outreach businesses</p>
                    </div>
                    <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
                        <button
                            onClick={() => setLaunchMode('single')}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                                launchMode === 'single' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                        >
                            Single Zip
                        </button>
                        <button
                            onClick={() => setLaunchMode('county')}
                            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1 ${
                                launchMode === 'county' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                        >
                            <MapPin className="w-3 h-3" /> County Research
                        </button>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {launchMode === 'single' ? (
                        <>
                            <input
                                type="text"
                                value={zipCode}
                                onChange={e => setZipCode(e.target.value.replace(/\D/g, '').slice(0, 5))}
                                placeholder="07110"
                                className="w-28 px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-center font-mono text-lg focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                                maxLength={5}
                                onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                            />
                            <input
                                type="text"
                                value={businessType}
                                onChange={e => setBusinessType(e.target.value)}
                                placeholder="Restaurants (optional)"
                                className="flex-1 px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                                onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                            />
                        </>
                    ) : (
                        <>
                            <input
                                type="text"
                                value={businessType}
                                onChange={e => setBusinessType(e.target.value)}
                                placeholder="Business type (e.g. Bakery)"
                                className="flex-1 px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                                onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                            />
                            <input
                                type="text"
                                value={county}
                                onChange={e => setCounty(e.target.value)}
                                placeholder="County (e.g. Essex County NJ)"
                                className="flex-1 px-3 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                                onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                            />
                        </>
                    )}
                    <button
                        onClick={handleLaunch}
                        disabled={isLaunching}
                        className="px-5 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-md transition-all"
                    >
                        {isLaunching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
                        {isLaunching ? 'Launching...' : 'Launch Pipeline'}
                    </button>
                </div>
            </div>

            {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-600">
                    <AlertTriangle className="w-5 h-5 shrink-0" />
                    <p className="text-sm">{error}</p>
                    <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
                        <XCircle className="w-4 h-4" />
                    </button>
                </div>
            )}

            {/* Active Workflow */}
            {activeWorkflow && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                    {/* Phase Progress Bar */}
                    <div className="p-4 border-b border-gray-200">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <h4 className="text-sm font-semibold text-gray-700">
                                    Pipeline: {activeWorkflow.county || activeWorkflow.zipCode}
                                </h4>
                                {activeWorkflow.businessType && (
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200">
                                        {activeWorkflow.businessType}
                                    </span>
                                )}
                                {activeWorkflow.zipCodes && activeWorkflow.zipCodes.length > 0 && (
                                    <span className="text-xs text-gray-400">
                                        {activeWorkflow.zipCodes.length} zips
                                    </span>
                                )}
                            </div>
                            <span className="text-xs text-gray-400 font-mono">{activeWorkflow.id.slice(0, 8)}</span>
                        </div>
                        <div className="flex items-center gap-1">
                            {PHASE_STEPS.map((step, idx) => (
                                <div key={step} className="flex items-center flex-1">
                                    <div className={`flex-1 h-1.5 rounded-full transition-all ${
                                        activeWorkflow.phase === 'failed'
                                            ? 'bg-red-200'
                                            : idx < currentPhaseIdx
                                                ? 'bg-green-500'
                                                : idx === currentPhaseIdx
                                                    ? 'bg-indigo-500 animate-pulse'
                                                    : 'bg-gray-200'
                                    }`} />
                                    {idx < PHASE_STEPS.length - 1 && <ChevronRight className="w-3 h-3 text-gray-300 shrink-0" />}
                                </div>
                            ))}
                        </div>
                        <div className="flex justify-between mt-1.5">
                            {PHASE_STEPS.map((step, idx) => (
                                <span key={step} className={`text-[10px] ${
                                    idx <= currentPhaseIdx ? 'text-gray-700' : 'text-gray-400'
                                }`}>
                                    {phaseLabel(step)}
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Zip Scanning Progress */}
                    {activeWorkflow.progress.zipCodesTotal && activeWorkflow.progress.zipCodesTotal > 0 && (
                        <div className="px-4 pt-3 pb-1 border-b border-gray-200">
                            <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                                <span>Zip codes scanned</span>
                                <span className="font-mono">{activeWorkflow.progress.zipCodesScanned ?? 0}/{activeWorkflow.progress.zipCodesTotal}</span>
                            </div>
                            <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-indigo-400 rounded-full transition-all"
                                    style={{ width: `${((activeWorkflow.progress.zipCodesScanned ?? 0) / activeWorkflow.progress.zipCodesTotal) * 100}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Progress Stats */}
                    <div className="p-4 border-b border-gray-200 grid grid-cols-4 gap-4">
                        <div className="text-center">
                            <div className="text-2xl font-bold text-gray-800">{activeWorkflow.progress.totalBusinesses}</div>
                            <div className="text-xs text-gray-500">Discovered</div>
                        </div>
                        <div className="text-center">
                            <div className="text-2xl font-bold text-blue-500">{activeWorkflow.progress.analysisComplete}</div>
                            <div className="text-xs text-gray-500">Analyzed</div>
                        </div>
                        <div className="text-center">
                            <div className="text-2xl font-bold text-green-500">{activeWorkflow.progress.qualityPassed}</div>
                            <div className="text-xs text-gray-500">Passed QA</div>
                        </div>
                        <div className="text-center">
                            <div className="text-2xl font-bold text-purple-500">{activeWorkflow.progress.outreachComplete}</div>
                            <div className="text-xs text-gray-500">Outreached</div>
                        </div>
                    </div>

                    {/* Business Cards */}
                    {activeWorkflow.businesses && activeWorkflow.businesses.length > 0 && (
                        <div className="p-4 space-y-2">
                            {activeWorkflow.businesses.map(biz => (
                                <div key={biz.slug} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium text-sm text-gray-800">{biz.name}</span>
                                            <span className="text-xs text-gray-400">{biz.slug}</span>
                                            {biz.sourceZipCode && activeWorkflow.zipCodes && activeWorkflow.zipCodes.length > 0 && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-mono">{biz.sourceZipCode}</span>
                                            )}
                                        </div>
                                        <div className="text-xs text-gray-500 mt-0.5">{biz.address}</div>
                                    </div>

                                    {/* Capability dots */}
                                    <div className="flex items-center gap-1.5 mx-4">
                                        {CAPABILITY_DISPLAY_INFO.map(cap => (
                                            <span key={cap.name}>{capabilityDot(biz, cap.name)}</span>
                                        ))}
                                    </div>

                                    {/* Evaluation scores */}
                                    {biz.evaluations && Object.keys(biz.evaluations).length > 0 && (
                                        <div className="flex items-center gap-2 mx-4">
                                            {Object.entries(biz.evaluations).map(([cap, ev]) => ev && (
                                                <span key={cap} className={`text-xs px-1.5 py-0.5 rounded ${
                                                    ev.score >= 80 && !ev.isHallucinated
                                                        ? 'bg-green-50 text-green-600 border border-green-200'
                                                        : 'bg-amber-50 text-amber-600 border border-amber-200'
                                                }`}>
                                                    {cap.slice(0, 3)}: {ev.score}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Phase badge / Approval toggle */}
                                    {activeWorkflow.phase === 'approval' && biz.qualityPassed && biz.phase === 'evaluation_done' ? (
                                        <div className="flex items-center gap-1">
                                            <button
                                                onClick={() => setApprovals(prev => ({ ...prev, [biz.slug]: 'approve' }))}
                                                className={`p-1.5 rounded transition-colors ${
                                                    approvals[biz.slug] === 'approve'
                                                        ? 'bg-green-600 text-white'
                                                        : 'bg-gray-200 text-gray-500 hover:text-green-600'
                                                }`}
                                                title="Approve for outreach"
                                            >
                                                <ThumbsUp className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                onClick={() => setApprovals(prev => ({ ...prev, [biz.slug]: 'reject' }))}
                                                className={`p-1.5 rounded transition-colors ${
                                                    approvals[biz.slug] === 'reject'
                                                        ? 'bg-red-600 text-white'
                                                        : 'bg-gray-200 text-gray-500 hover:text-red-600'
                                                }`}
                                                title="Reject"
                                            >
                                                <ThumbsDown className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    ) : (
                                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                                            biz.phase === 'outreach_done' ? 'bg-green-50 text-green-600' :
                                            biz.phase === 'outreach_failed' ? 'bg-red-50 text-red-600' :
                                            biz.phase === 'approved' ? 'bg-green-50 text-green-600' :
                                            biz.phase === 'rejected' ? 'bg-red-50 text-red-600' :
                                            'bg-gray-100 text-gray-500'
                                        }`}>
                                            {biz.phase.replace(/_/g, ' ')}
                                        </span>
                                    )}

                                    {/* Save as fixture buttons */}
                                    {['approval', 'completed', 'failed'].includes(activeWorkflow.phase) &&
                                     biz.evaluations && Object.keys(biz.evaluations).length > 0 && (
                                        <div className="flex items-center gap-1 ml-2">
                                            {savedFixtures[`${biz.slug}:grounding`] ? (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-200">Saved</span>
                                            ) : (
                                                <button
                                                    onClick={() => handleSaveFixture(biz.slug, 'grounding')}
                                                    disabled={savingFixture[`${biz.slug}:grounding`]}
                                                    className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-200 hover:bg-green-100 disabled:opacity-50 transition-colors"
                                                    title="Save as grounding data"
                                                >
                                                    {savingFixture[`${biz.slug}:grounding`] ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <BookmarkPlus className="w-2.5 h-2.5" />}
                                                    Grounding
                                                </button>
                                            )}
                                            {savedFixtures[`${biz.slug}:failure_case`] ? (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">Saved</span>
                                            ) : (
                                                <button
                                                    onClick={() => handleSaveFixture(biz.slug, 'failure_case')}
                                                    disabled={savingFixture[`${biz.slug}:failure_case`]}
                                                    className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100 disabled:opacity-50 transition-colors"
                                                    title="Save as failure case"
                                                >
                                                    {savingFixture[`${biz.slug}:failure_case`] ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <BookmarkPlus className="w-2.5 h-2.5" />}
                                                    Failure Case
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Action Buttons */}
                    <div className="p-4 border-t border-gray-200 flex items-center gap-3">
                        {activeWorkflow.phase === 'approval' && (
                            <button
                                onClick={handleApprove}
                                disabled={isApproving || Object.keys(approvals).length === 0}
                                className="px-4 py-2 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all shadow-sm"
                            >
                                {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                                Submit Approvals
                            </button>
                        )}

                        {activeWorkflow.phase === 'failed' && (
                            <button
                                onClick={handleResume}
                                disabled={isResuming}
                                className="px-4 py-2 bg-amber-500 text-white font-semibold rounded-lg hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all shadow-sm"
                            >
                                {isResuming ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                                Resume Workflow
                            </button>
                        )}

                        {activeWorkflow.phase === 'failed' && activeWorkflow.lastError && (
                            <span className="text-xs text-red-500 flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" /> {activeWorkflow.lastError}
                            </span>
                        )}

                        {(activeWorkflow.phase !== 'approval' && activeWorkflow.phase !== 'failed' && activeWorkflow.phase !== 'completed') && (
                            <>
                                <span className="text-sm text-gray-500 flex items-center gap-2">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Processing {phaseLabel(activeWorkflow.phase)}...
                                </span>
                                {!confirmStop ? (
                                    <button
                                        onClick={() => setConfirmStop(true)}
                                        disabled={isStopping}
                                        className="px-3 py-1.5 text-xs font-medium bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition-colors flex items-center gap-1.5"
                                    >
                                        <XCircle className="w-3.5 h-3.5" /> Stop
                                    </button>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-red-500">Stop this run?</span>
                                        <button
                                            onClick={handleStop}
                                            disabled={isStopping}
                                            className="px-2.5 py-1 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-500 transition-colors flex items-center gap-1"
                                        >
                                            {isStopping ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                                            Confirm Stop
                                        </button>
                                        <button
                                            onClick={() => setConfirmStop(false)}
                                            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                )}
                            </>
                        )}

                        {activeWorkflow.phase === 'completed' && (
                            <span className="text-sm text-green-600 flex items-center gap-2">
                                <CheckCircle2 className="w-4 h-4" />
                                Pipeline complete
                            </span>
                        )}

                        <div className="ml-auto flex items-center gap-3">
                            {!confirmDeleteActive && !deletingId && (
                                <button
                                    onClick={() => setConfirmDeleteActive(true)}
                                    className="text-gray-300 hover:text-red-500 transition-colors p-1"
                                    title="Delete run"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            )}
                            {confirmDeleteActive && !deletingId && (
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-red-500">Delete?</span>
                                    <button
                                        onClick={() => {
                                            const isActive = !['completed', 'failed', 'approval'].includes(activeWorkflow.phase);
                                            isActive ? handleForceDelete(activeWorkflow.id) : handleDelete(activeWorkflow.id);
                                        }}
                                        className="px-2.5 py-1 text-xs font-semibold bg-red-600 text-white rounded hover:bg-red-500 transition-colors"
                                    >
                                        Confirm
                                    </button>
                                    <button
                                        onClick={() => setConfirmDeleteActive(false)}
                                        className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            )}
                            {deletingId === activeWorkflow.id && (
                                <span className="flex items-center gap-1.5 text-xs text-red-500">
                                    <Loader2 className="w-3 h-3 animate-spin" /> Deleting...
                                </span>
                            )}
                            <button
                                onClick={() => { setActiveWorkflow(null); setApprovals({}); setConfirmDeleteActive(false); setConfirmStop(false); }}
                                className="text-xs text-gray-400 hover:text-gray-700 transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* History */}
            <div>
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-gray-700">Workflow History</h3>
                    <button
                        onClick={fetchWorkflows}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                        title="Refresh"
                    >
                        <RefreshCw className="w-4 h-4" />
                    </button>
                </div>
                <WorkflowHistory
                    workflows={workflows}
                    onSelect={handleSelectWorkflow}
                    onDelete={handleDelete}
                    onStop={handleStopFromHistory}
                    onForceDelete={handleForceDelete}
                    deletingId={deletingId}
                    stoppingId={stoppingHistoryId}
                />
            </div>
        </div>
    );
}
