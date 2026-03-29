'use client';

import { Cpu, Zap, ExternalLink, ChevronRight, Sparkles } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import FeedbackButton from '@/components/Feedback/FeedbackButton';
import type { AiTool } from './types';

export function AiToolsCard({
  tools,
  businessSlug,
  zipCode,
  vertical,
}: {
  tools: AiTool[] | null | undefined;
  businessSlug?: string;
  zipCode?: string;
  vertical?: string;
}) {
  if (!tools?.length) {
    return <LockedCard title="AI & Tech Tools" icon={Cpu} action="Load Business" />;
  }
  return (
    <Card className="p-6 border-l-4 border-violet-500 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <div>
          <Label>AI & Tech Tools</Label>
          <h3 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Your Competitors Are Adopting</h3>
        </div>
        <Sparkles className="w-4 h-4 text-violet-400 flex-shrink-0 ml-4" />
      </div>
      <div className="flex-1 grid grid-cols-2 gap-3">
        {tools.map((t, i) => {
          // Strip markdown bold markers from tool names
          const toolName = t.tool.replace(/\*\*/g, '');
          return (
          <div key={i} className="rounded-xl border border-slate-100 p-4 hover:border-purple-200 hover:bg-purple-50/30 transition-all group flex flex-col">
            <div className="flex items-start justify-between gap-1 mb-2">
              <div className="flex items-center gap-2.5 min-w-0">
                {t.url ? (
                  <img
                    src={`${new URL(t.url).origin}/favicon.ico`}
                    alt=""
                    className="w-5 h-5 rounded object-contain flex-shrink-0"
                    onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : (
                  <div className="w-5 h-5 rounded bg-purple-100 flex items-center justify-center flex-shrink-0">
                    <Zap className="w-3 h-3 text-purple-500" />
                  </div>
                )}
                {t.url ? (
                  <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-sm font-bold text-slate-800 group-hover:text-purple-700 transition-colors flex items-center gap-1 truncate">
                    {toolName} <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </a>
                ) : (
                  <span className="text-sm font-bold text-slate-800 truncate">{toolName}</span>
                )}
              </div>
              {businessSlug && (
                <FeedbackButton
                  businessSlug={businessSlug}
                  dataType="ai_tool"
                  itemId={`tool-${toolName}`}
                  itemLabel={toolName}
                  zipCode={zipCode}
                  vertical={vertical}
                  className="flex-shrink-0"
                />
              )}
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">{t.capability}</p>
            {t.actionForOwner && (
              <p className="text-[10px] font-bold text-purple-600 mt-2 flex items-center gap-1">
                <ChevronRight className="w-3 h-3" /> {t.actionForOwner}
              </p>
            )}
          </div>
        );})}
      </div>
    </Card>
  );
}
