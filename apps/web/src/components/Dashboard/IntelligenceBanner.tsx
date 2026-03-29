'use client';

import { Brain, ArrowRight } from 'lucide-react';
import type { Insight } from './types';

export function IntelligenceBanner({
  insight,
  onApply,
  onDismiss,
}: {
  insight: Insight | null;
  onApply?: () => void;
  onDismiss?: () => void;
}) {
  if (!insight) return null;
  return (
    <div className="fixed bottom-0 left-56 right-[420px] z-40 px-6 pb-4">
      <div className="bg-white/90 backdrop-blur-xl border border-purple-100 shadow-2xl shadow-purple-900/10 rounded-2xl p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 min-w-0">
          <div className="w-10 h-10 rounded-full bg-purple-700 flex items-center justify-center flex-shrink-0">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Intelligence Engine · {insight.title}</p>
            <p className="text-sm font-semibold text-slate-700 truncate">{insight.recommendation}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {onDismiss && (
            <button onClick={onDismiss} className="bg-slate-100 text-slate-600 px-4 py-2 rounded-lg text-xs font-bold hover:bg-slate-200 transition-colors uppercase">
              Dismiss
            </button>
          )}
          <button onClick={onApply} className="bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-bold hover:bg-purple-800 transition-colors uppercase flex items-center gap-1.5">
            Ask AI <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
