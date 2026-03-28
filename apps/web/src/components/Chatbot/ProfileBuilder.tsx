"use client";

import React, { useState } from 'react';
import { Search, UtensilsCrossed, Users, Palette, Phone, Check, Pencil, X, Loader2 } from 'lucide-react';
import { BaseIdentity } from '@/types/api';
import { useApiClient } from '@/hooks/useApiClient';

type Section = 'menu' | 'social' | 'competitors' | 'theme' | 'contact';
type SectionStatus = 'idle' | 'discovering' | 'found' | 'confirmed' | 'editing';

interface SectionState {
    status: SectionStatus;
    data: Record<string, any> | null;
    editValue: string;
}

const SECTIONS: { id: Section; label: string; icon: React.ReactNode; description: string }[] = [
    { id: 'menu', label: 'Menu', icon: <UtensilsCrossed className="w-3.5 h-3.5" />, description: 'Find menu & delivery links' },
    { id: 'social', label: 'Social', icon: <Search className="w-3.5 h-3.5" />, description: 'Find social media profiles' },
    { id: 'competitors', label: 'Rivals', icon: <Users className="w-3.5 h-3.5" />, description: 'Discover nearby competitors' },
    { id: 'theme', label: 'Brand', icon: <Palette className="w-3.5 h-3.5" />, description: 'Detect logo & brand colors' },
    { id: 'contact', label: 'Contact', icon: <Phone className="w-3.5 h-3.5" />, description: 'Find email, phone & hours' },
];

function formatUrl(url: string): string {
    return url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');
}

function renderSectionData(section: Section, data: Record<string, any>): React.ReactNode {
    if (!data) return <span className="text-slate-500">Nothing found</span>;

    if (section === 'menu') {
        const links = [
            data.menuUrl && { label: 'Menu', url: data.menuUrl },
            data.grubhub && { label: 'Grubhub', url: data.grubhub },
            data.doordash && { label: 'DoorDash', url: data.doordash },
            data.ubereats && { label: 'UberEats', url: data.ubereats },
            data.seamless && { label: 'Seamless', url: data.seamless },
            data.toasttab && { label: 'Toast', url: data.toasttab },
        ].filter(Boolean) as { label: string; url: string }[];
        if (!links.length) return <span className="text-slate-500">No menu found</span>;
        return (
            <div className="space-y-1">
                {links.map(l => (
                    <div key={l.label} className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold text-slate-500 w-14 shrink-0">{l.label}</span>
                        <a href={l.url} target="_blank" rel="noreferrer" className="text-[11px] text-indigo-400 hover:text-indigo-300 truncate">{formatUrl(l.url)}</a>
                    </div>
                ))}
            </div>
        );
    }

    if (section === 'social') {
        const platforms = ['instagram', 'facebook', 'tiktok', 'yelp', 'twitter'].filter(k => data[k]);
        if (!platforms.length) return <span className="text-slate-500">None found</span>;
        return (
            <div className="space-y-1">
                {platforms.map(p => (
                    <div key={p} className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold text-slate-500 w-14 shrink-0 capitalize">{p}</span>
                        <a href={data[p]} target="_blank" rel="noreferrer" className="text-[11px] text-indigo-400 hover:text-indigo-300 truncate">{formatUrl(data[p])}</a>
                    </div>
                ))}
            </div>
        );
    }

    if (section === 'competitors') {
        const comps = data.competitors || (Array.isArray(data) ? data : []);
        if (!comps.length) return <span className="text-slate-500">None found</span>;
        return (
            <div className="space-y-1">
                {comps.slice(0, 5).map((c: any, i: number) => (
                    <div key={i} className="flex items-center gap-1.5">
                        <span className="text-[11px] font-semibold text-white">{c.name}</span>
                        {c.url && <a href={c.url} target="_blank" rel="noreferrer" className="text-[10px] text-indigo-400 hover:text-indigo-300 truncate">↗</a>}
                    </div>
                ))}
            </div>
        );
    }

    if (section === 'theme') {
        return (
            <div className="flex items-center gap-2 flex-wrap">
                {data.logoUrl && <span className="text-[10px] text-slate-400">Logo ✓</span>}
                {data.favicon && <img src={data.favicon} className="w-4 h-4 rounded" alt="favicon" />}
                {data.primaryColor && <span className="w-4 h-4 rounded-full border border-white/20" style={{ backgroundColor: data.primaryColor }} />}
                {data.secondaryColor && <span className="w-4 h-4 rounded-full border border-white/20" style={{ backgroundColor: data.secondaryColor }} />}
                {data.persona && <span className="text-[10px] text-indigo-300 bg-indigo-500/20 px-1.5 py-0.5 rounded">{data.persona}</span>}
                {!data.logoUrl && !data.primaryColor && !data.persona && <span className="text-slate-500 text-[10px]">No theme found</span>}
            </div>
        );
    }

    if (section === 'contact') {
        const items = [
            data.email && { label: 'Email', value: data.email },
            data.phone && { label: 'Phone', value: data.phone },
            data.hours && { label: 'Hours', value: typeof data.hours === 'string' ? data.hours : JSON.stringify(data.hours) },
            data.contactFormUrl && { label: 'Form', value: data.contactFormUrl },
        ].filter(Boolean) as { label: string; value: string }[];
        if (!items.length) return <span className="text-slate-500">No contact found</span>;
        return (
            <div className="space-y-1">
                {items.map(item => (
                    <div key={item.label} className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold text-slate-500 w-10 shrink-0">{item.label}</span>
                        <span className="text-[11px] text-slate-300 truncate">{item.value}</span>
                    </div>
                ))}
            </div>
        );
    }

    return <span className="text-[10px] text-slate-400 truncate">{JSON.stringify(data).slice(0, 80)}</span>;
}

