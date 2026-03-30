'use client';

import { MapPin, Utensils, Calendar, Database, TrendingUp, FileText } from 'lucide-react';
import { Card, Label } from './Card';
import type { DashboardData } from './types';

export function MarketPositionCard({ dashboard, onNominateZip }: { dashboard: DashboardData | null; onNominateZip?: () => void }) {
  const stats = dashboard?.stats;
  const keyMetrics = dashboard?.keyMetrics;
  const events = dashboard?.events;
  const isUltralocal = dashboard && !dashboard.isNational;

  const localIntel = dashboard?.localIntel;

  const researchSnippets = dashboard?.researchSnippets;

  // ── Build primary stat pills (max 3, curated) ──────────────────
  const pills: { label: string; value: string; accent: string }[] = [];

  // Location always first
  if (stats?.city && stats?.state) {
    pills.push({ label: 'Location', value: `${stats.city}, ${stats.state}`, accent: 'text-slate-700' });
  }

  // Competitors
  if (stats?.competitorCount != null && stats.competitorCount > 0) {
    pills.push({ label: 'Competitors', value: `${stats.competitorCount} nearby`, accent: 'text-purple-700' });
  }

  // Pick ONE curated metric from keyMetrics — the most impactful, with a human-readable label
  if (keyMetrics && pills.length < 3) {
    // Priority order: big movers that affect a restaurant owner's bottom line
    const curatedMetrics: { key: string; label: string }[] = [
      { key: 'beef_&_veal_yoy_pct', label: 'Beef Cost YoY' },
      { key: 'pork_yoy_pct', label: 'Pork Cost YoY' },
      { key: 'fish_&_seafood_mom_pct', label: 'Seafood MoM' },
      { key: 'food_(all_items)_yoy_pct', label: 'Food Inflation' },
      { key: 'fda_recent_recall_count', label: 'FDA Recalls' },
      { key: 'fresh_vegetables_yoy_pct', label: 'Produce YoY' },
    ];
    for (const { key, label } of curatedMetrics) {
      const val = keyMetrics[key];
      if (typeof val === 'number' && val !== 0 && pills.length < 3) {
        const isPercent = key.includes('pct');
        const formatted = isPercent ? `${val > 0 ? '+' : ''}${val.toFixed(1)}%` : val.toLocaleString();
        pills.push({ label, value: formatted, accent: val > 0 ? 'text-red-500' : 'text-emerald-600' });
        break; // Only one metric
      }
    }
  }

  // Data sources as trust signal
  if (stats?.confirmedSources && pills.length < 3) {
    pills.push({ label: 'Data Sources', value: `${stats.confirmedSources} verified`, accent: 'text-slate-500' });
  }

  // ── Events by name (not just a count) ────────────────────────────
  const upcomingEvents = events?.slice(0, 3);

  return (
    <Card className="p-5">
      <div className="flex items-center gap-2 mb-3">
        <MapPin className="w-4 h-4 text-purple-400" />
        <Label>Market Position</Label>
        {isUltralocal && (
          <span className="ml-2 text-[9px] font-bold uppercase tracking-widest bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded">Live · Ultralocal</span>
        )}
        {dashboard?.isNational && (
          <span className="ml-2 text-[9px] font-bold uppercase tracking-widest bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">National</span>
        )}
      </div>

      {/* Primary stat pills */}
      {pills.length > 0 ? (
        <div className={`grid ${pills.length <= 2 ? 'grid-cols-2' : pills.length <= 3 ? 'grid-cols-3' : 'grid-cols-4'} gap-3`}>
          {pills.map(({ label, value, accent }) => (
            <div key={label} className="bg-purple-50/60 rounded-xl px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
              <p className={`text-lg font-black mt-0.5 ${accent} truncate`}>{value}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {['Competitors', 'Income', 'Location'].map(l => (
            <div key={l} className="bg-slate-50 rounded-xl px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{l}</p>
              <p className="text-sm font-semibold text-slate-300 mt-0.5">—</p>
            </div>
          ))}
        </div>
      )}

      {/* Local events — the real value of the platform */}
      {upcomingEvents && upcomingEvents.length > 0 && (
        <div className="mt-3 flex items-start gap-3 bg-violet-50/50 border border-violet-100 rounded-xl px-4 py-3">
          <Calendar className="w-4 h-4 text-violet-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-widest text-violet-500 mb-1">This Week Near You</p>
            <div className="space-y-1">
              {upcomingEvents.map((ev, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <div className="w-1 h-1 rounded-full bg-violet-400 mt-1.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold text-slate-700">{ev.what}</span>
                    {ev.when && <span className="text-slate-400 ml-1.5">· {ev.when}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Research insight — one key finding */}
      {researchSnippets?.keyFindings?.[0] && (
        <div className="mt-3 flex items-start gap-2.5 bg-indigo-50/50 border border-indigo-100 rounded-xl px-4 py-2.5">
          <FileText className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-indigo-700 leading-relaxed">{researchSnippets.keyFindings[0].slice(0, 150)}{researchSnippets.keyFindings[0].length > 150 ? '...' : ''}</p>
        </div>
      )}

      {/* Monitoring CTA when no local data */}
      {!stats?.population && !keyMetrics && onNominateZip && (
        <div className="mt-3 flex items-center gap-3 bg-amber-50/60 border border-amber-100 rounded-xl px-4 py-2.5">
          <p className="text-xs text-amber-700 flex-1">
            <span className="font-semibold">Enable zip monitoring</span> for weekly local pulse, govt contract alerts, and community buzz
          </p>
          <button onClick={onNominateZip} className="flex-shrink-0 bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-colors">
            Enable
          </button>
        </div>
      )}
    </Card>
  );
}
