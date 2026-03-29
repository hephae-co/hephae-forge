'use client';

import { useState } from 'react';
import { BarChart3, DollarSign, Globe, TrendingUp, Flame, Search, MapPin, Lock, Radio } from 'lucide-react';

export type ActiveSection = 'overview' | 'margin' | 'seo' | 'traffic' | 'competitive' | 'local-intel';

const GATED_SECTIONS: ActiveSection[] = ['margin', 'seo', 'traffic', 'competitive'];

const NAV: { id: ActiveSection; label: string; icon: React.ElementType; section?: 'analyses' | 'intel' }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'local-intel', label: 'Local Intel', icon: Radio, section: 'intel' },
  { id: 'margin', label: 'Margin', icon: DollarSign, section: 'analyses' },
  { id: 'seo', label: 'SEO Health', icon: Globe, section: 'analyses' },
  { id: 'traffic', label: 'Foot Traffic', icon: TrendingUp, section: 'analyses' },
  { id: 'competitive', label: 'Competitive', icon: Flame, section: 'analyses' },
];

export function LeftSidebar({
  active,
  onSelect,
  onSearch,
  showNominateZip,
  onNominateZip,
  isLoggedIn = true,
  availableReports = {},
  /** Per-capability readiness: does the user have enough data to run each? */
  capabilityReady = {},
}: {
  active: ActiveSection;
  onSelect: (s: ActiveSection) => void;
  onSearch: (query: string) => void;
  showNominateZip?: boolean;
  onNominateZip?: () => void;
  isLoggedIn?: boolean;
  availableReports?: Partial<Record<ActiveSection, boolean>>;
  capabilityReady?: Partial<Record<ActiveSection, boolean>>;
}) {
  const [q, setQ] = useState('');

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-64px)] w-56 bg-white border-r border-purple-100/60 flex flex-col p-4 gap-2 z-40">
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { onSearch(q); setQ(''); } }}
          placeholder="Search business..."
          className="w-full bg-purple-50/60 border border-purple-100 rounded-xl pl-8 pr-3 py-2 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-300/30"
        />
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map(({ id, label, icon: Icon, section }, idx) => {
          // Section divider before first 'analyses' item
          const prevSection = idx > 0 ? NAV[idx - 1].section : undefined;
          const showDivider = section && section !== prevSection;
          const isGated = GATED_SECTIONS.includes(id);
          const hasReport = !!availableReports[id];
          const isReady = !!capabilityReady[id];
          const isLocked = isGated && !hasReport && !isReady && !isLoggedIn;
          const lockReason = !isLoggedIn ? 'Sign in to unlock' : '';
          return (
            <div key={id}>
            {showDivider && (
              <div className="px-3 pt-3 pb-1">
                <p className="text-[9px] font-bold uppercase tracking-widest text-slate-300">{section === 'analyses' ? 'Analyses' : 'Intelligence'}</p>
              </div>
            )}
            <div className="relative group/navitem">
              <button
                onClick={() => !isLocked && onSelect(id)}
                disabled={isLocked}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-widest transition-all text-left ${
                  isLocked
                    ? 'text-slate-400 cursor-not-allowed opacity-50'
                    : active === id
                      ? 'bg-white text-purple-700 shadow-sm shadow-purple-900/8 border border-purple-100'
                      : 'text-slate-500 hover:bg-purple-50/60 hover:text-purple-600 hover:translate-x-0.5'
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">{label}</span>
                {hasReport && !isLocked && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" title="Report available" />}
                {isLocked && <Lock className="w-3 h-3 opacity-70 flex-shrink-0" />}
              </button>
              {isLocked && (
                <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 hidden group-hover/navitem:block z-50 pointer-events-none">
                  <div className="bg-slate-800 text-white text-[10px] font-semibold px-2.5 py-1.5 rounded-lg whitespace-nowrap shadow-lg">
                    {lockReason}
                    <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
                  </div>
                </div>
              )}
            </div>
            </div>
          );
        })}
      </nav>

      <div className="mt-auto pt-4 border-t border-slate-100 space-y-3">
        {showNominateZip && (
          <button
            onClick={onNominateZip}
            className="w-full flex items-center justify-center gap-2 bg-amber-50 border border-amber-200 text-amber-700 rounded-xl px-3 py-2.5 text-xs font-bold hover:bg-amber-100 transition-colors"
          >
            <MapPin className="w-3.5 h-3.5" /> Nominate this zip
          </button>
        )}
        <div>
          <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400 px-3 mb-2">Data Sources</div>
          <div className="flex flex-wrap gap-1 px-2">
            {['BLS', 'USDA', 'Census', 'NWS', 'OSM', 'IRS'].map(s => (
              <span key={s} className="text-[9px] font-bold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded">{s}</span>
            ))}
          </div>
          <p className="text-[9px] text-slate-400 px-3 mt-2">12 verified data sources</p>
        </div>
      </div>
    </aside>
  );
}
