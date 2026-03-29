'use client';

import { Globe } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import type { SeoCardData } from './types';

export function SeoCard({ seo, onRun, onExpand }: { seo: SeoCardData | null; onRun?: () => void; onExpand?: () => void }) {
  if (!seo) {
    return <LockedCard title="SEO Health" icon={Globe} action="Run SEO Check" onAction={onRun} />;
  }
  const score = seo.overallScore ?? 0;
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  const high = seo.findings?.filter(f => f.severity === 'high').length ?? 0;
  return (
    <Card className="p-6 cursor-pointer hover:shadow-md transition-shadow" onClick={onExpand}>
      <Label>SEO Health</Label>
      <div className="flex items-center gap-4 mt-4">
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="26" fill="none" stroke="#f1f5f9" strokeWidth="6" />
          <circle
            cx="32" cy="32" r="26" fill="none"
            stroke={color} strokeWidth="6"
            strokeDasharray={`${(score / 100) * 163.4} 163.4`}
            strokeLinecap="round"
            transform="rotate(-90 32 32)"
          />
          <text x="32" y="37" textAnchor="middle" fontSize="16" fontWeight="900" fill="#1e293b">{score}</text>
        </svg>
        <div>
          <p className="text-xl font-black text-slate-900">{score}/100</p>
          <p className="text-xs text-slate-400 mt-0.5">Google Presence Score</p>
          {high > 0 && (
            <p className="text-xs font-bold text-red-500 mt-1">{high} critical {high === 1 ? 'issue' : 'issues'}</p>
          )}
        </div>
      </div>
      {seo.findings?.slice(0, 3).map((f, i) => (
        <div key={i} className={`mt-2 text-xs rounded-lg px-3 py-2 font-medium flex items-center gap-2 ${f.severity === 'high' ? 'bg-red-50 text-red-700' : f.severity === 'medium' ? 'bg-amber-50 text-amber-700' : 'bg-slate-50 text-slate-600'}`}>
          <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${f.severity === 'high' ? 'bg-red-400' : f.severity === 'medium' ? 'bg-amber-400' : 'bg-slate-300'}`} />
          {f.title}
        </div>
      ))}
    </Card>
  );
}
