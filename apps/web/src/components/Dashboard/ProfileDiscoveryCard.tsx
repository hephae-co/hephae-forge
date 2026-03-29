'use client';

import { Sparkles, CheckCircle, CircleDashed, ArrowRight, DollarSign, Globe, TrendingUp, Flame, ExternalLink, Pencil } from 'lucide-react';
import { Card, Label } from './Card';

export interface ProfileStatus {
  hasWebsite: boolean;
  hasMenu: boolean;
  hasSocial: boolean;
  hasHours: boolean;
}

export interface ProfileData {
  officialUrl?: string;
  menuUrl?: string;
  socialLinks?: Record<string, string>;
  deliveryLinks?: Record<string, string>;
}

export function ProfileDiscoveryCard({
  status,
  profileData,
  isBuilding,
  isBuilt,
  onStartBuild,
  onSignIn,
  onEditProfile,
  isSignedIn,
}: {
  status: ProfileStatus;
  profileData: ProfileData;
  isBuilding: boolean;
  isBuilt: boolean;
  onStartBuild: () => void;
  onSignIn: () => void;
  onEditProfile?: () => void;
  isSignedIn: boolean;
}) {
  const completed = [status.hasWebsite, status.hasMenu, status.hasSocial, status.hasHours].filter(Boolean).length;
  const total = 4;

  const items = [
    { label: 'Website', done: status.hasWebsite },
    { label: 'Menu URL', done: status.hasMenu },
    { label: 'Social profiles', done: status.hasSocial },
    { label: 'Operating hours', done: status.hasHours },
  ];

  const unlocks = [
    { icon: DollarSign, label: 'Margin Analysis' },
    { icon: Globe, label: 'SEO Audit' },
    { icon: TrendingUp, label: 'Traffic Forecast' },
    { icon: Flame, label: 'Competitive Intel' },
  ];

  // ── Built state: show profile summary with edit ────────────────────
  if (isBuilt && !isBuilding) {
    const links: { label: string; url: string }[] = [];
    if (profileData.officialUrl) links.push({ label: 'Website', url: profileData.officialUrl });
    if (profileData.menuUrl) links.push({ label: 'Menu', url: profileData.menuUrl });
    if (profileData.deliveryLinks) {
      for (const [platform, url] of Object.entries(profileData.deliveryLinks)) {
        if (url && platform !== 'menuUrl') links.push({ label: platform.charAt(0).toUpperCase() + platform.slice(1), url });
      }
    }
    if (profileData.socialLinks) {
      for (const [platform, url] of Object.entries(profileData.socialLinks)) {
        if (url) links.push({ label: platform.charAt(0).toUpperCase() + platform.slice(1), url });
      }
    }

    return (
      <Card className="p-6 border-l-4 border-emerald-500 h-full flex flex-col">
        <div className="flex justify-between items-start mb-3">
          <div>
            <Label>Business Profile</Label>
            <h3 className="text-lg font-bold tracking-tight text-slate-900 mt-1">Profile Complete</h3>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center">
              <CheckCircle className="w-4 h-4 text-emerald-500" />
            </div>
          </div>
        </div>

        {links.length > 0 && (
          <div className="flex-1 space-y-1.5 mb-4">
            {links.map(({ label, url }) => (
              <div key={label + url} className="flex items-center gap-2 text-xs">
                <span className="font-semibold text-slate-600 w-16 flex-shrink-0">{label}</span>
                <a href={url} target="_blank" rel="noopener noreferrer" className="text-purple-600 hover:text-purple-800 truncate flex items-center gap-1">
                  {url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 40)}
                  <ExternalLink className="w-2.5 h-2.5 flex-shrink-0 opacity-50" />
                </a>
              </div>
            ))}
          </div>
        )}

        {links.length === 0 && (
          <p className="text-xs text-slate-400 mb-4 flex-1">No links saved yet. Click below to add.</p>
        )}

        <button
          onClick={onEditProfile ?? onStartBuild}
          className="w-full flex items-center justify-center gap-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-600 px-4 py-2 rounded-xl text-xs font-semibold transition-colors"
        >
          <Pencil className="w-3 h-3" /> Edit profile / add more links
        </button>
      </Card>
    );
  }

  // ── Building state: show progress ──────────────────────────────────
  if (isBuilding) {
    return (
      <Card className="p-6 border-l-4 border-violet-500 h-full flex flex-col">
        <div className="flex justify-between items-start mb-3">
          <div>
            <Label>Profile Enrichment</Label>
            <h3 className="text-lg font-bold tracking-tight text-slate-900 mt-1">Discovering your profile...</h3>
          </div>
          <div className="flex-shrink-0 ml-3">
            <div className="relative w-12 h-12">
              <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90">
                <circle cx="18" cy="18" r="14" fill="none" stroke="#f1f5f9" strokeWidth="3" />
                <circle cx="18" cy="18" r="14" fill="none" stroke="#7c3aed" strokeWidth="3" strokeDasharray={`${(completed / total) * 88} 88`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xs font-black text-purple-700">{completed}/{total}</span>
            </div>
          </div>
        </div>

        <p className="text-xs text-slate-500 leading-relaxed mb-3">
          Check the chat — I&apos;ll ask you to confirm or fill in anything I can&apos;t find automatically.
        </p>

        <div className="grid grid-cols-2 gap-1.5 mb-4">
          {items.map(({ label, done }) => (
            <div key={label} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium ${done ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-600'}`}>
              {done ? <CheckCircle className="w-3 h-3 text-emerald-500 flex-shrink-0" /> : <CircleDashed className="w-3 h-3 text-amber-400 flex-shrink-0 animate-spin" style={{ animationDuration: '3s' }} />}
              {label}
            </div>
          ))}
        </div>

        <div className="mt-auto flex items-center gap-2 bg-violet-50 border border-violet-100 rounded-xl px-3 py-2">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce" />
            <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
            <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
          </div>
          <span className="text-xs text-violet-600 font-medium">Check the chat for questions →</span>
        </div>
      </Card>
    );
  }

  // ── Default: invitation to build/complete ──────────────────────────
  const missingItems = items.filter(i => !i.done);
  const hasPartialProfile = completed > 0 && completed < total;

  // Build a summary of what we already know
  const knownLinks: { label: string; url: string }[] = [];
  if (profileData.officialUrl) knownLinks.push({ label: 'Website', url: profileData.officialUrl });
  if (profileData.menuUrl) knownLinks.push({ label: 'Menu', url: profileData.menuUrl });
  if (profileData.socialLinks) {
    for (const [p, u] of Object.entries(profileData.socialLinks)) {
      if (u) knownLinks.push({ label: p.charAt(0).toUpperCase() + p.slice(1), url: u });
    }
  }

  return (
    <Card className="p-6 border-l-4 border-violet-500 h-full flex flex-col">
      <div className="flex justify-between items-start mb-3">
        <div>
          <Label>Profile Enrichment</Label>
          <h3 className="text-lg font-bold tracking-tight text-slate-900 mt-1">
            {hasPartialProfile ? 'Almost there — complete your profile' : 'Unlock deeper analyses'}
          </h3>
        </div>
        <div className="flex-shrink-0 ml-3">
          <div className="relative w-12 h-12">
            <svg viewBox="0 0 36 36" className="w-12 h-12 -rotate-90">
              <circle cx="18" cy="18" r="14" fill="none" stroke="#f1f5f9" strokeWidth="3" />
              <circle cx="18" cy="18" r="14" fill="none" stroke="#7c3aed" strokeWidth="3" strokeDasharray={`${(completed / total) * 88} 88`} strokeLinecap="round" />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-xs font-black text-purple-700">{completed}/{total}</span>
          </div>
        </div>
      </div>

      {/* Show what we already found */}
      {knownLinks.length > 0 && (
        <div className="mb-3 space-y-1">
          {knownLinks.map(({ label, url }) => (
            <div key={label + url} className="flex items-center gap-2 text-[11px]">
              <CheckCircle className="w-3 h-3 text-emerald-500 flex-shrink-0" />
              <span className="font-semibold text-slate-500 w-14 flex-shrink-0">{label}</span>
              <span className="text-slate-400 truncate">{url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 30)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Show what's missing */}
      {hasPartialProfile ? (
        <p className="text-xs text-slate-500 leading-relaxed mb-3">
          Just need: <strong>{missingItems.map(i => i.label.toLowerCase()).join(', ')}</strong>. Quick enrichment will try to find {missingItems.length === 1 ? 'it' : 'them'} automatically.
        </p>
      ) : (
        <div className="bg-purple-50/60 border border-purple-100 rounded-xl p-3 mb-3">
          <p className="text-[10px] font-bold text-purple-600 uppercase tracking-widest mb-2">This unlocks</p>
          <div className="grid grid-cols-2 gap-1.5">
            {unlocks.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-2 text-[11px]">
                <Icon className="w-3 h-3 text-purple-400 flex-shrink-0" />
                <span className="text-slate-600 font-medium">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {isSignedIn ? (
        <button
          onClick={onStartBuild}
          className="w-full flex items-center justify-center gap-2 bg-purple-700 hover:bg-purple-800 text-white px-4 py-2.5 rounded-xl text-xs font-bold shadow-md shadow-purple-900/20 transition-all hover:scale-[1.01] active:scale-95"
        >
          <Sparkles className="w-3.5 h-3.5" /> {hasPartialProfile ? 'Complete profile' : 'Build my profile'}
        </button>
      ) : (
        <button
          onClick={onSignIn}
          className="w-full flex items-center justify-center gap-2 bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700 px-4 py-2.5 rounded-xl text-xs font-bold transition-colors"
        >
          Sign in to build profile <ArrowRight className="w-3 h-3" />
        </button>
      )}
    </Card>
  );
}
