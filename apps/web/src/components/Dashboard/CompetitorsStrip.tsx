'use client';

import type { Competitor } from './types';

export function CompetitorsStrip({ competitors }: { competitors: Competitor[] | null | undefined }) {
  if (!competitors?.length) return null;
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex-shrink-0">
        {competitors.length} nearby rivals:
      </span>
      {competitors.map((c, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1.5 bg-white border border-slate-100 rounded-full px-3 py-1 text-xs text-slate-600 shadow-sm"
        >
          <span className="font-semibold text-slate-800">{c.name}</span>
          <span className="text-slate-400">
            {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}
          </span>
        </span>
      ))}
    </div>
  );
}
