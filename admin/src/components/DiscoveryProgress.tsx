'use client';

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, CheckCircle2, XCircle, Loader2, Search, ShieldCheck, BarChart3 } from 'lucide-react';

interface DiscoveryProgressData {
    zipCode: string;
    status: 'running' | 'completed' | 'failed';
    phase: 'planning' | 'scanning' | 'verifying' | 'scoring' | 'complete';
    currentAgent: string | null;
    categoriesPlanned: number;
    categoriesScanned: number;
    totalCategories: number;
    businessesFound: number;
    businessesVerified: number;
    businessesPassed: number;
    startedAt: string;
    completedAt: string | null;
    error: string | null;
}

interface DiscoveryProgressProps {
    zipCode: string;
    onComplete?: () => void;
}

const PHASE_STEPS = [
    { key: 'planning', label: 'Planning', icon: Search },
    { key: 'scanning', label: 'Scanning', icon: Search },
    { key: 'verifying', label: 'Verifying', icon: ShieldCheck },
    { key: 'scoring', label: 'Scoring', icon: BarChart3 },
    { key: 'complete', label: 'Done', icon: CheckCircle2 },
] as const;

const AGENT_LABELS: Record<string, string> = {
    category_planner: 'Planning categories...',
    category_scanner: 'Searching for businesses...',
    discovery_accumulator: 'Collecting results...',
    category_progress_checker: 'Advancing to next category...',
    business_verifier: 'Cross-verifying businesses...',
    confidence_scorer: 'Scoring confidence...',
};

function getElapsedTime(startedAt: string, completedAt: string | null): string {
    const start = new Date(startedAt).getTime();
    const end = completedAt ? new Date(completedAt).getTime() : Date.now();
    const seconds = Math.floor((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
}

export default function DiscoveryProgress({ zipCode, onComplete }: DiscoveryProgressProps) {
    const [progress, setProgress] = useState<DiscoveryProgressData | null>(null);
    const [loading, setLoading] = useState(false);
    const [lastFetched, setLastFetched] = useState<Date | null>(null);

    const fetchProgress = useCallback(async () => {
        if (!zipCode) return;
        setLoading(true);
        try {
            const res = await fetch(`/api/research/discovery-status?zipCode=${zipCode}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.success && data.progress) {
                setProgress(data.progress);
                if (data.progress.status === 'completed' && onComplete) {
                    onComplete();
                }
            }
            setLastFetched(new Date());
        } catch (err) {
            console.error('[DiscoveryProgress] fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, [zipCode, onComplete]);

    useEffect(() => {
        fetchProgress();
    }, [fetchProgress]);

    // Auto-refresh every 5s while running
    useEffect(() => {
        if (!progress || progress.status !== 'running') return;
        const interval = setInterval(fetchProgress, 5000);
        return () => clearInterval(interval);
    }, [progress?.status, fetchProgress]);

    if (!progress) return null;

    const phaseIndex = PHASE_STEPS.findIndex(s => s.key === progress.phase);
    const isRunning = progress.status === 'running';
    const isFailed = progress.status === 'failed';
    const isComplete = progress.status === 'completed';

    return (
        <div className={`border rounded-xl p-5 mb-6 transition-all ${
            isRunning ? 'bg-indigo-50 border-indigo-200' :
            isFailed ? 'bg-red-50 border-red-200' :
            'bg-green-50 border-green-200'
        }`}>
            {/* Header */}
            <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                    {isRunning && <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />}
                    {isComplete && <CheckCircle2 className="w-4 h-4 text-green-600" />}
                    {isFailed && <XCircle className="w-4 h-4 text-red-600" />}
                    <h4 className={`font-semibold text-sm ${
                        isRunning ? 'text-indigo-700' : isFailed ? 'text-red-700' : 'text-green-700'
                    }`}>
                        Discovery Pipeline — {zipCode}
                        {isRunning && <span className="ml-2 font-normal text-xs opacity-75">
                            {getElapsedTime(progress.startedAt, null)} elapsed
                        </span>}
                        {isComplete && progress.completedAt && <span className="ml-2 font-normal text-xs opacity-75">
                            completed in {getElapsedTime(progress.startedAt, progress.completedAt)}
                        </span>}
                    </h4>
                </div>
                <button
                    onClick={fetchProgress}
                    disabled={loading}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                    title="Refresh status"
                >
                    <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                    {lastFetched && <span className="hidden sm:inline">
                        {lastFetched.toLocaleTimeString()}
                    </span>}
                </button>
            </div>

            {/* Phase progress bar */}
            <div className="flex items-center gap-1 mb-4">
                {PHASE_STEPS.map((step, i) => {
                    const StepIcon = step.icon;
                    const isActive = step.key === progress.phase;
                    const isDone = i < phaseIndex || isComplete;
                    return (
                        <div key={step.key} className="flex items-center flex-1">
                            <div className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium w-full justify-center ${
                                isActive && isRunning ? 'bg-indigo-600 text-white' :
                                isDone ? 'bg-green-100 text-green-700 border border-green-200' :
                                'bg-gray-100 text-gray-400 border border-gray-200'
                            }`}>
                                <StepIcon className="w-3 h-3" />
                                <span className="hidden sm:inline">{step.label}</span>
                            </div>
                            {i < PHASE_STEPS.length - 1 && (
                                <div className={`w-2 h-0.5 mx-0.5 ${isDone ? 'bg-green-300' : 'bg-gray-200'}`} />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Current activity */}
            {isRunning && progress.currentAgent && (
                <p className="text-xs text-indigo-600 mb-3 italic">
                    {AGENT_LABELS[progress.currentAgent] || progress.currentAgent}
                </p>
            )}

            {/* Stats grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-white rounded-lg p-2 border border-gray-200 text-center">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Categories</p>
                    <p className="text-lg font-bold text-gray-900">
                        {progress.categoriesScanned}
                        <span className="text-sm font-normal text-gray-400">
                            /{progress.totalCategories || '?'}
                        </span>
                    </p>
                </div>
                <div className="bg-white rounded-lg p-2 border border-gray-200 text-center">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Found</p>
                    <p className="text-lg font-bold text-gray-900">{progress.businessesFound}</p>
                </div>
                <div className="bg-white rounded-lg p-2 border border-gray-200 text-center">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Verified</p>
                    <p className="text-lg font-bold text-gray-900">{progress.businessesVerified}</p>
                </div>
                <div className="bg-white rounded-lg p-2 border border-gray-200 text-center">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">Passed</p>
                    <p className="text-lg font-bold text-green-600">{progress.businessesPassed}</p>
                </div>
            </div>

            {/* Error */}
            {isFailed && progress.error && (
                <div className="mt-3 p-2 bg-red-100 border border-red-200 rounded text-xs text-red-700">
                    {progress.error}
                </div>
            )}
        </div>
    );
}
