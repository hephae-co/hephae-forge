'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { WorkflowDocument, WorkflowPhase, ProgressEvent, BusinessWorkflowState } from '@/lib/workflow/types';
import WorkflowHistory from './WorkflowHistory';
import { FixtureType } from '@/lib/fixtures/types';
import { CAPABILITY_DISPLAY_INFO } from '@/lib/capabilities/display';
import {
    Rocket, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Loader2,
    ChevronRight, ChevronDown, ThumbsUp, ThumbsDown, Send, RotateCcw, Trash2, MapPin, BookmarkPlus, FileText,
} from 'lucide-react';

const PHASE_STEPS: WorkflowPhase[] = ['discovery', 'qualification', 'analysis', 'evaluation', 'approval', 'outreach', 'completed'];

function phaseLabel(phase: WorkflowPhase): string {
    const labels: Record<WorkflowPhase, string> = {
        discovery: 'Discovery',
        qualification: 'Qualification',
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

const BUSINESS_TYPES = [
    'Restaurants',
    'Barbers',
    'Bakeries',
];

export default function WorkflowDashboard() {
    const [launchMode, setLaunchMode] = useState<LaunchMode>('single');
    const [zipCode, setZipCode] = useState('');
    const [businessType, setBusinessType] = useState('Restaurants');
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
    const [research, setResearch] = useState<{ zipReports: Record<string, any>; areaResearch: Record<string, any> } | null>(null);
    const [researchOpen, setResearchOpen] = useState(false);
    const [researchLoading, setResearchLoading] = useState(false);
    const [expandedBiz, setExpandedBiz] = useState<string | null>(null);
    const [bizDetail, setBizDetail] = useState<Record<string, any>>({});
    const [bizDetailLoading, setBizDetailLoading] = useState<string | null>(null);

    const eventSourceRef = useRef<EventSource | null>(null);
    const refetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

    const fetchResearch = useCallback(async (id: string) => {
        setResearchLoading(true);
        try {
            const res = await fetch(`/api/workflows/${id}/research`);
            if (res.ok) {
                const data = await res.json();
                setResearch(data);
            }
        } catch { /* silent */ }
        finally { setResearchLoading(false); }
    }, []);

    const toggleBizDetail = useCallback(async (slug: string) => {
        if (expandedBiz === slug) {
            setExpandedBiz(null);
            return;
        }
        setExpandedBiz(slug);
        if (bizDetail[slug]) return; // already cached
        setBizDetailLoading(slug);
        try {
            const res = await fetch(`/api/research/businesses/${slug}`);
            if (res.ok) {
                const data = await res.json();
                setBizDetail(prev => ({ ...prev, [slug]: data }));
            }
        } catch { /* silent */ }
        finally { setBizDetailLoading(null); }
    }, [expandedBiz, bizDetail]);

    // Poll for active workflow state when not streaming
    useEffect(() => {
        if (!activeWorkflow) return;
        if (activeWorkflow.phase === 'completed' || activeWorkflow.phase === 'failed' || activeWorkflow.phase === 'approval') return;

        // SSE connection for live updates
        const es = new EventSource(`/api/workflows/${activeWorkflow.id}/stream`);
        eventSourceRef.current = es;

        // Debounced re-fetch: batches rapid events (e.g. many business:discovery in succession)
        const scheduleRefetch = (id: string) => {
            if (refetchTimerRef.current) return; // already scheduled
            refetchTimerRef.current = setTimeout(() => {
                refetchTimerRef.current = null;
                fetchWorkflow(id);
            }, 800);
        };

        es.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);

                // Handle stream-level events (initial, done, poll, heartbeat)
                if (data.type === 'initial' && data.workflow) {
                    setActiveWorkflow(data.workflow as WorkflowDocument);
                    return;
                }
                if (data.type === 'done') {
                    es.close();
                    if (data.workflow) {
                        setActiveWorkflow(data.workflow as WorkflowDocument);
                    } else {
                        fetchWorkflow(activeWorkflow.id);
                    }
                    fetchWorkflows();
                    return;
                }
                if (data.type === 'heartbeat' || data.type === 'error') return;
                if (data.type === 'poll' && data.progress) {
                    setActiveWorkflow(prev => prev ? { ...prev, progress: data.progress } : prev);
                    return;
                }
                // Polling fallback phase_changed includes full workflow
                if (data.type === 'phase_changed' && data.workflow) {
                    setActiveWorkflow(data.workflow as WorkflowDocument);
                    if (data.phase === 'approval' || data.phase === 'completed' || data.phase === 'failed') {
                        es.close();
                        fetchWorkflows();
                    }
                    return;
                }

                // Handle ProgressEvent from in-process engine streaming
                const event: ProgressEvent = data;
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
                    return;
                }

                // When reaching approval, fetch full state for business details
                if (event.phase === 'approval') {
                    es.close();
                    fetchWorkflow(activeWorkflow.id);
                    return;
                }

                // Re-fetch full workflow on phase transitions to pick up new data (e.g. businesses after discovery)
                if (event.type === 'workflow:phase_changed') {
                    fetchWorkflow(activeWorkflow.id);
                    return;
                }

                // Debounced re-fetch for business-level events (discovery, enrichment, analysis progress)
                if (event.type.startsWith('business:')) {
                    scheduleRefetch(activeWorkflow.id);
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
            if (refetchTimerRef.current) {
                clearTimeout(refetchTimerRef.current);
                refetchTimerRef.current = null;
            }
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
            if (!county.trim()) {
                setError('Enter a county (e.g. Essex County NJ)');
                return;
            }
        }

        setIsLaunching(true);
        setError(null);

        try {
            let res: Response;

            const resolvedType = businessType;

            if (launchMode === 'county') {
                res = await fetch('/api/workflows/county', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        businessType: resolvedType,
                        county: county.trim(),
                    }),
                });
            } else {
                const body: Record<string, string> = { zipCode, businessType: resolvedType };
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
        setResearch(null);
        setResearchOpen(false);
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
            <div className="bg-white border border-gray-200 px-4 py-3 rounded-xl shadow-sm">
                <div className="flex items-center gap-2">
                    <div className="flex items-center bg-gray-100 rounded-md p-0.5">
                        <button
                            onClick={() => setLaunchMode('single')}
                            className={`px-2 py-1 text-[11px] font-medium rounded transition-all ${
                                launchMode === 'single' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                        >
                            Zip
                        </button>
                        <button
                            onClick={() => setLaunchMode('county')}
                            className={`px-2 py-1 text-[11px] font-medium rounded transition-all flex items-center gap-0.5 ${
                                launchMode === 'county' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                            }`}
                        >
                            <MapPin className="w-2.5 h-2.5" /> County
                        </button>
                    </div>

                    {launchMode === 'single' ? (
                        <input
                            type="text"
                            value={zipCode}
                            onChange={e => setZipCode(e.target.value.replace(/\D/g, '').slice(0, 5))}
                            placeholder="07110"
                            className="w-24 px-2 py-1.5 bg-gray-50 border border-gray-300 rounded-md text-center font-mono text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                            maxLength={5}
                            onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                        />
                    ) : (
                        <input
                            type="text"
                            value={county}
                            onChange={e => setCounty(e.target.value)}
                            placeholder="Essex County NJ"
                            className="w-40 px-2 py-1.5 bg-gray-50 border border-gray-300 rounded-md text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                            onKeyDown={e => e.key === 'Enter' && handleLaunch()}
                        />
                    )}

                    <select
                        value={businessType}
                        onChange={e => setBusinessType(e.target.value)}
                        className="w-36 px-2 py-1.5 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                    >
                        {BUSINESS_TYPES.map(t => (
                            <option key={t} value={t}>{t}</option>
                        ))}
                    </select>

                    <button
                        onClick={handleLaunch}
                        disabled={isLaunching}
                        data-testid="launch-button"
                        className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-semibold rounded-md hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 shadow-sm transition-all"
                    >
                        {isLaunching ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Rocket className="w-3.5 h-3.5" />}
                        {isLaunching ? 'Launching...' : 'Launch'}
                    </button>
                </div>
                <p className="text-[11px] text-gray-400 mt-1.5">
                    Runs industry-specific research (sector analysis, area intel, zip demographics) in parallel with discovery, then qualifies leads before deep analysis.
                </p>
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
                        <div className="flex items-center gap-1" data-testid="phase-stepper" data-phase={activeWorkflow.phase}>
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
                    <div className="p-4 border-b border-gray-200 grid grid-cols-6 gap-3" data-testid="progress-counters">
                        <div className="text-center" data-testid="counter-discovered">
                            <div className="text-2xl font-bold text-gray-800">{activeWorkflow.progress.totalBusinesses}</div>
                            <div className="text-xs text-gray-500">Discovered</div>
                        </div>
                        <div className="text-center" data-testid="counter-qualified">
                            <div className="text-2xl font-bold text-emerald-500">{activeWorkflow.progress.qualificationQualified ?? 0}</div>
                            <div className="text-xs text-gray-500">Qualified</div>
                        </div>
                        <div className="text-center" data-testid="counter-parked">
                            <div className="text-2xl font-bold text-amber-400">{activeWorkflow.progress.qualificationParked ?? 0}</div>
                            <div className="text-xs text-gray-500">Parked</div>
                        </div>
                        <div className="text-center" data-testid="counter-analyzed">
                            <div className="text-2xl font-bold text-blue-500">{activeWorkflow.progress.analysisComplete}</div>
                            <div className="text-xs text-gray-500">Analyzed</div>
                        </div>
                        <div className="text-center" data-testid="counter-passed-qa">
                            <div className="text-2xl font-bold text-green-500">{activeWorkflow.progress.qualityPassed}</div>
                            <div className="text-xs text-gray-500">Passed QA</div>
                        </div>
                        <div className="text-center" data-testid="counter-outreached">
                            <div className="text-2xl font-bold text-purple-500">{activeWorkflow.progress.outreachComplete}</div>
                            <div className="text-xs text-gray-500">Outreached</div>
                        </div>
                    </div>

                    {/* Market Research */}
                    {activeWorkflow.zipCodes && activeWorkflow.zipCodes.length > 0 || activeWorkflow.zipCode ? (
                        <div className="border-b border-gray-200">
                            <button
                                onClick={() => {
                                    if (!researchOpen && !research) {
                                        fetchResearch(activeWorkflow.id);
                                    }
                                    setResearchOpen(!researchOpen);
                                }}
                                className="w-full px-4 py-2.5 flex items-center gap-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
                            >
                                <FileText className="w-4 h-4 text-indigo-500" />
                                Market Research
                                {researchLoading ? (
                                    <Loader2 className="w-3 h-3 animate-spin ml-1" />
                                ) : researchOpen ? (
                                    <ChevronDown className="w-3.5 h-3.5 ml-1" />
                                ) : (
                                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                                )}
                            </button>
                            {researchOpen && research && (
                                <div className="px-4 pb-4 space-y-4 max-h-[500px] overflow-y-auto">
                                    {Object.keys(research.zipReports).length === 0 && Object.keys(research.areaResearch).length === 0 && (
                                        <p className="text-xs text-gray-400 italic">No research data generated yet for this workflow.</p>
                                    )}

                                    {Object.entries(research.zipReports).map(([zip, report]: [string, any]) => (
                                        <div key={`zip-${zip}`} className="bg-indigo-50/50 rounded-lg p-3 border border-indigo-100">
                                            <h5 className="text-xs font-semibold text-indigo-700 mb-1.5">Zip Code Report: {zip}</h5>
                                            {report.summary && (
                                                <p className="text-xs text-gray-600 mb-2">{report.summary}</p>
                                            )}
                                            {report.sections && (
                                                <div className="space-y-2">
                                                    {Object.entries(report.sections)
                                                        .filter(([, section]: [string, any]) => section && section.content)
                                                        .map(([key, section]: [string, any]) => (
                                                            <details key={key} className="group">
                                                                <summary className="text-[11px] font-medium text-indigo-600 cursor-pointer hover:text-indigo-800 transition-colors">
                                                                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                                                </summary>
                                                                <p className="text-[11px] text-gray-600 mt-1 pl-2 border-l-2 border-indigo-200 whitespace-pre-line leading-relaxed">
                                                                    {section.content}
                                                                </p>
                                                            </details>
                                                        ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    {Object.entries(research.areaResearch).map(([zip, areaData]: [string, any]) => (
                                        <div key={`area-${zip}`} className="bg-emerald-50/50 rounded-lg p-3 border border-emerald-100">
                                            <h5 className="text-xs font-semibold text-emerald-700 mb-1">
                                                Area Research: {areaData.area || zip}
                                                {areaData.businessType && (
                                                    <span className="ml-1.5 font-normal text-emerald-500">({areaData.businessType})</span>
                                                )}
                                            </h5>
                                            {areaData.summary && (
                                                <div className="space-y-2">
                                                    {areaData.summary.synthesis && (
                                                        <p className="text-[11px] text-gray-600">{typeof areaData.summary.synthesis === 'string' ? areaData.summary.synthesis : JSON.stringify(areaData.summary.synthesis)}</p>
                                                    )}
                                                    {areaData.summary.sections && Object.entries(areaData.summary.sections)
                                                        .filter(([, v]: [string, any]) => v)
                                                        .map(([key, val]: [string, any]) => (
                                                            <details key={key} className="group">
                                                                <summary className="text-[11px] font-medium text-emerald-600 cursor-pointer hover:text-emerald-800 transition-colors">
                                                                    {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                                                </summary>
                                                                <p className="text-[11px] text-gray-600 mt-1 pl-2 border-l-2 border-emerald-200 whitespace-pre-line leading-relaxed">
                                                                    {typeof val === 'string' ? val : JSON.stringify(val, null, 2)}
                                                                </p>
                                                            </details>
                                                        ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : null}

                    {/* Business Cards */}
                    {activeWorkflow.businesses && activeWorkflow.businesses.length > 0 && (
                        <div className="p-4 space-y-2">
                            {activeWorkflow.businesses.map(biz => (
                                <div key={biz.slug} data-testid={`business-card-${biz.slug}`} data-phase={biz.phase} className="bg-gray-50 rounded-lg border border-gray-200">
                                <div className="flex items-center justify-between p-3">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <button onClick={() => toggleBizDetail(biz.slug)} className="font-medium text-sm text-gray-800 hover:text-indigo-600 transition-colors text-left flex items-center gap-1">
                                                {expandedBiz === biz.slug ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                                                {biz.name}
                                            </button>
                                            <span className="text-xs text-gray-400">{biz.slug}</span>
                                            {biz.sourceZipCode && activeWorkflow.zipCodes && activeWorkflow.zipCodes.length > 0 && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-mono">{biz.sourceZipCode}</span>
                                            )}
                                        </div>
                                        <div className="text-xs text-gray-500 mt-0.5">{biz.address}</div>
                                        {!biz.officialUrl && biz.phase !== 'pending' && (
                                            <div className="text-[10px] text-amber-600 mt-0.5">No website found</div>
                                        )}
                                        {biz.lastError && !biz.lastError.includes('retry_queued') && (
                                            <div className="text-[10px] text-red-500 mt-0.5 truncate max-w-md" title={biz.lastError}>
                                                Error: {biz.lastError.length > 100 ? biz.lastError.slice(0, 100) + '…' : biz.lastError}
                                            </div>
                                        )}
                                        {biz.capabilitiesFailed.length > 0 && biz.capabilitiesCompleted.length > 0 && biz.phase === 'analyzing' && (
                                            <div className="text-[10px] text-blue-500 mt-0.5 flex items-center gap-1">
                                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                                Retrying: {biz.capabilitiesFailed.join(', ')}
                                            </div>
                                        )}
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
                                                }`} title={`${cap} QA eval: ${ev.score}/100${ev.isHallucinated ? ' (hallucinated)' : ''}`}>
                                                    {cap}: {ev.score}
                                                </span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Phase badge / Approval toggle */}
                                    {activeWorkflow.phase === 'approval' && biz.phase === 'evaluation_done' ? (
                                        <div className="flex items-center gap-2">
                                            {!biz.qualityPassed && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200" title="Did not pass automated QA">
                                                    Low QA
                                                </span>
                                            )}
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
                                        <span data-testid="phase-badge" className={`text-xs px-2 py-0.5 rounded-full ${
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

                                {/* Expandable detail panel */}
                                {expandedBiz === biz.slug && (
                                    <div className="border-t border-gray-200 px-4 py-3 bg-white">
                                        {bizDetailLoading === biz.slug ? (
                                            <div className="flex items-center gap-2 text-xs text-gray-400">
                                                <Loader2 className="w-3 h-3 animate-spin" /> Loading business details...
                                            </div>
                                        ) : bizDetail[biz.slug] ? (
                                            <div className="grid grid-cols-2 gap-4 text-xs">
                                                {/* Left: Identity */}
                                                <div className="space-y-2">
                                                    <h5 className="font-semibold text-gray-700 text-[11px] uppercase tracking-wide">Discovery Profile</h5>
                                                    {bizDetail[biz.slug].officialUrl && (
                                                        <div><span className="text-gray-400">Website:</span>{' '}
                                                            <a href={bizDetail[biz.slug].officialUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">{bizDetail[biz.slug].officialUrl}</a>
                                                        </div>
                                                    )}
                                                    {bizDetail[biz.slug].phone && <div><span className="text-gray-400">Phone:</span> {bizDetail[biz.slug].phone}</div>}
                                                    {bizDetail[biz.slug].email && <div><span className="text-gray-400">Email:</span> {bizDetail[biz.slug].email}</div>}
                                                    {bizDetail[biz.slug].hours && <div><span className="text-gray-400">Hours:</span> {bizDetail[biz.slug].hours}</div>}
                                                    {bizDetail[biz.slug].menuUrl && (
                                                        <div><span className="text-gray-400">Menu:</span>{' '}
                                                            <a href={bizDetail[biz.slug].menuUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">View Menu</a>
                                                        </div>
                                                    )}
                                                    {bizDetail[biz.slug].persona && (
                                                        <div className="mt-1"><span className="text-gray-400">Persona:</span> <span className="text-gray-600">{bizDetail[biz.slug].persona}</span></div>
                                                    )}
                                                    {bizDetail[biz.slug].socialLinks && Object.keys(bizDetail[biz.slug].socialLinks).length > 0 && (
                                                        <div>
                                                            <span className="text-gray-400">Social:</span>{' '}
                                                            {Object.entries(bizDetail[biz.slug].socialLinks).map(([platform, url]) => (
                                                                <a key={platform} href={url as string} target="_blank" rel="noopener noreferrer" className="inline-block mr-2 text-indigo-600 hover:underline">{platform}</a>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {bizDetail[biz.slug].competitors?.length > 0 && (
                                                        <div>
                                                            <span className="text-gray-400">Competitors:</span>{' '}
                                                            <span className="text-gray-600">{bizDetail[biz.slug].competitors.map((c: any) => typeof c === 'string' ? c : c.name).join(', ')}</span>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Right: Capability summaries + Insights */}
                                                <div className="space-y-2">
                                                    {bizDetail[biz.slug].capabilities && Object.keys(bizDetail[biz.slug].capabilities).length > 0 && (
                                                        <>
                                                            <h5 className="font-semibold text-gray-700 text-[11px] uppercase tracking-wide">Analysis Results</h5>
                                                            {Object.entries(bizDetail[biz.slug].capabilities).map(([cap, data]: [string, any]) => (
                                                                <div key={cap} className="bg-gray-50 rounded p-2 border border-gray-100">
                                                                    <div className="flex items-center justify-between">
                                                                        <span className="font-medium text-gray-700">{cap.replace(/_/g, ' ')}</span>
                                                                        {data.score != null && (
                                                                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${data.score >= 70 ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>
                                                                                {data.score}/100
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    {data.summary && <p className="text-gray-500 mt-0.5 line-clamp-3">{data.summary}</p>}
                                                                    {data.reportUrl && (
                                                                        <a href={data.reportUrl} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline text-[10px] mt-0.5 inline-block">View Full Report</a>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </>
                                                    )}
                                                    {bizDetail[biz.slug].insights && (
                                                        <>
                                                            <h5 className="font-semibold text-gray-700 text-[11px] uppercase tracking-wide mt-2">Insights</h5>
                                                            <p className="text-gray-600">{bizDetail[biz.slug].insights.summary}</p>
                                                            {bizDetail[biz.slug].insights.keyFindings?.length > 0 && (
                                                                <ul className="list-disc list-inside text-gray-500 space-y-0.5">
                                                                    {bizDetail[biz.slug].insights.keyFindings.map((f: string, i: number) => <li key={i}>{f}</li>)}
                                                                </ul>
                                                            )}
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <p className="text-xs text-gray-400 italic">No details available for this business.</p>
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
                                onClick={() => { setActiveWorkflow(null); setApprovals({}); setResearch(null); setResearchOpen(false); setConfirmDeleteActive(false); setConfirmStop(false); }}
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
