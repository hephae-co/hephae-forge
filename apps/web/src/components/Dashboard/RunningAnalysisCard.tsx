'use client';

import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { Card, Label } from './Card';

const CAPABILITY_LABELS: Record<string, { label: string; color: string; description: string }> = {
  surgery: { label: 'Margin Analysis', color: 'border-purple-700', description: 'Analyzing menu prices against commodity costs and local competitors...' },
  seo: { label: 'SEO Health', color: 'border-emerald-500', description: 'Auditing your Google presence across search, maps, and schema...' },
  traffic: { label: 'Foot Traffic', color: 'border-sky-500', description: 'Predicting patterns from local events, weather, and historical data...' },
  competitive: { label: 'Competitive Intel', color: 'border-orange-500', description: 'Analyzing your position against nearby competitors...' },
  marketing: { label: 'Social Audit', color: 'border-pink-500', description: 'Checking your presence across all social platforms...' },
  discovery: { label: 'Discovery', color: 'border-indigo-500', description: 'Mapping your digital presence across 12+ data sources...' },
};

export function RunningAnalysisCard({ capabilityId, startTime }: { capabilityId: string; startTime: number | null }) {
  const cap = CAPABILITY_LABELS[capabilityId] ?? { label: 'Analysis', color: 'border-purple-500', description: 'Running analysis...' };
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(id);
  }, [startTime]);

  return (
    <Card className={`p-6 border-l-4 ${cap.color} h-full flex flex-col items-center justify-center gap-4 min-h-[200px] animate-fade-in`}>
      <div className="relative">
        <div className="w-12 h-12 rounded-full bg-purple-50 flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-purple-600 animate-spin" />
        </div>
        <div className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-purple-500 animate-pulse" />
      </div>
      <div className="text-center">
        <Label>{cap.label}</Label>
        <p className="text-sm font-semibold text-slate-700 mt-2">{cap.description}</p>
        {elapsed > 5 && (
          <p className="text-[10px] text-slate-400 mt-2">{elapsed}s elapsed — complex analyses can take up to 60s</p>
        )}
      </div>
      <div className="w-32 h-1 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-purple-500 rounded-full animate-pulse" style={{ width: '60%' }} />
      </div>
    </Card>
  );
}
