'use client';

import { useState, useEffect, useCallback, type ReactNode } from 'react';
import {
    Search, BarChart3, Loader2, ChevronDown, ChevronUp,
    Phone, Mail, Globe, Clock, MapPin, Instagram,
    Star, Users, TrendingUp, Zap, Trash2, RefreshCw,
    BookmarkPlus, TestTube2, MoreVertical, CheckCircle2,
    Tag, X, Send, CheckSquare, Square, ChevronRight,
    BadgeCheck, FlaskConical, AlertCircle, Filter,
    ChevronLeft, UserCheck, Target, ExternalLink,
} from 'lucide-react';

type DiscoveryStatus = 'scanned' | 'discovering' | 'discovered' | 'analyzing' | 'analyzed' | 'failed';

interface SocialLinks {
    instagram?: string | null;
    facebook?: string | null;
    twitter?: string | null;
    yelp?: string | null;
    tiktok?: string | null;
    grubhub?: string | null;
    doordash?: string | null;
    ubereats?: string | null;
}

interface ReviewerOutput {
    outreach_score: number;
    best_channel: string;
    primary_reason: string;
    strengths: string[];
    concerns: string[];
}

interface Business {
    id: string;
    name: string;
    address?: string;
    zipCode: string;
    category?: string;
    website?: string;
    discoveryStatus?: DiscoveryStatus;
    phone?: string;
    email?: string;
    emailStatus?: string;
    contactFormUrl?: string;
    contactFormStatus?: string;
    hours?: string;
    googleMapsUrl?: string;
    logoUrl?: string;
    primaryColor?: string;
    socialLinks?: SocialLinks;
    competitors?: { name: string; url: string; reason: string }[];
    insights?: { summary: string; keyFindings: string[]; recommendations: string[] };
    identity?: Record<string, any>;
    latestOutputs?: Record<string, any>;
    outreachContent?: {
        generatedAt?: string;
        instagram?: { original?: string; edited?: string; savedAt?: string };
        facebook?: { original?: string; edited?: string; savedAt?: string };
        twitter?: { original?: string; edited?: string; savedAt?: string };
        email?: { subject?: string; editedSubject?: string; original?: string; edited?: string; savedAt?: string };
        contactForm?: { original?: string; edited?: string; savedAt?: string };
    };
    crm?: { status: string; outreachCount: number };
}

interface PaginatedResponse {
    businesses: Business[];
    total: number;
    page: number;
    pages: number;
    pageSize: number;
}

interface BusinessBrowserProps { zipCode: string; }

// ── Agents config ─────────────────────────────────────────────────────────────
const AGENTS = [
    { name: 'seo',            label: 'SEO Audit',            outputKey: 'seo_auditor',          color: 'emerald', icon: '🔍' },
    { name: 'traffic',        label: 'Foot Traffic',         outputKey: 'traffic_forecaster',   color: 'blue',    icon: '📈' },
    { name: 'competitive',    label: 'Competitive',          outputKey: 'competitive_analyzer',  color: 'red',     icon: '⚔️'  },
    { name: 'margin_surgeon', label: 'Margin Surgery',       outputKey: 'margin_surgeon',        color: 'amber',   icon: '💰' },
    { name: 'social',         label: 'Social Media',         outputKey: 'social_media_auditor',  color: 'purple',  icon: '📱' },
] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusBadge(status?: DiscoveryStatus) {
    switch (status) {
        case 'scanned':     return <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 border border-gray-200">Scanned</span>;
        case 'discovering': return <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-600 border border-blue-200 flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" />Discovering</span>;
        case 'discovered':  return <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 border border-emerald-200">Discovered</span>;
        case 'analyzing':   return <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-600 border border-violet-200 flex items-center gap-1"><Loader2 className="w-2.5 h-2.5 animate-spin" />Analyzing</span>;
        case 'analyzed':    return <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-200">Analyzed</span>;
        case 'failed':      return <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-600 border border-red-200">Failed</span>;
        default:            return null;
    }
}