interface ProfileBuilderProps {
    business: BaseIdentity;
}

export default function ProfileBuilder({ business }: ProfileBuilderProps) {
    const { apiFetch } = useApiClient();
    const [sections, setSections] = useState<Record<Section, SectionState>>(() => {
        const init: Record<string, SectionState> = {};
        SECTIONS.forEach(s => { init[s.id] = { status: 'idle', data: null, editValue: '' }; });
        return init as Record<Section, SectionState>;
    });

    const [error, setError] = useState<string | null>(null);

    const discover = async (sectionId: Section) => {
        setError(null);
        setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'discovering' } }));
        try {
            const res = await apiFetch('/api/profile/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section: sectionId,
                    identity: {
                        name: business.name,
                        address: business.address,
                        zipCode: (business as any).zipCode,
                        officialUrl: business.officialUrl,
                    },
                }),
            });
            if (res.ok) {
                const result = await res.json();
                setSections(prev => ({
                    ...prev,
                    [sectionId]: { status: 'found', data: result.data, editValue: '' },
                }));
            } else {
                const errText = await res.text().catch(() => res.statusText);
                console.error(`[ProfileBuilder] ${sectionId} failed: ${res.status}`, errText);
                setError(`${sectionId} discovery failed (${res.status})`);
                setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'idle' } }));
            }
        } catch (e) {
            console.error(`[ProfileBuilder] ${sectionId} error:`, e);
            setError(`${sectionId} discovery failed`);
            setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'idle' } }));
        }
    };

    const confirm = async (sectionId: Section) => {
        const s = sections[sectionId];
        if (!s.data) return;
        setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'confirmed' } }));
        try {
            await apiFetch('/api/profile/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section: sectionId,
                    identity: { name: business.name, address: business.address, zipCode: (business as any).zipCode },
                    data: s.data,
                }),
            });
        } catch { /* best-effort save */ }
    };

    const submitOverride = async (sectionId: Section) => {
        const s = sections[sectionId];
        if (!s.editValue.trim()) return;
        setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'discovering' } }));
        try {
            const res = await apiFetch('/api/profile/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section: sectionId,
                    identity: { name: business.name, address: business.address, zipCode: (business as any).zipCode },
                    override: s.editValue.trim(),
                }),
            });
            if (res.ok) {
                const result = await res.json();
                setSections(prev => ({
                    ...prev,
                    [sectionId]: { status: 'confirmed', data: result.data, editValue: '' },
                }));
                // Auto-confirm user overrides
                await apiFetch('/api/profile/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        section: sectionId,
                        identity: { name: business.name, address: business.address, zipCode: (business as any).zipCode },
                        data: result.data,
                    }),
                });
            }
        } catch {
            setSections(prev => ({ ...prev, [sectionId]: { ...prev[sectionId], status: 'idle', editValue: '' } }));
        }
    };

    return (
        <div className="p-3 space-y-2">
            <div className="flex items-center gap-1.5 mb-1">
                <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider">Build Profile</span>
            </div>
            {error && (
                <p className="text-[10px] text-red-400 bg-red-500/10 px-2 py-1 rounded">{error}</p>
            )}

            <div className="grid grid-cols-2 gap-1.5">
                {SECTIONS.map(({ id, label, icon, description }) => {
                    const s = sections[id];

                    // Discovering state
                    if (s.status === 'discovering') {
                        return (
                            <div key={id} className="col-span-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-500/10 border border-indigo-400/20">
                                <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                                <span className="text-xs text-indigo-300">Finding {label.toLowerCase()}...</span>
                            </div>
                        );
                    }

                    // Found — show result with confirm/edit/dismiss
                    if (s.status === 'found' && s.data) {
                        return (
                            <div key={id} className="col-span-2 px-3 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-400/20 space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold text-emerald-300">{label}</span>
                                    <div className="flex gap-1">
                                        <button onClick={() => confirm(id)} className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">
                                            <Check className="w-3 h-3" /> Confirm
                                        </button>
                                        <button onClick={() => setSections(prev => ({ ...prev, [id]: { ...prev[id], status: 'editing', editValue: '' } }))}
                                            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-white/5 text-slate-400 hover:bg-white/10">
                                            <Pencil className="w-3 h-3" /> Edit
                                        </button>
                                        <button onClick={() => setSections(prev => ({ ...prev, [id]: { status: 'idle', data: null, editValue: '' } }))}
                                            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-white/5 text-slate-400 hover:bg-white/10">
                                            <X className="w-3 h-3" />
                                        </button>
                                    </div>
                                </div>
                                <div className="text-[11px]">{renderSectionData(id, s.data)}</div>
                            </div>
                        );
                    }

                    // Confirmed state
                    if (s.status === 'confirmed') {
                        return (
                            <div key={id} className="col-span-1 flex items-center gap-2 px-2.5 py-2 rounded-lg bg-emerald-500/10 border border-emerald-400/15">
                                <Check className="w-3 h-3 text-emerald-400" />
                                <span className="text-[11px] font-semibold text-emerald-300 truncate">{label}</span>
                            </div>
                        );
                    }

                    // Editing — manual input
                    if (s.status === 'editing') {
                        return (
                            <div key={id} className="col-span-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 space-y-1.5">
                                <span className="text-xs font-bold text-slate-300">{label} — paste URL or details</span>
                                <div className="flex gap-1.5">
                                    <input
                                        type="text"
                                        value={s.editValue}
                                        onChange={e => setSections(prev => ({ ...prev, [id]: { ...prev[id], editValue: e.target.value } }))}
                                        placeholder={id === 'menu' ? 'Menu URL...' : id === 'social' ? 'Instagram URL...' : 'Enter details...'}
                                        className="flex-1 bg-black/30 border border-white/10 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-400/50"
                                        onKeyDown={e => e.key === 'Enter' && submitOverride(id)}
                                    />
                                    <button onClick={() => submitOverride(id)} className="px-2 py-1 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30">
                                        Save
                                    </button>
                                    <button onClick={() => setSections(prev => ({ ...prev, [id]: { status: 'idle', data: null, editValue: '' } }))}
                                        className="px-2 py-1 rounded text-[10px] font-bold bg-white/5 text-slate-400 hover:bg-white/10">
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>
                        );
                    }

                    // Idle — action button
                    return (
                        <button
                            key={id}
                            onClick={() => discover(id)}
                            className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/5 border border-white/8 hover:bg-indigo-500/10 hover:border-indigo-400/20 transition-all text-left group"
                        >
                            <div className="w-6 h-6 rounded-md bg-indigo-500/15 flex items-center justify-center text-indigo-400 group-hover:bg-indigo-500/25 transition-colors shrink-0">
                                {icon}
                            </div>
                            <div className="min-w-0">
                                <p className="text-[11px] font-bold text-slate-300 leading-tight">{label}</p>
                                <p className="text-[9px] text-slate-500 leading-tight truncate">{description}</p>
                            </div>
                        </button>
                    );
                })}
            </div>

            {/* Manual input shortcut */}
            <button
                onClick={() => {
                    // Toggle the first idle section to editing mode
                    const firstIdle = SECTIONS.find(s => sections[s.id].status === 'idle');
                    if (firstIdle) {
                        setSections(prev => ({ ...prev, [firstIdle.id]: { ...prev[firstIdle.id], status: 'editing' } }));
                    }
                }}
                className="w-full text-center text-[10px] text-slate-500 hover:text-indigo-400 transition-colors py-1"
            >
                Or paste details manually
            </button>
        </div>
    );
}
