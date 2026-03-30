'use client';

import type { Competitor } from './types';

export function CompetitorsStrip({ competitors }: { competitors: Competitor[] | null | undefined }) {
  if (!competitors?.length) return null;
  return (
    <div className="flex items-center gap-2 overflow-hidden">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex-shrink-0">
        {competitors.length} rivals:
      </span>
      <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
        {competitors.map((c, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 bg-white border border-slate-100 rounded-full px-2.5 py-0.5 text-[11px] text-slate-600 shadow-sm whitespace-nowrap flex-shrink-0"
          >
            <span className="font-semibold text-slate-700">{c.name}</span>
            <span className="text-slate-300">
              {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
