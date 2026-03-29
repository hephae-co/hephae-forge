'use client';

import { Activity } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import type { Insight } from './types';

export function BuzzCard({ buzz, insights }: { buzz: string | null | undefined; insights: Insight[] | null | undefined }) {
  if (!buzz && !insights?.length) {
    return <LockedCard title="Community & Insights" icon={Activity} action="Load Business" />;
  }
  return (
    <Card className="p-6">
      <Label>Community Pulse</Label>
      {buzz && (
        <p className="text-sm text-slate-600 mt-3 leading-relaxed border-l-2 border-amber-400 pl-3">{buzz}</p>
      )}
      {insights?.length ? (
        <div className="mt-4 space-y-3">
          {insights.slice(0, 3).map((ins, i) => (
            <div key={i} className="rounded-xl bg-violet-50 border border-violet-100 p-3">
              <p className="text-xs font-bold text-violet-800">{ins.title}</p>
              <p className="text-xs text-violet-600 mt-0.5 leading-relaxed">{ins.recommendation}</p>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
