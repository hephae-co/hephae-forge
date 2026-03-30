'use client';

import { useState } from 'react';
import { Cpu, Zap, ExternalLink, ChevronRight, ChevronDown, Sparkles } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import FeedbackButton from '@/components/Feedback/FeedbackButton';
import type { AiTool } from './types';

interface PersonalizedTool {
  tool: string;
  reason: string;
  priority: string;
  score: number;
  url?: string;
  pricing?: string;
  isFree?: boolean;
  capability?: string;
}

export function AiToolsCard({
  tools,
  personalizedTools,
  businessSlug,
  zipCode,
  vertical,
}: {
  tools: AiTool[] | null | undefined;
  personalizedTools?: PersonalizedTool[] | null;
  businessSlug?: string;
  zipCode?: string;
  vertical?: string;
}) {
  const [showAllPersonalized, setShowAllPersonalized] = useState(false);
  const hasPersonalized = personalizedTools && personalizedTools.length > 0;
  const hasGeneric = tools && tools.length > 0;

  if (!hasPersonalized && !hasGeneric) {
    return <LockedCard title="AI & Tech Tools" icon={Cpu} action="Load Business" />;
  }

  const visiblePersonalized = hasPersonalized
    ? (showAllPersonalized ? personalizedTools! : personalizedTools!.slice(0, 3))
    : [];
  const remainingCount = hasPersonalized ? Math.max(0, personalizedTools!.length - 3) : 0;

  return (
    <Card className="p-6 border-l-4 border-violet-500 flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-xl font-bold tracking-tight text-slate-900">AI & Tech Tools</h3>
          {hasPersonalized && <p className="text-xs text-purple-500 font-medium mt-0.5">Recommended for your business</p>}
          {!hasPersonalized && <p className="text-xs text-slate-400 mt-0.5">Your competitors are adopting</p>}
        </div>
        <Sparkles className="w-4 h-4 text-violet-400 flex-shrink-0 ml-4" />
      </div>

      <div className="flex-1 space-y-2">
        {/* Personalized picks */}
        {visiblePersonalized.map((rec, i) => {
          // Only show FREE if pricing explicitly says "free" or "$0"
          const pricingLower = (rec.pricing || '').toLowerCase();
          const confirmedFree = pricingLower === 'free' || pricingLower.startsWith('free.') || pricingLower.startsWith('$0') || pricingLower === 'free plan';
          return (
          <div key={`p-${i}`} className="rounded-xl border border-purple-100 bg-purple-50/30 p-3 hover:border-purple-200 transition-all group">
            <div className="flex items-start justify-between gap-2 mb-1">
              <div className="flex items-center gap-2 min-w-0">
                {rec.url ? (
                  <img src={`${new URL(rec.url).origin}/favicon.ico`} alt="" className="w-4 h-4 rounded object-contain flex-shrink-0"
                    onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                ) : (
                  <Zap className="w-4 h-4 text-purple-500 flex-shrink-0" />
                )}
                {rec.url ? (
                  <a href={rec.url} target="_blank" rel="noopener noreferrer" className="text-sm font-bold text-slate-800 group-hover:text-purple-700 transition-colors flex items-center gap-1 truncate">
                    {rec.tool} <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </a>
                ) : (
                  <span className="text-sm font-bold text-slate-800 truncate">{rec.tool}</span>
                )}
                {confirmedFree && <span className="text-[9px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded flex-shrink-0">FREE</span>}
              </div>
              {businessSlug && (
                <FeedbackButton businessSlug={businessSlug} dataType="ai_tool" itemId={`tool-${rec.tool}`} itemLabel={rec.tool} zipCode={zipCode} vertical={vertical} className="flex-shrink-0" />
              )}
            </div>
            <p className="text-[11px] text-purple-600 font-medium">{rec.reason}</p>
            {rec.capability && <p className="text-[10px] text-slate-400 mt-0.5 leading-snug">{rec.capability.slice(0, 80)}</p>}
          </div>
        );})}

        {/* Show more / show less toggle */}
        {remainingCount > 0 && (
          <button
            onClick={() => setShowAllPersonalized(v => !v)}
            className="w-full flex items-center justify-center gap-1 text-xs text-purple-600 font-semibold py-1.5 hover:bg-purple-50 rounded-lg transition-colors"
          >
            {showAllPersonalized ? 'Show less' : `Show ${remainingCount} more`}
            <ChevronDown className={`w-3 h-3 transition-transform ${showAllPersonalized ? 'rotate-180' : ''}`} />
          </button>
        )}

        {/* Divider between personalized and generic */}
        {hasPersonalized && hasGeneric && (
          <div className="flex items-center gap-2 pt-2">
            <div className="flex-1 h-px bg-slate-100" />
            <span className="text-[9px] font-bold uppercase tracking-widest text-slate-300">Competitors are adopting</span>
            <div className="flex-1 h-px bg-slate-100" />
          </div>
        )}

        {/* Generic tools — compact list */}
        {hasGeneric && (
          <div className="space-y-2">
            {(tools ?? []).slice(0, hasPersonalized ? 3 : 4).map((t, i) => {
              const toolName = t.tool.replace(/\*\*/g, '');
              return (
                <div key={`g-${i}`} className="flex items-start gap-2.5 rounded-xl border border-slate-100 p-3 hover:border-purple-200 hover:bg-purple-50/20 transition-all group">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    {t.url ? (
                      <img src={`${new URL(t.url).origin}/favicon.ico`} alt="" className="w-4 h-4 rounded object-contain flex-shrink-0"
                        onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                    ) : (
                      <div className="w-4 h-4 rounded bg-purple-100 flex items-center justify-center flex-shrink-0">
                        <Zap className="w-2.5 h-2.5 text-purple-500" />
                      </div>
                    )}
                    <div className="min-w-0">
                      {t.url ? (
                        <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-xs font-bold text-slate-700 group-hover:text-purple-700 transition-colors flex items-center gap-1">
                          {toolName} <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                        </a>
                      ) : (
                        <span className="text-xs font-bold text-slate-700">{toolName}</span>
                      )}
                      <p className="text-[10px] text-slate-400 leading-snug mt-0.5">{t.capability?.slice(0, 60)}</p>
                    </div>
                  </div>
                  {t.actionForOwner && (
                    <p className="text-[9px] font-bold text-purple-500 flex items-center gap-0.5 flex-shrink-0">
                      <ChevronRight className="w-2.5 h-2.5" /> Action
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}
