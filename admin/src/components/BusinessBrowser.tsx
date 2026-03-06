'use client';

import { useState, useEffect, useRef } from 'react';
import {
    Mail, Zap, ExternalLink, MessageSquare, Loader2, CheckCircle2,
    MoreVertical, Trash2, RefreshCw, BookmarkPlus, AlertTriangle,
    Instagram, Facebook, X, Search, BarChart3, Tag
} from 'lucide-react';

type DiscoveryStatus = 'scanned' | 'discovering' | 'discovered' | 'analyzing' | 'analyzed' | 'failed';

interface Business {
    id: string;
    name: string;
    address?: string;
    zipCode: string;
    category?: string;
    discoveryStatus?: DiscoveryStatus;
    identity?: {
        email?: string;
        socialLinks?: { instagram?: string; facebook?: string };
    };
    latestOutputs?: {
        seo_auditor?: { score: number };
        traffic_forecaster?: { score: number };
        competitive_analyzer?: { score: number };
    };
    crm?: {
        status: string;
        outreachCount: number;
    };
}

type OutreachChannel = 'email' | 'instagram' | 'facebook';

interface BusinessBrowserProps {
    zipCode: string;
}

export default function BusinessBrowser({ zipCode }: BusinessBrowserProps) {
    const [businesses, setBusinesses] = useState<Business[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [actionId, setActionId] = useState<string | null>(null);
    const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [bulkAction, setBulkAction] = useState<string | null>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    const fetchBusinesses = async () => {
        if (!zipCode) return;
        setIsLoading(true);
        try {
            const res = await fetch(`/api/research/businesses?zipCode=${zipCode}`);
            if (!res.ok) throw new Error("Failed to fetch");
            const data = await res.json();
            setBusinesses(data);
        } catch (err) {
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchBusinesses();
    }, [zipCode]);

    // Close menu on outside click
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setMenuOpenId(null);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const clearSelection = () => {
        setSelectedIds(new Set());
    };

    const handleAction = async (biz: Business, action: string, opts?: { channel?: OutreachChannel; fixtureType?: string }) => {
        const key = biz.id + action + (opts?.channel || '') + (opts?.fixtureType || '');
        setActionId(key);
        setMenuOpenId(null);
        try {
            const res = await fetch('/api/research/actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action,
                    businessId: biz.id,
                    businessName: biz.name,
                    businessAddress: biz.address,
                    zipCode: biz.zipCode,
                    channel: opts?.channel,
                    fixtureType: opts?.fixtureType,
                })
            });
            if (res.ok) {
                if (action === 'delete' || action === 'rediscover') {
                    setBusinesses(prev => prev.filter(b => b.id !== biz.id));
                    setSelectedIds(prev => { const next = new Set(prev); next.delete(biz.id); return next; });
                } else {
                    await fetchBusinesses();
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setActionId(null);
            setConfirmingId(null);
        }
    };

    const handleDelete = async (biz: Business) => {
        setDeletingId(biz.id);
        try {
            const res = await fetch('/api/research/actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete', businessId: biz.id })
            });
            if (res.ok) {
                setBusinesses(prev => prev.filter(b => b.id !== biz.id));
                setSelectedIds(prev => { const next = new Set(prev); next.delete(biz.id); return next; });
            }
        } catch (err) {
            console.error(err);
        } finally {
            setDeletingId(null);
            setConfirmingId(null);
        }
    };

    const handleBulkAction = async (action: string, opts?: { channel?: OutreachChannel; fixtureType?: string }) => {
        const ids = Array.from(selectedIds);
        if (!ids.length) return;
        setBulkAction(action);
        try {
            const res = await fetch('/api/research/actions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'bulk',
                    businessIds: ids,
                    bulkAction: action,
                    channel: opts?.channel,
                    fixtureType: opts?.fixtureType,
                })
            });
            if (res.ok) {
                if (action === 'delete') {
                    setBusinesses(prev => prev.filter(b => !selectedIds.has(b.id)));
                    clearSelection();
                } else {
                    await fetchBusinesses();
                    if (action !== 'save-fixture') clearSelection();
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setBulkAction(null);
        }
    };

    // Compute common channels across selected businesses for bulk outreach
    const getCommonChannels = (): OutreachChannel[] => {
        if (selectedIds.size === 0) return [];
        const selected = businesses.filter(b => selectedIds.has(b.id));
        const channels: OutreachChannel[] = [];
        if (selected.every(b => b.identity?.email)) channels.push('email');
        if (selected.every(b => b.identity?.socialLinks?.instagram)) channels.push('instagram');
        if (selected.every(b => b.identity?.socialLinks?.facebook)) channels.push('facebook');
        return channels;
    };

    const getAvailableChannels = (biz: Business): OutreachChannel[] => {
        const channels: OutreachChannel[] = [];
        if (biz.identity?.email) channels.push('email');
        if (biz.identity?.socialLinks?.instagram) channels.push('instagram');
        if (biz.identity?.socialLinks?.facebook) channels.push('facebook');
        return channels;
    };

    if (isLoading) return (
        <div className="flex justify-center p-12">
            <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        </div>
    );

    if (businesses.length === 0) return (
        <div className="text-center p-12 border border-dashed border-gray-300 rounded-xl text-gray-400">
            No businesses found for zip code {zipCode}. Trigger a Discovery first.
        </div>
    );

    const commonChannels = getCommonChannels();

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-700">Results for {zipCode} ({businesses.length})</h3>
                <div className="flex items-center gap-3">
                    {businesses.length > 0 && (
                        <label className="text-xs text-gray-500 flex items-center gap-1.5 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={selectedIds.size === businesses.length && businesses.length > 0}
                                onChange={() => {
                                    if (selectedIds.size === businesses.length) {
                                        clearSelection();
                                    } else {
                                        setSelectedIds(new Set(businesses.map(b => b.id)));
                                    }
                                }}
                                className="rounded border-gray-300"
                            />
                            Select All
                        </label>
                    )}
                    <button onClick={fetchBusinesses} className="text-sm text-indigo-500 hover:text-indigo-600 flex items-center gap-1">
                        <Zap className="w-4 h-4" /> Refresh
                    </button>
                </div>
            </div>

            {/* Floating bulk toolbar */}
            {selectedIds.size > 0 && (
                <div className="sticky top-2 z-20 bg-indigo-50 border border-indigo-200 rounded-xl p-3 flex flex-wrap items-center gap-2 shadow-lg">
                    <span className="text-sm font-medium text-indigo-700">
                        {selectedIds.size} selected
                    </span>
                    <div className="h-5 w-px bg-indigo-200" />

                    <button
                        onClick={() => handleBulkAction('delete')}
                        disabled={!!bulkAction}
                        className="text-xs bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-red-200"
                    >
                        {bulkAction === 'delete' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                        Bulk Delete
                    </button>

                    <button
                        onClick={() => handleBulkAction('save-fixture', { fixtureType: 'grounding' })}
                        disabled={!!bulkAction}
                        className="text-xs bg-emerald-100 hover:bg-emerald-200 text-emerald-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-emerald-200"
                    >
                        {bulkAction === 'save-fixture' ? <Loader2 className="w-3 h-3 animate-spin" /> : <BookmarkPlus className="w-3 h-3" />}
                        Save as Grounding
                    </button>

                    <button
                        onClick={() => handleBulkAction('save-fixture', { fixtureType: 'failure_case' })}
                        disabled={!!bulkAction}
                        className="text-xs bg-amber-100 hover:bg-amber-200 text-amber-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-amber-200"
                    >
                        {bulkAction === 'save-fixture' ? <Loader2 className="w-3 h-3 animate-spin" /> : <AlertTriangle className="w-3 h-3" />}
                        Save as Failure Case
                    </button>

                    <div className="h-5 w-px bg-indigo-200" />

                    <button
                        onClick={() => handleBulkAction('start-discovery')}
                        disabled={!!bulkAction}
                        className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-blue-200"
                    >
                        {bulkAction === 'start-discovery' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                        Discover
                    </button>

                    <button
                        onClick={() => handleBulkAction('run-analysis')}
                        disabled={!!bulkAction}
                        className="text-xs bg-violet-100 hover:bg-violet-200 text-violet-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-violet-200"
                    >
                        {bulkAction === 'run-analysis' ? <Loader2 className="w-3 h-3 animate-spin" /> : <BarChart3 className="w-3 h-3" />}
                        Analyze
                    </button>

                    {commonChannels.map(ch => (
                        <button
                            key={ch}
                            onClick={() => handleBulkAction('outreach', { channel: ch })}
                            disabled={!!bulkAction}
                            className="text-xs bg-indigo-100 hover:bg-indigo-200 text-indigo-700 px-3 py-1.5 rounded-lg flex items-center gap-1 border border-indigo-200"
                        >
                            {bulkAction === 'outreach' ? <Loader2 className="w-3 h-3 animate-spin" /> : channelIcon(ch)}
                            Outreach ({ch})
                        </button>
                    ))}

                    <div className="ml-auto">
                        <button
                            onClick={clearSelection}
                            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                        >
                            <X className="w-3 h-3" /> Clear
                        </button>
                    </div>
                </div>
            )}

            <div className="grid gap-4">
                {businesses.map((biz) => {
                    const isSelected = selectedIds.has(biz.id);
                    const isConfirming = confirmingId === biz.id;
                    const isDeleting = deletingId === biz.id;
                    const channels = getAvailableChannels(biz);

                    return (
                        <div
                            key={biz.id}
                            className={`bg-white border rounded-xl p-5 transition-all ${
                                isConfirming ? 'border-red-300 bg-red-50/30' :
                                isSelected ? 'border-indigo-400 bg-indigo-50/30 shadow-sm' :
                                'border-gray-200 hover:shadow-md hover:border-gray-300'
                            }`}
                        >
                            <div className="flex flex-col md:flex-row justify-between gap-4">
                                {/* Left: checkbox + info */}
                                <div className="flex gap-3 flex-1">
                                    <div className="pt-1">
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => toggleSelect(biz.id)}
                                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                                        />
                                    </div>
                                    <div className="flex-1">
                                        <h4 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                                            {biz.name}
                                            {biz.crm?.status === 'outreached' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                                            {statusBadge(biz.discoveryStatus)}
                                        </h4>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            <p className="text-sm text-gray-500">{biz.address}</p>
                                            {biz.category && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center gap-0.5">
                                                    <Tag className="w-2.5 h-2.5" /> {biz.category}
                                                </span>
                                            )}
                                        </div>

                                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                                            {biz.identity?.email && (
                                                <span className="bg-indigo-50 text-indigo-600 px-2 py-1 rounded flex items-center gap-1 border border-indigo-100">
                                                    <Mail className="w-3 h-3" /> {biz.identity.email}
                                                </span>
                                            )}
                                            {biz.identity?.socialLinks?.instagram && (
                                                <span className="bg-purple-50 text-purple-600 px-2 py-1 rounded flex items-center gap-1 border border-purple-100">
                                                    <Instagram className="w-3 h-3" /> Instagram
                                                </span>
                                            )}
                                            {biz.identity?.socialLinks?.facebook && (
                                                <span className="bg-blue-50 text-blue-600 px-2 py-1 rounded flex items-center gap-1 border border-blue-100">
                                                    <Facebook className="w-3 h-3" /> Facebook
                                                </span>
                                            )}
                                            <span className={`px-2 py-1 rounded border ${biz.crm?.status === 'outreached' ? 'border-green-200 text-green-600 bg-green-50' : 'border-gray-200 text-gray-500'}`}>
                                                CRM: {biz.crm?.status || 'Idle'} ({biz.crm?.outreachCount || 0})
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Right: scores + actions */}
                                <div className="flex flex-col gap-2 min-w-[180px]">
                                    {/* Score badges */}
                                    <div className="grid grid-cols-2 gap-2 mb-1">
                                        <div className="text-center p-1 bg-gray-50 rounded border border-gray-200">
                                            <p className="text-[10px] text-gray-500 uppercase">SEO</p>
                                            <p className="font-bold text-gray-900">{biz.latestOutputs?.seo_auditor?.score || '-'}</p>
                                        </div>
                                        <div className="text-center p-1 bg-gray-50 rounded border border-gray-200">
                                            <p className="text-[10px] text-gray-500 uppercase">Traffic</p>
                                            <p className="font-bold text-gray-900">{biz.latestOutputs?.traffic_forecaster?.score || '-'}</p>
                                        </div>
                                    </div>

                                    {/* Delete confirmation row */}
                                    {isConfirming ? (
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => handleDelete(biz)}
                                                disabled={isDeleting}
                                                className="flex-1 text-xs bg-red-600 hover:bg-red-500 text-white py-2 rounded flex items-center justify-center gap-1"
                                            >
                                                {isDeleting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                                                {isDeleting ? 'Deleting...' : 'Confirm'}
                                            </button>
                                            <button
                                                onClick={() => setConfirmingId(null)}
                                                className="flex-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    ) : (
                                        <>
                                            {/* Discovery / Analysis action buttons */}
                                            {(!biz.discoveryStatus || biz.discoveryStatus === 'scanned' || biz.discoveryStatus === 'failed') && (
                                                <button
                                                    onClick={() => handleAction(biz, 'start-discovery')}
                                                    disabled={!!actionId}
                                                    className="w-full text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 py-2 rounded flex items-center justify-center gap-1.5 border border-blue-200"
                                                >
                                                    {actionId === biz.id + 'start-discovery' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
                                                    Discover
                                                </button>
                                            )}
                                            {(biz.discoveryStatus === 'discovered' || biz.discoveryStatus === 'analyzed') && (
                                                <button
                                                    onClick={() => handleAction(biz, 'run-analysis')}
                                                    disabled={!!actionId}
                                                    className="w-full text-xs bg-violet-50 hover:bg-violet-100 text-violet-700 py-2 rounded flex items-center justify-center gap-1.5 border border-violet-200"
                                                >
                                                    {actionId === biz.id + 'run-analysis' ? <Loader2 className="w-3 h-3 animate-spin" /> : <BarChart3 className="w-3 h-3" />}
                                                    {biz.discoveryStatus === 'analyzed' ? 'Re-Analyze' : 'Analyze'}
                                                </button>
                                            )}

                                            {/* Action buttons row */}
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleAction(biz, 'deep-dive')}
                                                    disabled={!!actionId || !biz.discoveryStatus || biz.discoveryStatus === 'scanned'}
                                                    className="flex-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded flex items-center justify-center gap-1.5 border border-gray-200 disabled:opacity-40"
                                                >
                                                    {actionId === biz.id + 'deep-dive' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3 text-amber-500" />}
                                                    Deep Dive
                                                </button>

                                                {/* 3-dot menu */}
                                                <div className="relative" ref={menuOpenId === biz.id ? menuRef : undefined}>
                                                    <button
                                                        onClick={() => setMenuOpenId(menuOpenId === biz.id ? null : biz.id)}
                                                        className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-500 px-2 py-2 rounded border border-gray-200"
                                                    >
                                                        <MoreVertical className="w-3.5 h-3.5" />
                                                    </button>
                                                    {menuOpenId === biz.id && (
                                                        <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-xl z-30 py-1">
                                                            <button
                                                                onClick={() => { setConfirmingId(biz.id); setMenuOpenId(null); }}
                                                                className="w-full text-left text-xs px-3 py-2 hover:bg-red-50 text-red-600 flex items-center gap-2"
                                                            >
                                                                <Trash2 className="w-3 h-3" /> Delete Business
                                                            </button>
                                                            <button
                                                                onClick={() => handleAction(biz, 'rediscover')}
                                                                disabled={!!actionId}
                                                                className="w-full text-left text-xs px-3 py-2 hover:bg-gray-50 text-gray-700 flex items-center gap-2"
                                                            >
                                                                {actionId === biz.id + 'rediscover' ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                                                Re-run Discovery
                                                            </button>
                                                            <div className="border-t border-gray-100 my-1" />
                                                            <button
                                                                onClick={() => handleAction(biz, 'save-fixture', { fixtureType: 'grounding' })}
                                                                disabled={!!actionId}
                                                                className="w-full text-left text-xs px-3 py-2 hover:bg-emerald-50 text-emerald-700 flex items-center gap-2"
                                                            >
                                                                {actionId === biz.id + 'save-fixturegrounding' ? <Loader2 className="w-3 h-3 animate-spin" /> : <BookmarkPlus className="w-3 h-3" />}
                                                                Save as Grounding
                                                            </button>
                                                            <button
                                                                onClick={() => handleAction(biz, 'save-fixture', { fixtureType: 'failure_case' })}
                                                                disabled={!!actionId}
                                                                className="w-full text-left text-xs px-3 py-2 hover:bg-amber-50 text-amber-700 flex items-center gap-2"
                                                            >
                                                                {actionId === biz.id + 'save-fixturefailure_case' ? <Loader2 className="w-3 h-3 animate-spin" /> : <AlertTriangle className="w-3 h-3" />}
                                                                Save as Failure Case
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Channel-specific outreach buttons */}
                                            {channels.length > 0 && (
                                                <div className="flex gap-2">
                                                    {channels.map(ch => (
                                                        <button
                                                            key={ch}
                                                            onClick={() => handleAction(biz, 'outreach', { channel: ch })}
                                                            disabled={!!actionId}
                                                            className={`flex-1 text-xs py-2 rounded flex items-center justify-center gap-1.5 shadow-sm ${channelStyle(ch)}`}
                                                        >
                                                            {actionId === biz.id + 'outreach' + ch ? <Loader2 className="w-3 h-3 animate-spin" /> : channelIcon(ch)}
                                                            {channelLabel(ch)}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

function statusBadge(status?: DiscoveryStatus) {
    switch (status) {
        case 'scanned':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200">Scanned</span>;
        case 'discovering':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 border border-blue-200 flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" />Discovering</span>;
        case 'discovered':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">Discovered</span>;
        case 'analyzing':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-600 border border-amber-200 flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" />Analyzing</span>;
        case 'analyzed':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 border border-green-200">Analyzed</span>;
        case 'failed':
            return <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-600 border border-red-200">Failed</span>;
        default:
            return null;
    }
}

function channelIcon(ch: OutreachChannel) {
    switch (ch) {
        case 'email': return <Mail className="w-3 h-3" />;
        case 'instagram': return <Instagram className="w-3 h-3" />;
        case 'facebook': return <Facebook className="w-3 h-3" />;
    }
}

function channelLabel(ch: OutreachChannel) {
    switch (ch) {
        case 'email': return 'Email';
        case 'instagram': return 'Instagram';
        case 'facebook': return 'Facebook';
    }
}

function channelStyle(ch: OutreachChannel) {
    switch (ch) {
        case 'email': return 'bg-indigo-600 hover:bg-indigo-500 text-white';
        case 'instagram': return 'bg-purple-600 hover:bg-purple-500 text-white';
        case 'facebook': return 'bg-blue-600 hover:bg-blue-500 text-white';
    }
}
