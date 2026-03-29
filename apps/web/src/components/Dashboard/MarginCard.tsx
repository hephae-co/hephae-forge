'use client';

import { DollarSign } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import type { MarginCardData } from './types';

export function MarginCard({ margin, onRun, onExpand }: { margin: MarginCardData | null; onRun?: () => void; onExpand?: () => void }) {
  if (!margin) {
    return (
      <LockedCard title="Margin Analysis" icon={DollarSign} action="Run Cost Analysis" onAction={onRun} className="min-h-[200px]" />
    );
  }
  const cats = Object.values(margin.categories ?? {});
  const scoreColor = (margin.overall_score ?? 0) >= 70 ? 'text-emerald-600' : (margin.overall_score ?? 0) >= 50 ? 'text-amber-500' : 'text-red-500';

  return (
    <Card className="p-6 border-l-4 border-purple-700 h-full flex flex-col cursor-pointer hover:shadow-md transition-shadow" onClick={onExpand}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <Label>Margin Analysis</Label>
          <h3 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Food Cost Breakdown</h3>
          {margin.top_opportunity && (
            <p className="text-slate-500 text-xs mt-1 max-w-xs leading-relaxed">{margin.top_opportunity}</p>
          )}
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          <span className={`block text-3xl font-black ${scoreColor}`}>{margin.overall_score ?? '—'}</span>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">/100</span>
          {!!margin.annual_leakage && (
            <div className="mt-0.5 text-xs font-bold text-red-500">
              ${(margin.annual_leakage / 1000).toFixed(0)}k/yr leak
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 grid grid-cols-2 gap-3">
        {cats.map((cat, i) => {
          const pct = cat.margin_pct ?? 0;
          const color = pct >= 75 ? 'bg-emerald-500' : pct >= 60 ? 'bg-purple-600' : 'bg-amber-500';
          return (
            <div key={i} className="p-4 rounded-xl bg-slate-50 border border-slate-100 flex flex-col justify-between">
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{cat.label ?? `Cat ${i + 1}`}</p>
                <p className="text-2xl font-black text-slate-900 mt-1">{pct.toFixed(1)}%</p>
              </div>
              <div>
                <div className="w-full bg-slate-200 h-1.5 mt-3 rounded-full overflow-hidden">
                  <div className={`${color} h-full rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Cost: {(cat.cost_pct ?? 0).toFixed(1)}%</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
