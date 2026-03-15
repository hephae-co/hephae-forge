'use client';

import { useState } from 'react';
import { WorkflowDocument, WorkflowPhase } from '@/lib/workflow/types';
import { Clock, CheckCircle2, XCircle, Pause, Loader2, Trash2, StopCircle } from 'lucide-react';

interface WorkflowHistoryProps {
    workflows: WorkflowDocument[];
    onSelect: (workflowId: string) => void;
    onDelete: (workflowId: string) => Promise<void>;
    onStop?: (workflowId: string) => Promise<void>;
    onForceDelete?: (workflowId: string) => Promise<void>;
    deletingId?: string | null;
    stoppingId?: string | null;
}

const ACTIVE_PHASES: WorkflowPhase[] = ['discovery', 'qualification', 'analysis', 'evaluation', 'outreach'];

function phaseBadge(phase: WorkflowPhase) {
    switch (phase) {
        case 'completed':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-50 text-green-600 border border-green-200"><CheckCircle2 className="w-3 h-3" /> Done</span>;
        case 'failed':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200"><XCircle className="w-3 h-3" /> Failed</span>;
        case 'approval':
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200"><Pause className="w-3 h-3" /> Awaiting Approval</span>;
        default:
            return <span className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-200"><Loader2 className="w-3 h-3 animate-spin" /> {phase}</span>;
    }
}

export default function WorkflowHistory({ workflows, onSelect, onDelete, onStop, onForceDelete, deletingId, stoppingId }: WorkflowHistoryProps) {
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [confirmAction, setConfirmAction] = useState<'delete' | 'stop' | 'force-delete' | null>(null);

    if (workflows.length === 0) {
        return (
            <div className="text-center py-12 border border-dashed border-gray-300 rounded-xl text-gray-400">
                <Clock className="w-10 h-10 mx-auto mb-3 opacity-30" />
                <p>No workflow history yet. Launch a pipeline above to get started.</p>
            </div>
        );
    }

    const startConfirm = (id: string, action: 'delete' | 'stop' | 'force-delete') => {
        setConfirmingId(id);
        setConfirmAction(action);
    };

    const clearConfirm = () => {
        setConfirmingId(null);
        setConfirmAction(null);
    };

    return (
        <div className="space-y-2">
            {workflows.map(wf => {
                const isConfirming = confirmingId === wf.id;
                const isDeleting = deletingId === wf.id;
                const isStopping = stoppingId === wf.id;
                const isActive = ACTIVE_PHASES.includes(wf.phase);

                return (
                    <div
                        key={wf.id}
                        className={`relative w-full text-left p-4 border rounded-lg transition-all ${
                            isConfirming
                                ? 'bg-red-50 border-red-200'
                                : 'bg-white border-gray-200 hover:shadow-md hover:border-gray-300'
                        }`}
                    >
                        <button
                            onClick={() => onSelect(wf.id)}
                            className="w-full text-left"
                            disabled={isConfirming || isDeleting || isStopping}
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <span className="text-xs font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{wf.id.slice(0, 8)}</span>
                                    <span className="text-sm font-mono text-gray-700 bg-gray-100 px-2 py-0.5 rounded">
                                        {wf.county || wf.zipCode}
                                    </span>
                                    {wf.businessType && (
                                        <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">
                                            {wf.businessType}
                                        </span>
                                    )}
                                    {phaseBadge(wf.phase)}
                                </div>
                                <span className="text-xs text-gray-400">
                                    {new Date(wf.createdAt).toLocaleDateString()} {new Date(wf.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                            <div className="mt-2 flex gap-4 text-xs text-gray-500">
                                <span>{wf.progress.totalBusinesses} businesses</span>
                                <span>{wf.progress.analysisComplete} analyzed</span>
                                <span>{wf.progress.qualityPassed} passed QA</span>
                                <span>{wf.progress.outreachComplete} outreached</span>
                            </div>
                        </button>

                        {/* Action buttons — top right */}
                        {!isConfirming && !isDeleting && !isStopping && (
                            <div className="absolute top-4 right-4 flex items-center gap-1">
                                {isActive && onStop && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); startConfirm(wf.id, 'stop'); }}
                                        className="p-1.5 text-gray-300 hover:text-amber-500 hover:bg-amber-50 rounded transition-colors"
                                        title="Stop run"
                                    >
                                        <StopCircle className="w-4 h-4" />
                                    </button>
                                )}
                                {isActive && onForceDelete && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); startConfirm(wf.id, 'force-delete'); }}
                                        className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                        title="Force delete"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                                {!isActive && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); startConfirm(wf.id, 'delete'); }}
                                        className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                                        title="Delete run"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                )}
                            </div>
                        )}

                        {/* Confirmation bar */}
                        {isConfirming && !isDeleting && !isStopping && (
                            <div className="mt-3 flex items-center gap-3 pt-3 border-t border-red-200">
                                <span className="text-xs text-red-500">
                                    {confirmAction === 'stop' ? 'Stop this running workflow?' :
                                     confirmAction === 'force-delete' ? 'Force delete this running workflow and its data?' :
                                     'Delete this run and its business data?'}
                                </span>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (confirmAction === 'stop' && onStop) {
                                            onStop(wf.id).finally(clearConfirm);
                                        } else if (confirmAction === 'force-delete' && onForceDelete) {
                                            onForceDelete(wf.id).finally(clearConfirm);
                                        } else {
                                            onDelete(wf.id).finally(clearConfirm);
                                        }
                                    }}
                                    className={`px-3 py-1 text-xs font-semibold text-white rounded transition-colors ${
                                        confirmAction === 'stop' ? 'bg-amber-500 hover:bg-amber-400' : 'bg-red-600 hover:bg-red-500'
                                    }`}
                                >
                                    Confirm
                                </button>
                                <button
                                    onClick={(e) => { e.stopPropagation(); clearConfirm(); }}
                                    className="px-3 py-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        )}

                        {isStopping && (
                            <div className="mt-3 flex items-center gap-2 pt-3 border-t border-amber-200">
                                <Loader2 className="w-3 h-3 animate-spin text-amber-500" />
                                <span className="text-xs text-amber-500">Stopping...</span>
                            </div>
                        )}

                        {isDeleting && (
                            <div className="mt-3 flex items-center gap-2 pt-3 border-t border-red-200">
                                <Loader2 className="w-3 h-3 animate-spin text-red-500" />
                                <span className="text-xs text-red-500">Deleting...</span>
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