function ScoreBar({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' }) {
    const pct = Math.min(100, Math.max(0, score));
    const color = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500';
    const h = size === 'sm' ? 'h-1.5' : 'h-2';
    return (
        <div className="flex items-center gap-2">
            <div className={`flex-1 ${h} bg-gray-100 rounded-full overflow-hidden`}>
                <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
            </div>
            <span className={`font-bold text-gray-800 w-8 text-right ${size === 'sm' ? 'text-xs' : 'text-sm'}`}>{score}</span>
        </div>
    );
}

function ReviewerBadge({ reviewer }: { reviewer: ReviewerOutput }) {
    const score = reviewer.outreach_score;
    const color = score >= 8 ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
        : score >= 5 ? 'bg-amber-100 text-amber-700 border-amber-200'
        : 'bg-red-100 text-red-600 border-red-200';
    const icon = score >= 8 ? <CheckCircle2 className="w-3 h-3" /> : score >= 5 ? <Target className="w-3 h-3" /> : <X className="w-3 h-3" />;
    return (
        <span title={reviewer.primary_reason}
            className={`text-[10px] px-1.5 py-0.5 rounded border flex items-center gap-0.5 font-semibold ${color}`}>
            {icon}{score}/10
        </span>
    );
}

// ── Content Studio Modal ──────────────────────────────────────────────────────────
type ContentChannel = 'instagram' | 'facebook' | 'twitter' | 'email' | 'contactForm';
const CHANNELS: Record<ContentChannel, { label: string; charLimit: number | null }> = {
    instagram: { label: 'Instagram', charLimit: 2200 },
    facebook: { label: 'Facebook', charLimit: null },
    twitter: { label: 'Twitter / X', charLimit: 280 },
    email: { label: 'Email', charLimit: null },
    contactForm: { label: 'Contact Form', charLimit: null },
};

function ContentStudioModal({ biz, onClose, onSend }: {
    biz: Business;
    onClose: () => void;
    onSend: (channel: string) => Promise<void>;
}) {
    const [activeTab, setActiveTab] = useState<ContentChannel>('instagram');
    const [contents, setContents] = useState<Record<ContentChannel, string>>({
        instagram: biz.outreachContent?.instagram?.edited || biz.outreachContent?.instagram?.original || '',
        facebook: biz.outreachContent?.facebook?.edited || biz.outreachContent?.facebook?.original || '',
        twitter: biz.outreachContent?.twitter?.edited || biz.outreachContent?.twitter?.original || '',
        email: biz.outreachContent?.email?.edited || biz.outreachContent?.email?.original || '',
        contactForm: biz.outreachContent?.contactForm?.edited || biz.outreachContent?.contactForm?.original || '',
    });
    const [emailSubject, setEmailSubject] = useState(biz.outreachContent?.email?.editedSubject || biz.outreachContent?.email?.subject || '');
    const [generating, setGenerating] = useState(false);
    const [saving, setSaving] = useState<ContentChannel | null>(null);
    const [saved, setSaved] = useState<Record<ContentChannel, boolean>>({ instagram: false, facebook: false, twitter: false, email: false, contactForm: false });

    const callAction = async (body: Record<string, unknown>): Promise<any | null> => {
        const res = await fetch('/api/research/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) { console.error('Action failed:', await res.json().catch(() => ({}))); return null; }
        return res.json();
    };

    const handleGenerate = async () => {
        setGenerating(true);
        const res = await callAction({ action: 'generate-outreach-content', businessId: biz.id });
        if (res?.content) {
            const c = res.content;
            setContents({
                instagram: c.instagram?.caption || '',
                facebook: c.facebook?.post || '',
                twitter: c.twitter?.tweet || '',
                email: c.email?.body || '',
                contactForm: c.contactForm?.message || '',
            });
            setEmailSubject(c.email?.subject || '');
        }
        setGenerating(false);
    };

    const handleSave = async (channel: ContentChannel) => {
        setSaving(channel);
        await callAction({
            action: 'save-outreach-draft',
            businessId: biz.id,
            channel,
            editedContent: contents[channel] || '',
            ...(channel === 'email' ? { emailSubject } : {}),
        });
        setSaving(null);
        setSaved(prev => ({ ...prev, [channel]: true }));
        setTimeout(() => setSaved(prev => ({ ...prev, [channel]: false })), 2500);
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
    };

    const getPlatformActionButton = (channel: ContentChannel) => {
        const content = contents[channel] || '';
        if (channel === 'twitter' && content) {
            const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(content)}`;
            return (
                <a href={tweetUrl} target="_blank" rel="noreferrer"
                    className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1">
                    <span>𝕏</span> Post to X
                </a>
            );
        } else if (channel === 'email' && biz.email) {
            return (
                <button onClick={() => onSend('email')}
                    className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition-colors">
                    Send via Resend
                </button>
            );
        } else if (channel === 'contactForm' && biz.contactFormUrl) {
            return (
                <a href={biz.contactFormUrl} target="_blank" rel="noreferrer"
                    className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-1">
                    <ExternalLink className="w-3 h-3" /> Open Form
                </a>
            );
        } else if (channel === 'instagram') {
            return (
                <a href="https://www.instagram.com/" target="_blank" rel="noreferrer"
                    className="px-3 py-1.5 bg-pink-600 text-white text-xs rounded-lg hover:bg-pink-700 transition-colors">
                    Open Instagram
                </a>
            );
        } else if (channel === 'facebook') {
            return (
                <a href="https://www.facebook.com/" target="_blank" rel="noreferrer"
                    className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 transition-colors">
                    Open Facebook
                </a>
            );
        }
        return null;
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900">📣 Content Studio</h2>
                        <p className="text-sm text-gray-500">{biz.name}</p>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
                </div>

                <div className="p-4">
                    <button onClick={handleGenerate} disabled={generating}
                        className="mb-4 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2">
                        {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Zap className="w-4 h-4" /> Generate Content</>}
                    </button>

                    {/* Tab bar */}
                    <div className="flex gap-1 border-b border-gray-200 mb-4 overflow-x-auto">
                        {(Object.keys(CHANNELS) as ContentChannel[]).map(ch => (
                            <button key={ch} onClick={() => setActiveTab(ch)}
                                className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                    activeTab === ch ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-600 hover:text-gray-800'
                                }`}>
                                {CHANNELS[ch].label}
                            </button>
                        ))}
                    </div>

                    {/* Content editor */}
                    <div className="space-y-3">
                        {activeTab === 'email' && (
                            <>
                                <div>
                                    <label className="text-xs font-semibold text-gray-600 block mb-1">Subject</label>
                                    <input value={emailSubject} onChange={e => setEmailSubject(e.target.value)}
                                        placeholder="Email subject line"
                                        className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                                </div>
                            </>
                        )}
                        <div className="relative">
                            <label className="text-xs font-semibold text-gray-600 block mb-1">Content</label>
                            <textarea value={contents[activeTab]} onChange={e => setContents(prev => ({ ...prev, [activeTab]: e.target.value }))}
                                rows={activeTab === 'twitter' ? 4 : 8}
                                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                            />
                            {CHANNELS[activeTab].charLimit && (
                                <div className={`absolute bottom-3 right-3 text-xs font-medium ${
                                    contents[activeTab].length > CHANNELS[activeTab].charLimit! ? 'text-red-500' : 'text-gray-400'
                                }`}>
                                    {contents[activeTab].length}/{CHANNELS[activeTab].charLimit}
                                </div>
                            )}
                        </div>

                        {/* Action buttons */}
                        <div className="flex flex-wrap gap-2 pt-2">
                            <button onClick={() => handleSave(activeTab)} disabled={saving === activeTab}
                                className="px-3 py-1.5 bg-emerald-600 text-white text-xs rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1">
                                {saving === activeTab ? <Loader2 className="w-3 h-3 animate-spin" /> : saved[activeTab] ? <CheckCircle2 className="w-3 h-3" /> : null}
                                {saved[activeTab] ? 'Saved!' : 'Save Draft'}
                            </button>
                            <button onClick={() => copyToClipboard(contents[activeTab])}
                                className="px-3 py-1.5 bg-gray-200 text-gray-700 text-xs rounded-lg hover:bg-gray-300">
                                Copy
                            </button>
                            {getPlatformActionButton(activeTab)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ── Section save + action buttons ─────────────────────────────────────────────
interface SaveState { grounding: boolean; test_case: boolean; }

function SectionActions({ bizId, sectionKey, savedState, onSave, onOutreach, onDelete }: {
    bizId: string; sectionKey: string; savedState: SaveState;
    onSave: (type: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void;
    onDelete?: () => Promise<void>;
}) {
    const [busy, setBusy] = useState<string | null>(null);
    const handle = async (type: string) => {
        setBusy(type);
        try {
            if (type === 'outreach') onOutreach();
            else if (type === 'delete' && onDelete) await onDelete();
            else await onSave(type as 'grounding' | 'test_case');
        } finally { setBusy(null); }
    };
    return (
        <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-gray-100">
            <button onClick={() => handle('grounding')} disabled={!!busy}
                className={`text-[11px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors disabled:opacity-50 ${savedState.grounding ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'}`}>
                {busy === 'grounding' ? <Loader2 className="w-3 h-3 animate-spin" /> : savedState.grounding ? <BadgeCheck className="w-3 h-3" /> : <BookmarkPlus className="w-3 h-3" />}
                {savedState.grounding ? 'Saved as Grounding' : 'Save as Grounding'}
            </button>
            <button onClick={() => handle('test_case')} disabled={!!busy}
                className={`text-[11px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors disabled:opacity-50 ${savedState.test_case ? 'bg-violet-600 text-white border-violet-600' : 'bg-violet-50 text-violet-700 border-violet-200 hover:bg-violet-100'}`}>
                {busy === 'test_case' ? <Loader2 className="w-3 h-3 animate-spin" /> : savedState.test_case ? <FlaskConical className="w-3 h-3" /> : <TestTube2 className="w-3 h-3" />}
                {savedState.test_case ? 'Saved as Test Case' : 'Save as Test Case'}
            </button>
            <button onClick={() => handle('outreach')} disabled={!!busy}
                className="text-[11px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 disabled:opacity-50">
                {busy === 'outreach' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                Send Outreach
            </button>
            {onDelete && (
                <button onClick={() => handle('delete')} disabled={!!busy}
                    className="ml-auto text-[11px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 disabled:opacity-50">
                    {busy === 'delete' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                    Delete Results
                </button>
            )}
        </div>
    );
}

// ── Discovery panel ───────────────────────────────────────────────────────────
function DiscoveryPanel({ biz, savedState, onSave, onOutreach }: {
    biz: Business; savedState: SaveState;
    onSave: (type: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void;
}) {
    const id = biz.identity ?? {};
    const phone = biz.phone || id.phone;
    const email = biz.email || id.email;
    const emailStatus = biz.emailStatus || id.emailStatus;
    const contactFormUrl = biz.contactFormUrl || id.contactFormUrl;
    const contactFormStatus = biz.contactFormStatus || id.contactFormStatus;
    const hours = biz.hours || id.hours;
    const mapsUrl = biz.googleMapsUrl || id.googleMapsUrl;
    const officialUrl = biz.website || id.officialUrl;
    const social = biz.socialLinks || id.socialLinks;
    const ai = id.aiOverview;
    const metrics = id.socialProfileMetrics?.summary;
    const competitors = biz.competitors || id.competitors;
    const menuUrl = id.menuUrl;
    const persona = id.persona;
    const news = id.news;

    if (!phone && !email && !hours && !mapsUrl && !officialUrl && !social && !ai && !competitors) {
        return (
            <div className="py-10 text-center text-gray-400 text-sm">
                <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
                No discovery data yet. Click <strong>Discover</strong> to enrich this business profile.
            </div>
        );
    }

    return (
        <div className="space-y-5">
            {(phone || email || hours || officialUrl || mapsUrl || menuUrl || contactFormUrl) && (
                <section>
                    <h5 className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2 pb-1 border-b border-blue-100">Contact & Location</h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        {phone && <div className="flex items-center gap-2 text-gray-700"><Phone className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />{phone}</div>}
                        {email ? (
                            <div className="flex items-center gap-2 text-gray-700">
                                <Mail className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                                <span>{email}</span>
                                {emailStatus === 'extraction_failed' && (
                                    <span title="Email may exist but couldn't be extracted — check manually" className="inline-block w-4 h-4 bg-amber-100 text-amber-700 rounded-full text-[10px] font-bold flex items-center justify-center flex-shrink-0">!</span>
                                )}
                            </div>
                        ) : emailStatus === 'not_found' ? (
                            <div className="text-gray-400 text-xs">No email found</div>
                        ) : emailStatus === 'extraction_failed' ? (
                            <div className="flex items-center gap-2 text-amber-700">
                                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                <span className="text-xs">Email extraction failed — check manually</span>
                            </div>
                        ) : null}
                        {hours && <div className="flex items-center gap-2 text-gray-700"><Clock className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />{typeof hours === 'string' ? hours : JSON.stringify(hours)}</div>}
                        {officialUrl && <a href={officialUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline truncate"><Globe className="w-3.5 h-3.5 flex-shrink-0" />{officialUrl}</a>}
                        {mapsUrl && <a href={mapsUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline"><MapPin className="w-3.5 h-3.5 flex-shrink-0" />View on Maps</a>}
                        {menuUrl && <a href={menuUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline"><Globe className="w-3.5 h-3.5 flex-shrink-0" />View Menu</a>}
                        {contactFormUrl ? (
                            <a href={contactFormUrl} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-blue-600 hover:underline">
                                <Mail className="w-3.5 h-3.5 flex-shrink-0" />
                                <span>Contact Form</span>
                                {contactFormStatus === 'extraction_failed' && (
                                    <span title="Contact form found but URL extraction failed — check manually" className="inline-block w-4 h-4 bg-amber-100 text-amber-700 rounded-full text-[10px] font-bold flex items-center justify-center flex-shrink-0">!</span>
                                )}
                            </a>
                        ) : contactFormStatus === 'not_found' ? (
                            <div className="text-gray-400 text-xs">No contact form</div>
                        ) : contactFormStatus === 'extraction_failed' ? (
                            <div className="flex items-center gap-2 text-amber-700">
                                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                <span className="text-xs">Contact form extraction failed — check manually</span>
                            </div>
                        ) : null}
                    </div>
                </section>
            )}

            {social && Object.entries(social).some(([, v]) => v) && (
                <section>
                    <h5 className="text-xs font-semibold text-purple-600 uppercase tracking-wider mb-2 pb-1 border-b border-purple-100">Social Presence</h5>
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(social).map(([platform, url]) => url && typeof url === 'string' ? (
                            <a key={platform} href={url} target="_blank" rel="noreferrer"
                                className="text-[11px] px-2 py-1 rounded bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 capitalize">
                                {platform}
                            </a>
                        ) : null)}
                    </div>
                    {metrics && (
                        <div className="mt-2 p-2 bg-gray-50 rounded-lg text-xs text-gray-600 flex flex-wrap gap-3">
                            {metrics.totalFollowers !== undefined && <span>Followers: <strong>{metrics.totalFollowers.toLocaleString()}</strong></span>}
                            {metrics.overallPresenceScore !== undefined && <span>Presence Score: <strong>{metrics.overallPresenceScore}/100</strong></span>}
                            {metrics.recommendation && <span className="text-gray-500 italic">{metrics.recommendation}</span>}
                        </div>
                    )}
                </section>
            )}

            {ai && (
                <section>
                    <h5 className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-2 pb-1 border-b border-amber-100">AI Business Overview</h5>
                    {ai.summary && <p className="text-sm text-gray-700 leading-relaxed mb-2">{ai.summary}</p>}
                    {ai.highlights?.length > 0 && (
                        <ul className="space-y-1 mb-2">
                            {ai.highlights.map((h: string, i: number) => <li key={i} className="text-xs text-gray-600 flex items-start gap-1.5"><span className="text-amber-500 mt-0.5">•</span>{h}</li>)}
                        </ul>
                    )}
                    <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                        {ai.business_type && <span>Type: <span className="font-medium text-gray-700">{ai.business_type}</span></span>}
                        {ai.price_range && <span>Price: <span className="font-medium text-gray-700">{ai.price_range}</span></span>}
                        {ai.reputation_signals && <span>Reputation: <span className="font-medium capitalize text-gray-700">{ai.reputation_signals}</span></span>}
                    </div>
                </section>
            )}

            {persona && (
                <section>
                    <h5 className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-2 pb-1 border-b border-indigo-100">Business Persona</h5>
                    <p className="text-sm text-gray-700 leading-relaxed">{persona}</p>
                </section>
            )}

            {competitors?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-2 pb-1 border-b border-red-100">Local Competitors ({competitors.length})</h5>
                    <div className="space-y-2">
                        {competitors.map((c: any, i: number) => (
                            <div key={i} className="p-2.5 bg-red-50 rounded-lg border border-red-100">
                                <a href={c.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-red-700 hover:underline">{c.name}</a>
                                {c.reason && <p className="text-xs text-gray-600 mt-0.5">{c.reason}</p>}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {news?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 pb-1 border-b border-gray-100">Recent News & Mentions</h5>
                    <div className="space-y-1.5">
                        {news.map((n: any, i: number) => (
                            <div key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                                <ChevronRight className="w-3 h-3 text-gray-400 mt-0.5 flex-shrink-0" />
                                {typeof n === 'string' ? n : (n.title || JSON.stringify(n))}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            <SectionActions bizId={biz.id} sectionKey="discovery" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} />
        </div>
    );
}

// ── Agent-specific rich output panels ─────────────────────────────────────────

function SectionScoreCard({ name, score, findings, recommendations }: {
    name: string; score?: number;
    findings?: string[]; recommendations?: string[];
}) {
    const [open, setOpen] = useState(false);
    return (
        <div className="border border-gray-100 rounded-lg overflow-hidden">
            <button onClick={() => setOpen(o => !o)}
                className="w-full flex items-center gap-3 px-3 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left">
                <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-700 capitalize">{name.replace(/_/g, ' ')}</p>
                    {score != null && <ScoreBar score={score} size="sm" />}
                </div>
                {open ? <ChevronUp className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />}
            </button>
            {open && (findings?.length || recommendations?.length) ? (
                <div className="px-3 py-3 space-y-3">
                    {findings?.length ? (
                        <div>
                            <p className="text-[10px] font-semibold text-red-500 uppercase tracking-wide mb-1.5">Findings</p>
                            <ul className="space-y-1">
                                {findings.map((f, i) => <li key={i} className="text-xs text-gray-700 flex items-start gap-1.5"><AlertCircle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />{f}</li>)}
                            </ul>
                        </div>
                    ) : null}
                    {recommendations?.length ? (
                        <div>
                            <p className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wide mb-1.5">Recommendations</p>
                            <ul className="space-y-1">
                                {recommendations.map((r, i) => <li key={i} className="text-xs text-gray-700 flex items-start gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 flex-shrink-0" />{r}</li>)}
                            </ul>
                        </div>
                    ) : null}
                </div>
            ) : null}
        </div>
    );
}

function SeoOutputPanel({ output, savedState, onSave, onOutreach, onDelete }: {
    output: Record<string, any>; savedState: SaveState;
    onSave: (t: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void; onDelete: () => Promise<void>;
}) {
    const score = output.score ?? output.overall_score ?? output.overallScore;
    const sections: any[] = output.sections || [];
    const issues = output.critical_issues || output.issues || [];
    const quickWins = output.quick_wins || [];

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                {score != null && (
                    <div className="mb-3">
                        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                            <span className="font-semibold text-gray-700">SEO Audit Score</span>
                            <span className="font-bold text-lg text-gray-800">{score}<span className="text-xs text-gray-400">/100</span></span>
                        </div>
                        <ScoreBar score={score} />
                    </div>
                )}
                {output.summary && <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.summary}</p>}
                {output.runAt && <p className="text-[10px] text-gray-400 mt-2">Run at {new Date(output.runAt).toLocaleString()} · v{output.agentVersion}</p>}
            </div>

            {sections.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Section Breakdown</h5>
                    <div className="space-y-1.5">
                        {sections.map((s: any, i: number) => (
                            <SectionScoreCard key={i}
                                name={s.name || s.section || `Section ${i + 1}`}
                                score={s.score}
                                findings={s.findings || s.issues}
                                recommendations={s.recommendations} />
                        ))}
                    </div>
                </section>
            )}

            {issues.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-2">Critical Issues</h5>
                    <ul className="space-y-1.5">
                        {issues.map((iss: string, i: number) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-red-50 rounded-lg border border-red-100">
                                <AlertCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />{iss}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {quickWins.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Quick Wins</h5>
                    <ul className="space-y-1.5">
                        {quickWins.map((w: string, i: number) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-emerald-50 rounded-lg border border-emerald-100">
                                <Zap className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />{w}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <SectionActions bizId="" sectionKey="seo_auditor" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} onDelete={onDelete} />
        </div>
    );
}

function CompetitiveOutputPanel({ output, savedState, onSave, onOutreach, onDelete }: {
    output: Record<string, any>; savedState: SaveState;
    onSave: (t: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void; onDelete: () => Promise<void>;
}) {
    const score = output.score ?? output.overall_score ?? output.overallScore;
    const competitors: any[] = output.competitors || [];
    const advantages: string[] = output.competitive_advantages || output.advantages || [];
    const disadvantages: string[] = output.competitive_disadvantages || output.disadvantages || [];
    const positioning = output.market_positioning || output.positioning;

    const threatColor = (level: string | number) => {
        const l = typeof level === 'string' ? level.toLowerCase() : '';
        if (l === 'high' || Number(level) >= 7) return 'bg-red-100 text-red-700 border-red-200';
        if (l === 'medium' || Number(level) >= 4) return 'bg-amber-100 text-amber-700 border-amber-200';
        return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    };

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                {score != null && (
                    <div className="mb-3">
                        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                            <span className="font-semibold text-gray-700">Competitive Position</span>
                            <span className="font-bold text-lg text-gray-800">{score}<span className="text-xs text-gray-400">/100</span></span>
                        </div>
                        <ScoreBar score={score} />
                    </div>
                )}
                <div className="flex flex-wrap gap-3 text-xs mt-2">
                    {output.avg_threat_level != null && <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded border border-red-100">Avg Threat: <strong>{output.avg_threat_level}</strong></span>}
                    {output.competitor_count != null && <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded border border-red-100">Competitors: <strong>{output.competitor_count}</strong></span>}
                </div>
                {output.summary && <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.summary}</p>}
                {positioning && typeof positioning === 'string' && <p className="text-xs text-gray-500 mt-2 italic">{positioning}</p>}
                {output.runAt && <p className="text-[10px] text-gray-400 mt-2">Run at {new Date(output.runAt).toLocaleString()} · v{output.agentVersion}</p>}
            </div>

            {competitors.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-2">Competitor Profiles ({competitors.length})</h5>
                    <div className="space-y-2">
                        {competitors.map((c: any, i: number) => (
                            <div key={i} className="p-3 bg-white border border-gray-200 rounded-xl">
                                <div className="flex items-start justify-between gap-2 mb-2">
                                    <div className="min-w-0">
                                        {c.url ? (
                                            <a href={c.url} target="_blank" rel="noreferrer" className="font-semibold text-sm text-gray-900 hover:text-indigo-600">{c.name}</a>
                                        ) : (
                                            <p className="font-semibold text-sm text-gray-900">{c.name}</p>
                                        )}
                                        {c.address && <p className="text-xs text-gray-500 truncate">{c.address}</p>}
                                    </div>
                                    {c.threat_level && (
                                        <span className={`text-[10px] px-2 py-0.5 rounded border flex-shrink-0 font-semibold capitalize ${threatColor(c.threat_level)}`}>
                                            {c.threat_level} threat
                                        </span>
                                    )}
                                </div>
                                {c.analysis && <p className="text-xs text-gray-600 mb-2">{c.analysis}</p>}
                                {c.strengths?.length > 0 && (
                                    <div className="text-xs text-emerald-700 mb-1">
                                        <span className="font-medium">Strengths: </span>{Array.isArray(c.strengths) ? c.strengths.join(', ') : c.strengths}
                                    </div>
                                )}
                                {c.weaknesses?.length > 0 && (
                                    <div className="text-xs text-red-600">
                                        <span className="font-medium">Weaknesses: </span>{Array.isArray(c.weaknesses) ? c.weaknesses.join(', ') : c.weaknesses}
                                    </div>
                                )}
                                {c.opportunity && <p className="text-xs text-indigo-700 mt-1"><span className="font-medium">Opportunity: </span>{c.opportunity}</p>}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {(advantages.length > 0 || disadvantages.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {advantages.length > 0 && (
                        <section>
                            <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Advantages</h5>
                            <ul className="space-y-1">
                                {advantages.map((a, i) => <li key={i} className="text-xs text-gray-700 flex items-start gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 flex-shrink-0" />{a}</li>)}
                            </ul>
                        </section>
                    )}
                    {disadvantages.length > 0 && (
                        <section>
                            <h5 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-2">Disadvantages</h5>
                            <ul className="space-y-1">
                                {disadvantages.map((d, i) => <li key={i} className="text-xs text-gray-700 flex items-start gap-1.5"><X className="w-3 h-3 text-red-500 mt-0.5 flex-shrink-0" />{d}</li>)}
                            </ul>
                        </section>
                    )}
                </div>
            )}

            <SectionActions bizId="" sectionKey="competitive_analyzer" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} onDelete={onDelete} />
        </div>
    );
}

function MarginOutputPanel({ output, savedState, onSave, onOutreach, onDelete }: {
    output: Record<string, any>; savedState: SaveState;
    onSave: (t: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void; onDelete: () => Promise<void>;
}) {
    const score = output.score ?? output.overall_score ?? output.overallScore;
    const items: any[] = output.menu_items || output.items || [];
    const quickWins: string[] = output.quick_wins || output.recommendations || [];
    const totalLeakage = output.total_leakage;

    const actionColor = (action: string = '') => {
        const a = action.toLowerCase();
        if (a.includes('raise') || a.includes('increase')) return 'text-emerald-700 bg-emerald-50';
        if (a.includes('remove') || a.includes('cut') || a.includes('eliminate')) return 'text-red-700 bg-red-50';
        return 'text-amber-700 bg-amber-50';
    };

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                {score != null && (
                    <div className="mb-3">
                        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                            <span className="font-semibold text-gray-700">Margin Health Score</span>
                            <span className="font-bold text-lg text-gray-800">{score}<span className="text-xs text-gray-400">/100</span></span>
                        </div>
                        <ScoreBar score={score} />
                    </div>
                )}
                <div className="flex flex-wrap gap-3 text-xs mt-2">
                    {totalLeakage != null && <span className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded border border-amber-100 font-medium">Total Leakage: ${Number(totalLeakage).toLocaleString()}/mo</span>}
                    {output.menu_item_count != null && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded border border-gray-200">Items: {output.menu_item_count}</span>}
                </div>
                {output.summary && <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.summary}</p>}
                {output.runAt && <p className="text-[10px] text-gray-400 mt-2">Run at {new Date(output.runAt).toLocaleString()} · v{output.agentVersion}</p>}
            </div>

            {items.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-2">Menu Item Analysis ({items.length})</h5>
                    <div className="overflow-x-auto rounded-xl border border-gray-200">
                        <table className="w-full text-xs">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="text-left px-3 py-2 font-semibold text-gray-600">Item</th>
                                    <th className="text-right px-3 py-2 font-semibold text-gray-600">Current</th>
                                    <th className="text-right px-3 py-2 font-semibold text-gray-600">Suggested</th>
                                    <th className="text-left px-3 py-2 font-semibold text-gray-600">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {items.map((item: any, i: number) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                        <td className="px-3 py-2 font-medium text-gray-800">{item.name || item.item}</td>
                                        <td className="px-3 py-2 text-right text-gray-600">{item.current_price != null ? `$${item.current_price}` : '—'}</td>
                                        <td className="px-3 py-2 text-right font-semibold text-emerald-700">{item.recommended_price != null ? `$${item.recommended_price}` : '—'}</td>
                                        <td className="px-3 py-2">
                                            {item.action && (
                                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${actionColor(item.action)}`}>
                                                    {item.action}
                                                </span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}

            {quickWins.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Quick Wins</h5>
                    <ul className="space-y-1.5">
                        {quickWins.map((w: string, i: number) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-emerald-50 rounded-lg border border-emerald-100">
                                <Zap className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />{w}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <SectionActions bizId="" sectionKey="margin_surgeon" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} onDelete={onDelete} />
        </div>
    );
}

function SocialMediaOutputPanel({ output, savedState, onSave, onOutreach, onDelete }: {
    output: Record<string, any>; savedState: SaveState;
    onSave: (t: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void; onDelete: () => Promise<void>;
}) {
    const score = output.score ?? output.overall_score ?? output.overallScore;
    const platforms: any[] = output.platforms || [];
    const strategy = output.content_strategy || output.strategy;
    const recommendations: string[] = output.recommendations || [];

    const platformIcon = (name: string) => {
        const n = name.toLowerCase();
        if (n.includes('instagram')) return '📸';
        if (n.includes('facebook')) return '👍';
        if (n.includes('twitter') || n.includes('x')) return '𝕏';
        if (n.includes('tiktok')) return '🎵';
        if (n.includes('yelp')) return '⭐';
        return '🌐';
    };

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                {score != null && (
                    <div className="mb-3">
                        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                            <span className="font-semibold text-gray-700">Social Media Score</span>
                            <span className="font-bold text-lg text-gray-800">{score}<span className="text-xs text-gray-400">/100</span></span>
                        </div>
                        <ScoreBar score={score} />
                    </div>
                )}
                <div className="flex flex-wrap gap-2 text-xs mt-2">
                    {output.platform_count != null && <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded border border-purple-100">Platforms: {output.platform_count}</span>}
                </div>
                {output.summary && <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.summary}</p>}
                {output.runAt && <p className="text-[10px] text-gray-400 mt-2">Run at {new Date(output.runAt).toLocaleString()} · v{output.agentVersion}</p>}
            </div>

            {platforms.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-purple-600 uppercase tracking-wider mb-2">Platform Analysis</h5>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {platforms.map((p: any, i: number) => {
                            const platformName = p.platform || p.name || `Platform ${i + 1}`;
                            const pScore = p.score ?? p.quality_score;
                            return (
                                <div key={i} className="p-3 bg-white border border-purple-100 rounded-xl">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <span className="text-lg">{platformIcon(platformName)}</span>
                                            <p className="text-sm font-semibold text-gray-800 capitalize">{platformName}</p>
                                        </div>
                                        {pScore != null && (
                                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${pScore >= 70 ? 'bg-emerald-100 text-emerald-700' : pScore >= 40 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                                                {pScore}/100
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-gray-500 space-y-0.5">
                                        {p.followers != null && <p>Followers: <span className="font-medium text-gray-700">{Number(p.followers).toLocaleString()}</span></p>}
                                        {p.engagement_rate != null && <p>Engagement: <span className="font-medium text-gray-700">{p.engagement_rate}</span></p>}
                                        {p.url && <a href={p.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline block truncate">{p.url}</a>}
                                    </div>
                                    {p.issues?.length > 0 && (
                                        <div className="mt-2 pt-2 border-t border-gray-100">
                                            {p.issues.map((iss: string, j: number) => (
                                                <p key={j} className="text-[10px] text-red-600 flex items-start gap-1"><AlertCircle className="w-2.5 h-2.5 mt-0.5 flex-shrink-0" />{iss}</p>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            {strategy && typeof strategy === 'string' && (
                <section>
                    <h5 className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-2">Content Strategy</h5>
                    <p className="text-sm text-gray-700 leading-relaxed p-3 bg-indigo-50 rounded-xl border border-indigo-100">{strategy}</p>
                </section>
            )}

            {recommendations.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-purple-600 uppercase tracking-wider mb-2">Recommendations</h5>
                    <ul className="space-y-1.5">
                        {recommendations.map((r: string, i: number) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-purple-50 rounded-lg border border-purple-100">
                                <Star className="w-3.5 h-3.5 text-purple-600 mt-0.5 flex-shrink-0" />{r}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <SectionActions bizId="" sectionKey="social_media_auditor" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} onDelete={onDelete} />
        </div>
    );
}

function TrafficOutputPanel({ output, savedState, onSave, onOutreach, onDelete }: {
    output: Record<string, any>; savedState: SaveState;
    onSave: (t: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void; onDelete: () => Promise<void>;
}) {
    const score = output.score ?? output.overall_score ?? output.overallScore;
    const peakHours: any[] = output.peak_hours || [];
    const peakDays: any[] = output.peak_days || [];
    const slowPeriods: string[] = output.slow_periods || [];
    const opportunities: string[] = output.opportunity_windows || output.opportunities || [];

    const dayName = (d: any) => typeof d === 'string' ? d : (d?.day || d?.name || String(d));

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                {score != null && (
                    <div className="mb-3">
                        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                            <span className="font-semibold text-gray-700">Traffic Score</span>
                            <span className="font-bold text-lg text-gray-800">{score}<span className="text-xs text-gray-400">/100</span></span>
                        </div>
                        <ScoreBar score={score} />
                    </div>
                )}
                {output.peak_slot_score != null && (
                    <div className="text-xs mt-2">
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded border border-blue-100">Peak Slot Score: <strong>{output.peak_slot_score}</strong></span>
                    </div>
                )}
                {output.summary && <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.summary}</p>}
                {output.runAt && <p className="text-[10px] text-gray-400 mt-2">Run at {new Date(output.runAt).toLocaleString()} · v{output.agentVersion}</p>}
            </div>

            {(peakHours.length > 0 || peakDays.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {peakHours.length > 0 && (
                        <section>
                            <h5 className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2">Peak Hours</h5>
                            <div className="flex flex-wrap gap-1.5">
                                {peakHours.map((h: any, i: number) => (
                                    <span key={i} className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-100 rounded-lg font-medium">
                                        {typeof h === 'string' ? h : (h.hour || h.time || String(h))}
                                        {h.traffic_level && <span className="ml-1 opacity-60">({h.traffic_level})</span>}
                                    </span>
                                ))}
                            </div>
                        </section>
                    )}
                    {peakDays.length > 0 && (
                        <section>
                            <h5 className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2">Peak Days</h5>
                            <div className="flex flex-wrap gap-1.5">
                                {peakDays.map((d: any, i: number) => (
                                    <span key={i} className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-100 rounded-lg font-medium">{dayName(d)}</span>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            )}

            {slowPeriods.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Slow Periods</h5>
                    <div className="flex flex-wrap gap-1.5">
                        {slowPeriods.map((p: string, i: number) => (
                            <span key={i} className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 border border-gray-200 rounded-lg">{p}</span>
                        ))}
                    </div>
                </section>
            )}

            {opportunities.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Opportunity Windows</h5>
                    <ul className="space-y-1.5">
                        {opportunities.map((o: string, i: number) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-emerald-50 rounded-lg border border-emerald-100">
                                <TrendingUp className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />{o}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <SectionActions bizId="" sectionKey="traffic_forecaster" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} onDelete={onDelete} />
        </div>
    );
}

function ReviewerOutputPanel({ output, onOutreach }: { output: ReviewerOutput; onOutreach: () => void; }) {
    const score = output.outreach_score;
    const scoreColor = score >= 8 ? 'text-emerald-700' : score >= 5 ? 'text-amber-700' : 'text-red-600';
    const barScore = score * 10;

    return (
        <div className="space-y-4">
            <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Outreach Readiness</span>
                    <span className={`text-2xl font-bold ${scoreColor}`}>{score}<span className="text-sm text-gray-400">/10</span></span>
                </div>
                <ScoreBar score={barScore} />
                {output.primary_reason && (
                    <p className="text-sm text-gray-700 leading-relaxed mt-3 pt-3 border-t border-gray-200">{output.primary_reason}</p>
                )}
                {output.best_channel && (
                    <p className="text-xs text-gray-500 mt-2">Best channel: <span className="font-medium text-gray-700 capitalize">{output.best_channel}</span></p>
                )}
            </div>

            {output.strengths?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2">Reasons to Reach Out</h5>
                    <ul className="space-y-1.5">
                        {output.strengths.map((s, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-emerald-50 rounded-lg border border-emerald-100">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />{s}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {output.concerns?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-red-600 uppercase tracking-wider mb-2">Concerns</h5>
                    <ul className="space-y-1.5">
                        {output.concerns.map((c, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-2 p-2 bg-red-50 rounded-lg border border-red-100">
                                <AlertCircle className="w-3.5 h-3.5 text-red-500 mt-0.5 flex-shrink-0" />{c}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {score >= 6 && (
                <button onClick={onOutreach}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 transition-colors">
                    <Send className="w-4 h-4" /> Send Outreach via {output.best_channel || 'best channel'}
                </button>
            )}
        </div>
    );
}

function InsightsPanel({ insights, savedState, onSave, onOutreach }: {
    insights: { summary: string; keyFindings: string[]; recommendations: string[] };
    savedState: SaveState;
    onSave: (type: 'grounding' | 'test_case') => Promise<void>;
    onOutreach: () => void;
}) {
    return (
        <div className="space-y-4">
            {insights.summary && (
                <div className="p-4 bg-gray-50 rounded-xl border border-gray-200">
                    <p className="text-sm text-gray-700 leading-relaxed">{insights.summary}</p>
                </div>
            )}
            {insights.keyFindings?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-2 pb-1 border-b border-indigo-100">Key Findings</h5>
                    <ul className="space-y-1.5">
                        {insights.keyFindings.map((f, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
                                <ChevronRight className="w-3.5 h-3.5 text-indigo-400 mt-0.5 flex-shrink-0" />{f}
                            </li>
                        ))}
                    </ul>
                </section>
            )}
            {insights.recommendations?.length > 0 && (
                <section>
                    <h5 className="text-xs font-semibold text-emerald-600 uppercase tracking-wider mb-2 pb-1 border-b border-emerald-100">Recommendations</h5>
                    <ul className="space-y-1.5">
                        {insights.recommendations.map((r, i) => (
                            <li key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />{r}
                            </li>
                        ))}
                    </ul>
                </section>
            )}
            <SectionActions bizId="" sectionKey="insights" savedState={savedState}
                onSave={onSave} onOutreach={onOutreach} />
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function BusinessBrowser({ zipCode }: BusinessBrowserProps) {
    const [businesses, setBusinesses] = useState<Business[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const PAGE_SIZE = 25;

    const [isLoading, setIsLoading] = useState(false);
    const [actionId, setActionId] = useState<string | null>(null);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [activeSection, setActiveSection] = useState<Record<string, string>>({});
    const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
    const [confirmingId, setConfirmingId] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [bulkLoading, setBulkLoading] = useState<string | null>(null);
    const [savedMap, setSavedMap] = useState<Record<string, SaveState>>({});
    const [outreachTarget, setOutreachTarget] = useState<Business | null>(null);

    // Filters
    const [filterCategory, setFilterCategory] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [filterHasEmail, setFilterHasEmail] = useState<boolean | null>(null);
    const [filterName, setFilterName] = useState('');
    const [debouncedFilterName, setDebouncedFilterName] = useState('');
    const [showFilters, setShowFilters] = useState(false);

    // Debounce name filter (300ms)
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedFilterName(filterName);
        }, 300);
        return () => clearTimeout(timer);
    }, [filterName]);

    const buildQuery = useCallback((p: number) => {
        const params = new URLSearchParams({ zipCode, page: String(p), pageSize: String(PAGE_SIZE) });
        if (filterCategory) params.set('category', filterCategory);
        if (filterStatus) params.set('status', filterStatus);
        if (filterHasEmail !== null) params.set('hasEmail', String(filterHasEmail));
        if (debouncedFilterName) params.set('name', debouncedFilterName);
        return params.toString();
    }, [zipCode, filterCategory, filterStatus, filterHasEmail, debouncedFilterName]);

    const fetchBusinesses = useCallback(async (p = page) => {
        if (!zipCode) return;
        setIsLoading(true);
        try {
            const res = await fetch(`/api/research/businesses?${buildQuery(p)}`);
            if (!res.ok) throw new Error('Failed to fetch');
            const data: PaginatedResponse = await res.json();
            setBusinesses(data.businesses);
            setTotal(data.total);
            setPage(data.page);
            setTotalPages(data.pages);
        } catch (err) { console.error(err); }
        finally { setIsLoading(false); }
    }, [zipCode, buildQuery, page]);

    useEffect(() => {
        setPage(1);
        fetchBusinesses(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [zipCode, filterCategory, filterStatus, filterHasEmail, debouncedFilterName]);

    const callAction = async (body: Record<string, unknown>): Promise<any | null> => {
        const res = await fetch('/api/research/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) { console.error('Action failed:', await res.json().catch(() => ({}))); return null; }
        return res.json();
    };

    const handleAction = async (biz: Business, action: string, opts: Record<string, unknown> = {}) => {
        setActionId(`${biz.id}-${action}`);
        setMenuOpenId(null);
        try {
            const result = await callAction({ action, businessId: biz.id, ...opts });
            if (result) {
                if (action === 'delete') {
                    setBusinesses(prev => prev.filter(b => b.id !== biz.id));
                    setSelectedIds(prev => { const n = new Set(prev); n.delete(biz.id); return n; });
                } else {
                    await fetchBusinesses(page);
                }
            }
        } finally { setActionId(null); setConfirmingId(null); }
    };

    const handleSaveFixture = async (bizId: string, sectionKey: string, type: 'grounding' | 'test_case') => {
        const biz = businesses.find(b => b.id === bizId);
        if (!biz) return;
        await handleAction(biz, 'save-fixture', { fixtureType: type, notes: `Section: ${sectionKey}` });
        const key = `${bizId}:${sectionKey}`;
        setSavedMap(prev => ({ ...prev, [key]: { ...prev[key], [type]: true } }));
    };

    const handleOutreachSend = async (biz: Business, channel: string) => {
        await handleAction(biz, 'outreach', { channel });
    };

    const handleDeleteAgentResult = async (bizId: string, agentKey: string) => {
        const biz = businesses.find(b => b.id === bizId);
        if (!biz) return;
        await handleAction(biz, 'delete-agent-result', { agentKey });
        const key = `${bizId}:${agentKey}`;
        setSavedMap(prev => { const n = { ...prev }; delete n[key]; return n; });
    };

    const selectedList = businesses.filter(b => selectedIds.has(b.id));
    const handleBulk = async (bulkAction: string, extra: Record<string, unknown> = {}, loadingKey?: string) => {
        if (!selectedList.length) return;
        setBulkLoading(loadingKey ?? bulkAction);
        try {
            await callAction({ action: 'bulk', businessIds: selectedList.map(b => b.id), bulkAction, ...extra });
            await fetchBusinesses(page);
        } finally { setBulkLoading(null); }
    };

    const toggleSelect = (id: string) => setSelectedIds(prev => {
        const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n;
    });
    const toggleSelectAll = () => setSelectedIds(
        selectedIds.size === businesses.length ? new Set() : new Set(businesses.map(b => b.id))
    );
    const toggleExpand = (id: string) => {
        setExpandedId(prev => prev === id ? null : id);
        if (!activeSection[id]) setActiveSection(prev => ({ ...prev, [id]: 'discovery' }));
    };
    const getSavedState = (bizId: string, sectionKey: string): SaveState => {
        return savedMap[`${bizId}:${sectionKey}`] ?? { grounding: false, test_case: false };
    };

    const clearFilters = () => {
        setFilterCategory('');
        setFilterStatus('');
        setFilterHasEmail(null);
        setFilterName('');
    };
    const hasActiveFilters = filterCategory || filterStatus || filterHasEmail !== null || filterName;

    // ── Render ───────────────────────────────────────────────────────────────
    if (isLoading && !businesses.length) return (
        <div className="flex items-center justify-center py-20 text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading businesses...
        </div>
    );

    const allSelected = businesses.length > 0 && selectedIds.size === businesses.length;
    const someSelected = selectedIds.size > 0;

    return (
        <div className="space-y-3">
            {/* Header with filters */}
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <button onClick={toggleSelectAll} className="text-gray-400 hover:text-indigo-600 p-1 transition-colors">
                        {allSelected ? <CheckSquare className="w-4 h-4 text-indigo-600" /> : <Square className="w-4 h-4" />}
                    </button>
                    <p className="text-sm text-gray-500">
                        {someSelected
                            ? `${selectedIds.size} of ${businesses.length} selected`
                            : total > 0 ? `${total} businesses${hasActiveFilters ? ' (filtered)' : ''}`
                            : `0 businesses in ${zipCode}`}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button onClick={() => setShowFilters(f => !f)}
                        className={`text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${showFilters || hasActiveFilters ? 'bg-indigo-50 text-indigo-700 border-indigo-200' : 'bg-gray-50 text-gray-500 border-gray-200 hover:bg-gray-100'}`}>
                        <Filter className="w-3 h-3" /> Filters
                        {hasActiveFilters && <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />}
                    </button>
                    <button onClick={() => fetchBusinesses(page)} disabled={isLoading}
                        className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 disabled:opacity-50">
                        {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Refresh
                    </button>
                </div>
            </div>

            {/* Filter bar */}
            {showFilters && (
                <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl flex flex-wrap gap-3 items-end">
                    <div>
                        <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide block mb-1">Name</label>
                        <input value={filterName} onChange={e => setFilterName(e.target.value)}
                            placeholder="Search by name"
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 w-36 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                    </div>
                    <div>
                        <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide block mb-1">Status</label>
                        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                            <option value="">All statuses</option>
                            <option value="scanned">Scanned</option>
                            <option value="discovered">Discovered</option>
                            <option value="analyzed">Analyzed</option>
                            <option value="failed">Failed</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide block mb-1">Category</label>
                        <input value={filterCategory} onChange={e => setFilterCategory(e.target.value)}
                            placeholder="e.g. restaurant"
                            className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-gray-700 w-32 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                    </div>
                    <div>
                        <label className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide block mb-1">Contact</label>
                        <div className="flex items-center gap-1.5">
                            {[{ label: 'All', value: null }, { label: 'Has email', value: true }, { label: 'No email', value: false }].map(opt => (
                                <button key={String(opt.value)} onClick={() => setFilterHasEmail(opt.value)}
                                    className={`text-[11px] px-2 py-1 rounded-lg border transition-colors ${filterHasEmail === opt.value ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    {hasActiveFilters && (
                        <button onClick={clearFilters} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 ml-auto">
                            <X className="w-3 h-3" /> Clear filters
                        </button>
                    )}
                </div>
            )}

            {/* Bulk toolbar */}
            {someSelected && (
                <div className="flex flex-wrap items-center gap-2 p-3 bg-indigo-50 border border-indigo-200 rounded-xl">
                    <span className="text-xs font-semibold text-indigo-700 mr-1">{selectedIds.size} selected</span>
                    <button onClick={() => handleBulk('start-discovery')} disabled={!!bulkLoading}
                        className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                        {bulkLoading === 'start-discovery' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />} Discover All
                    </button>
                    <button onClick={() => handleBulk('run-analysis')} disabled={!!bulkLoading}
                        className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50">
                        {bulkLoading === 'run-analysis' ? <Loader2 className="w-3 h-3 animate-spin" /> : <BarChart3 className="w-3 h-3" />} Analyze All
                    </button>
                    <button onClick={() => handleBulk('run-reviewer', {}, 'run-reviewer')} disabled={!!bulkLoading}
                        className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
                        {bulkLoading === 'run-reviewer' ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserCheck className="w-3 h-3" />} Review All
                    </button>
                    <div className="w-px h-4 bg-indigo-200" />
                    {AGENTS.map(agent => (
                        <button key={agent.name}
                            onClick={() => handleBulk('run-agent', { agentName: agent.name }, `run-agent:${agent.name}`)}
                            disabled={!!bulkLoading}
                            className="text-xs flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white text-indigo-700 border border-indigo-200 hover:bg-indigo-100 disabled:opacity-50">
                            {bulkLoading === `run-agent:${agent.name}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <span>{agent.icon}</span>}
                            {agent.label}
                        </button>
                    ))}
                    <button onClick={() => setSelectedIds(new Set())}
                        className="ml-auto text-xs flex items-center gap-1 text-indigo-500 hover:text-indigo-700 px-2 py-1">
                        <X className="w-3 h-3" /> Clear
                    </button>
                </div>
            )}

            {/* Empty state */}
            {!isLoading && !businesses.length && (
                <div className="text-center py-16 border border-dashed border-gray-300 rounded-xl text-gray-400">
                    <p>{hasActiveFilters ? 'No businesses match the current filters.' : `No businesses found for ${zipCode}. Use "Scan Businesses" above.`}</p>
                    {hasActiveFilters && (
                        <button onClick={clearFilters} className="mt-2 text-xs text-indigo-600 hover:underline">Clear filters</button>
                    )}
                </div>
            )}

            {/* Business list */}
            {businesses.map((biz) => {
                const isExpanded = expandedId === biz.id;
                const isSelected = selectedIds.has(biz.id);
                const isConfirming = confirmingId === biz.id;
                const outputs = biz.latestOutputs ?? {};
                const reviewer = outputs.reviewer as ReviewerOutput | undefined;

                const tabs: { key: string; label: string; hasData: boolean }[] = [
                    { key: 'discovery', label: 'Discovery', hasData: !!(biz.identity || biz.discoveryStatus === 'discovered' || biz.discoveryStatus === 'analyzed') },
                    ...AGENTS.map(a => ({ key: a.outputKey, label: a.label, hasData: !!outputs[a.outputKey] })),
                    { key: 'reviewer', label: 'Reviewer', hasData: !!reviewer },
                    { key: 'insights', label: 'Insights', hasData: !!biz.insights },
                ];
                const curSection = activeSection[biz.id] || 'discovery';

                return (
                    <div key={biz.id} className={`bg-white border rounded-xl transition-shadow ${isExpanded ? 'border-indigo-300 shadow-md' : isSelected ? 'border-indigo-200 shadow-sm' : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'}`}>
                        {/* Row */}
                        <div className="flex items-center gap-3 p-4">
                            <button onClick={() => toggleSelect(biz.id)} className="flex-shrink-0 text-gray-300 hover:text-indigo-600 transition-colors">
                                {isSelected ? <CheckSquare className="w-4 h-4 text-indigo-600" /> : <Square className="w-4 h-4" />}
                            </button>

                            {biz.logoUrl ? (
                                <img src={biz.logoUrl} alt="" className="w-9 h-9 rounded-lg object-contain border border-gray-100 bg-white flex-shrink-0"
                                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                            ) : (
                                <div className="w-9 h-9 rounded-lg flex-shrink-0 flex items-center justify-center text-white text-sm font-bold"
                                    style={{ backgroundColor: biz.primaryColor || '#6366f1' }}>
                                    {biz.name[0]}
                                </div>
                            )}

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <h4 className="font-semibold text-gray-900 truncate">{biz.name}</h4>
                                    {statusBadge(biz.discoveryStatus)}
                                    {reviewer && <ReviewerBadge reviewer={reviewer} />}
                                    {biz.crm?.status === 'outreached' && (
                                        <span title="Outreached"><CheckCircle2 className="w-3.5 h-3.5 text-green-500 flex-shrink-0" /></span>
                                    )}
                                </div>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <p className="text-xs text-gray-500 truncate">{biz.address}</p>
                                    {biz.category && (
                                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center gap-0.5 flex-shrink-0">
                                            <Tag className="w-2.5 h-2.5" />{biz.category}
                                        </span>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center gap-1.5 flex-shrink-0">
                                {(!biz.discoveryStatus || biz.discoveryStatus === 'scanned' || biz.discoveryStatus === 'failed') && (
                                    <button onClick={() => handleAction(biz, 'start-discovery')} disabled={!!actionId}
                                        className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 px-2.5 py-1.5 rounded-lg flex items-center gap-1 border border-blue-200 disabled:opacity-50">
                                        {actionId === `${biz.id}-start-discovery` ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />} Discover
                                    </button>
                                )}
                                {(biz.discoveryStatus === 'discovered' || biz.discoveryStatus === 'analyzed') && (
                                    <button onClick={() => handleAction(biz, 'run-analysis')} disabled={!!actionId}
                                        className="text-xs bg-violet-50 hover:bg-violet-100 text-violet-700 px-2.5 py-1.5 rounded-lg flex items-center gap-1 border border-violet-200 disabled:opacity-50">
                                        {actionId === `${biz.id}-run-analysis` ? <Loader2 className="w-3 h-3 animate-spin" /> : <BarChart3 className="w-3 h-3" />}
                                        {biz.discoveryStatus === 'analyzed' ? 'Re-Analyze' : 'Analyze All'}
                                    </button>
                                )}
                                <button onClick={() => toggleExpand(biz.id)}
                                    className={`text-xs px-2.5 py-1.5 rounded-lg flex items-center gap-1 border transition-colors ${isExpanded ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'}`}>
                                    {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                    {isExpanded ? 'Hide' : 'View'}
                                </button>

                                <div className="relative">
                                    <button onClick={() => setMenuOpenId(menuOpenId === biz.id ? null : biz.id)}
                                        className="text-xs bg-gray-50 hover:bg-gray-100 text-gray-500 px-2 py-1.5 rounded-lg border border-gray-200">
                                        <MoreVertical className="w-3.5 h-3.5" />
                                    </button>
                                    {menuOpenId === biz.id && (
                                        <div className="absolute right-0 top-full mt-1 w-52 bg-white border border-gray-200 rounded-lg shadow-xl z-30 py-1">
                                            <div className="px-3 py-1.5">
                                                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Run Agent</p>
                                            </div>
                                            {AGENTS.map(agent => (
                                                <button key={agent.name}
                                                    onClick={() => handleAction(biz, 'run-agent', { agentName: agent.name })}
                                                    disabled={!!actionId}
                                                    className="w-full text-left text-xs px-3 py-2 hover:bg-gray-50 text-gray-700 flex items-center gap-2 disabled:opacity-50">
                                                    <span>{agent.icon}</span> {agent.label}
                                                </button>
                                            ))}
                                            <button onClick={() => handleAction(biz, 'run-reviewer')} disabled={!!actionId}
                                                className="w-full text-left text-xs px-3 py-2 hover:bg-gray-50 text-gray-700 flex items-center gap-2">
                                                <UserCheck className="w-3 h-3" /> Review for Outreach
                                            </button>
                                            <div className="border-t border-gray-100 my-1" />
                                            <button onClick={() => handleAction(biz, 'rediscover')} disabled={!!actionId}
                                                className="w-full text-left text-xs px-3 py-2 hover:bg-gray-50 text-gray-700 flex items-center gap-2">
                                                <RefreshCw className="w-3 h-3" /> Re-run Discovery
                                            </button>
                                            <button onClick={() => { setMenuOpenId(null); setOutreachTarget(biz); }} disabled={!!actionId}
                                                className="w-full text-left text-xs px-3 py-2 hover:bg-gray-50 text-gray-700 flex items-center gap-2">
                                                <Send className="w-3 h-3" /> Send Outreach...
                                            </button>
                                            <div className="border-t border-gray-100 my-1" />
                                            {isConfirming ? (
                                                <div className="px-3 py-2 flex gap-2">
                                                    <button onClick={() => handleAction(biz, 'delete')} disabled={!!actionId}
                                                        className="flex-1 text-xs bg-red-600 text-white py-1 rounded flex items-center justify-center gap-1">
                                                        <Trash2 className="w-3 h-3" /> Confirm
                                                    </button>
                                                    <button onClick={() => setConfirmingId(null)} className="flex-1 text-xs bg-gray-100 text-gray-600 py-1 rounded">Cancel</button>
                                                </div>
                                            ) : (
                                                <button onClick={() => { setConfirmingId(biz.id); setMenuOpenId(null); }}
                                                    className="w-full text-left text-xs px-3 py-2 hover:bg-red-50 text-red-600 flex items-center gap-2">
                                                    <Trash2 className="w-3 h-3" /> Delete Business
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Expanded detail panel */}
                        {isExpanded && (
                            <div className="border-t border-gray-100">
                                <div className="flex border-b border-gray-100 overflow-x-auto">
                                    {tabs.map(tab => (
                                        <button key={tab.key}
                                            onClick={() => setActiveSection(prev => ({ ...prev, [biz.id]: tab.key }))}
                                            className={`text-xs px-4 py-2.5 font-medium border-b-2 transition-colors flex-shrink-0 flex items-center gap-1.5 ${curSection === tab.key ? 'border-indigo-500 text-indigo-700 bg-indigo-50/50' : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}>
                                            {tab.label}
                                            {tab.hasData && tab.key !== 'discovery' && (
                                                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${tab.key === 'reviewer' && reviewer ? (reviewer.outreach_score >= 8 ? 'bg-emerald-500' : reviewer.outreach_score >= 5 ? 'bg-amber-400' : 'bg-red-400') : 'bg-emerald-400'}`} />
                                            )}
                                        </button>
                                    ))}
                                </div>

                                <div className="p-5">
                                    {curSection === 'discovery' && (
                                        <DiscoveryPanel biz={biz}
                                            savedState={getSavedState(biz.id, 'discovery')}
                                            onSave={type => handleSaveFixture(biz.id, 'discovery', type)}
                                            onOutreach={() => setOutreachTarget(biz)} />
                                    )}
                                    {curSection === 'seo_auditor' && outputs.seo_auditor && (
                                        <SeoOutputPanel output={outputs.seo_auditor}
                                            savedState={getSavedState(biz.id, 'seo_auditor')}
                                            onSave={type => handleSaveFixture(biz.id, 'seo_auditor', type)}
                                            onOutreach={() => setOutreachTarget(biz)}
                                            onDelete={() => handleDeleteAgentResult(biz.id, 'seo_auditor')} />
                                    )}
                                    {curSection === 'competitive_analyzer' && outputs.competitive_analyzer && (
                                        <CompetitiveOutputPanel output={outputs.competitive_analyzer}
                                            savedState={getSavedState(biz.id, 'competitive_analyzer')}
                                            onSave={type => handleSaveFixture(biz.id, 'competitive_analyzer', type)}
                                            onOutreach={() => setOutreachTarget(biz)}
                                            onDelete={() => handleDeleteAgentResult(biz.id, 'competitive_analyzer')} />
                                    )}
                                    {curSection === 'margin_surgeon' && outputs.margin_surgeon && (
                                        <MarginOutputPanel output={outputs.margin_surgeon}
                                            savedState={getSavedState(biz.id, 'margin_surgeon')}
                                            onSave={type => handleSaveFixture(biz.id, 'margin_surgeon', type)}
                                            onOutreach={() => setOutreachTarget(biz)}
                                            onDelete={() => handleDeleteAgentResult(biz.id, 'margin_surgeon')} />
                                    )}
                                    {curSection === 'social_media_auditor' && outputs.social_media_auditor && (
                                        <SocialMediaOutputPanel output={outputs.social_media_auditor}
                                            savedState={getSavedState(biz.id, 'social_media_auditor')}
                                            onSave={type => handleSaveFixture(biz.id, 'social_media_auditor', type)}
                                            onOutreach={() => setOutreachTarget(biz)}
                                            onDelete={() => handleDeleteAgentResult(biz.id, 'social_media_auditor')} />
                                    )}
                                    {curSection === 'traffic_forecaster' && outputs.traffic_forecaster && (
                                        <TrafficOutputPanel output={outputs.traffic_forecaster}
                                            savedState={getSavedState(biz.id, 'traffic_forecaster')}
                                            onSave={type => handleSaveFixture(biz.id, 'traffic_forecaster', type)}
                                            onOutreach={() => setOutreachTarget(biz)}
                                            onDelete={() => handleDeleteAgentResult(biz.id, 'traffic_forecaster')} />
                                    )}
                                    {curSection === 'reviewer' && reviewer && (
                                        <ReviewerOutputPanel output={reviewer} onOutreach={() => setOutreachTarget(biz)} />
                                    )}
                                    {curSection === 'insights' && biz.insights && (
                                        <InsightsPanel insights={biz.insights}
                                            savedState={getSavedState(biz.id, 'insights')}
                                            onSave={type => handleSaveFixture(biz.id, 'insights', type)}
                                            onOutreach={() => setOutreachTarget(biz)} />
                                    )}
                                    {/* Empty states */}
                                    {curSection !== 'discovery' && curSection !== 'insights' && curSection !== 'reviewer' && !outputs[curSection] && (
                                        <div className="py-10 text-center text-gray-400 text-sm">
                                            <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
                                            No data yet for this agent. Run it from the <strong>⋮ menu</strong> or click <strong>Analyze All</strong>.
                                        </div>
                                    )}
                                    {curSection === 'reviewer' && !reviewer && (
                                        <div className="py-10 text-center text-gray-400 text-sm">
                                            <UserCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
                                            No review yet. Click <strong>Review for Outreach</strong> in the ⋮ menu.
                                        </div>
                                    )}
                                    {curSection === 'insights' && !biz.insights && (
                                        <div className="py-10 text-center text-gray-400 text-sm">
                                            <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-40" />
                                            Insights are generated after analysis completes.
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between pt-2">
                    <p className="text-xs text-gray-500">
                        Page {page} of {totalPages} · {total} total
                    </p>
                    <div className="flex items-center gap-1.5">
                        <button onClick={() => { const p = page - 1; setPage(p); fetchBusinesses(p); }}
                            disabled={page <= 1 || isLoading}
                            className="text-xs flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40">
                            <ChevronLeft className="w-3 h-3" /> Prev
                        </button>
                        {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                            const p = start + i;
                            if (p > totalPages) return null;
                            return (
                                <button key={p} onClick={() => { setPage(p); fetchBusinesses(p); }}
                                    disabled={isLoading}
                                    className={`text-xs w-7 h-7 rounded-lg border flex items-center justify-center transition-colors ${p === page ? 'bg-indigo-600 text-white border-indigo-600' : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'}`}>
                                    {p}
                                </button>
                            );
                        })}
                        <button onClick={() => { const p = page + 1; setPage(p); fetchBusinesses(p); }}
                            disabled={page >= totalPages || isLoading}
                            className="text-xs flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40">
                            Next <ChevronRight className="w-3 h-3" />
                        </button>
                    </div>
                </div>
            )}

            {/* Content Studio modal */}
            {outreachTarget && (
                <ContentStudioModal
                    biz={outreachTarget}
                    onClose={() => setOutreachTarget(null)}
                    onSend={channel => handleOutreachSend(outreachTarget, channel)} />
            )}
        </div>
    );
}
