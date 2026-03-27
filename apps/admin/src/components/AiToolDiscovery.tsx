'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Bot,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Clock,
  Tag,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AiTool {
  toolName: string;
  vendor: string;
  category: string;
  description: string;
  pricing: string;
  isFree: boolean;
  freeAlternativeTo: string | null;
  url: string;
  aiCapability: string;
  relevanceScore: 'HIGH' | 'MEDIUM' | 'LOW';
  reputationTier: 'established' | 'emerging' | 'unknown';
  isNew: boolean;
  sourceUrl: string;
  actionForOwner: string;
}

interface RunSummary {
  id: string;
  vertical: string;
  weekOf: string;
  totalToolsFound: number;
  newToolsCount: number;
  highRelevanceCount: number;
  weeklyHighlight: { title?: string; detail?: string; action?: string };
  generatedAt: string | null;
  testMode?: boolean;
}

interface FullRun extends RunSummary {
  tools: AiTool[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(val: string | null | undefined): string {
  if (!val) return '';
  const d = new Date(!val.includes('T') ? val + 'Z' : val);
  if (isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const h = Math.floor(diff / 3600000);
  const days = Math.floor(h / 24);
  if (days > 0) return `${days}d ago`;
  if (h > 0) return `${h}h ago`;
  return 'just now';
}

const RELEVANCE_STYLES: Record<string, string> = {
  HIGH: 'bg-emerald-100 text-emerald-700',
  MEDIUM: 'bg-amber-100 text-amber-700',
  LOW: 'bg-gray-100 text-gray-500',
};

// ─── Tool Card ────────────────────────────────────────────────────────────────

function ToolCard({ tool }: { tool: AiTool }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2.5 hover:border-indigo-200 transition-colors">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-sm text-gray-900 truncate">{tool.toolName}</span>
            {tool.isFree && (
              <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full">
                Free
              </span>
            )}
            {tool.isNew && (
              <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded-full">
                New
              </span>
            )}
            {tool.reputationTier === 'established' && (
              <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full">
                Established
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{tool.vendor} · {tool.category.replace(/_/g, ' ')}</p>
        </div>
        <span className={`shrink-0 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${RELEVANCE_STYLES[tool.relevanceScore] || RELEVANCE_STYLES.LOW}`}>
          {tool.relevanceScore}
        </span>
      </div>

      {/* Description */}
      <p className="text-xs text-gray-600 leading-relaxed">{tool.description}</p>

      {/* Free alternative callout */}
      {tool.freeAlternativeTo && (
        <div className="bg-emerald-50 border border-emerald-100 rounded-md px-3 py-2">
          <p className="text-xs text-emerald-700">
            <span className="font-semibold">Free alternative to</span> {tool.freeAlternativeTo}
          </p>
        </div>
      )}

      {/* AI Capability */}
      <div className="bg-indigo-50 rounded-md px-3 py-2">
        <p className="text-[10px] font-semibold text-indigo-500 uppercase tracking-wide mb-0.5">AI Capability</p>
        <p className="text-xs text-indigo-700">{tool.aiCapability}</p>
      </div>

      {/* Action */}
      <div className="bg-amber-50 rounded-md px-3 py-2">
        <p className="text-[10px] font-semibold text-amber-500 uppercase tracking-wide mb-0.5">Action for Owner</p>
        <p className="text-xs text-amber-700">{tool.actionForOwner}</p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-0.5">
        <span className="text-xs text-gray-400">{tool.pricing}</span>
        <a
          href={tool.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          Open <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
}

// ─── Vertical Panel ───────────────────────────────────────────────────────────

function VerticalPanel({
  vertical,
  summary,
  onGenerate,
  generating,
}: {
  vertical: string;
  summary: RunSummary | null;
  onGenerate: (v: string) => void;
  generating: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [fullRun, setFullRun] = useState<FullRun | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);

  const loadFull = useCallback(async () => {
    if (fullRun || loadingFull) return;
    setLoadingFull(true);
    try {
      const res = await fetch(`/api/ai-tool-discovery/${vertical}/latest`);
      if (res.ok) setFullRun(await res.json());
    } finally {
      setLoadingFull(false);
    }
  }, [vertical, fullRun, loadingFull]);

  const handleExpand = () => {
    if (!expanded) loadFull();
    setExpanded(v => !v);
  };

  const freeCount = fullRun?.tools?.filter(t => t.isFree).length ?? 0;

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between gap-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center text-base font-bold">
            {vertical[0].toUpperCase()}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm capitalize">{vertical}</h3>
            {summary ? (
              <div className="flex items-center gap-1 text-xs text-gray-400">
                <Clock className="w-3 h-3" />
                <span>{summary.weekOf} · {timeAgo(summary.generatedAt)}</span>
                {summary.testMode && (
                  <span className="ml-1 bg-amber-100 text-amber-600 text-[10px] font-bold px-1.5 py-0.5 rounded-full">TEST</span>
                )}
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">No run this week</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {summary && (
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span><span className="font-semibold text-gray-800">{summary.totalToolsFound}</span> tools</span>
              <span><span className="font-semibold text-emerald-600">{summary.newToolsCount}</span> new</span>
              <span><span className="font-semibold text-indigo-600">{summary.highRelevanceCount}</span> high</span>
            </div>
          )}
          <button
            onClick={() => onGenerate(vertical)}
            disabled={generating}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-700 hover:bg-indigo-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Bot className="w-3 h-3" />}
            {generating ? 'Running…' : 'Run Now'}
          </button>
          {summary && (
            <button
              onClick={handleExpand}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              title={expanded ? 'Collapse' : 'Expand tools'}
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Weekly highlight — always visible when summary exists */}
      {summary?.weeklyHighlight?.title && (
        <div className="px-5 py-3 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-indigo-100">
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span className="text-[10px] font-semibold text-indigo-500 uppercase tracking-widest">Weekly Highlight</span>
          </div>
          <p className="text-xs font-semibold text-gray-800">{summary.weeklyHighlight.title}</p>
          {summary.weeklyHighlight.action && (
            <p className="text-xs text-indigo-600 mt-0.5">{summary.weeklyHighlight.action}</p>
          )}
        </div>
      )}

      {/* Expanded tool list */}
      {expanded && (
        <div className="px-5 py-4">
          {loadingFull ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-28 bg-gray-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : fullRun?.tools?.length ? (
            <>
              {freeCount > 0 && (
                <div className="mb-3 flex items-center gap-2">
                  <Tag className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-xs font-semibold text-emerald-700">
                    {freeCount} free tool{freeCount !== 1 ? 's' : ''} found this week
                  </span>
                </div>
              )}
              <div className="grid gap-3 grid-cols-1 lg:grid-cols-2">
                {fullRun.tools.map((tool, idx) => (
                  <ToolCard key={`${tool.toolName}-${idx}`} tool={tool} />
                ))}
              </div>
            </>
          ) : (
            <p className="text-xs text-gray-400 italic text-center py-6">No tools found in this run.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

// Hardcoded for Phase 1 — will be driven by registered industries in Phase 2
const VERTICALS = ['restaurant', 'bakery', 'barber'];

export default function AiToolDiscovery() {
  const [summaries, setSummaries] = useState<Record<string, RunSummary | null>>({});
  const [generating, setGenerating] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  const loadSummaries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/ai-tool-discovery?limit=50');
      if (!res.ok) throw new Error(`Failed to load runs: ${res.status}`);
      const runs: RunSummary[] = await res.json();

      // Keep the most recent run per vertical
      const byVertical: Record<string, RunSummary | null> = {};
      for (const v of VERTICALS) byVertical[v] = null;
      for (const run of runs) {
        const existing = byVertical[run.vertical];
        if (
          byVertical[run.vertical] !== undefined &&
          (!existing || (run.generatedAt ?? '') > (existing.generatedAt ?? ''))
        ) {
          byVertical[run.vertical] = run;
        }
      }
      setSummaries(byVertical);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSummaries(); }, [loadSummaries]);

  const handleGenerate = async (vertical: string) => {
    setGenerating(g => ({ ...g, [vertical]: true }));
    try {
      const res = await fetch(`/api/ai-tool-discovery/${vertical}/generate-now`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true, testMode: false }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail || 'Generation failed');
      }
      const data = await res.json();
      showToast(
        `${vertical}: ${data.totalToolsFound} tools found (${data.freeToolsCount ?? 0} free, ${data.highRelevanceCount} high relevance)`
      );
      await loadSummaries();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(g => ({ ...g, [vertical]: false }));
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-gray-900 text-white text-sm font-medium px-5 py-3 rounded-xl shadow-xl animate-in fade-in slide-in-from-bottom-2 duration-200">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-100 rounded-lg">
            <Bot className="w-5 h-5 text-indigo-700" />
          </div>
          <div>
            <h2 className="font-bold text-gray-900">AI Tool Discovery</h2>
            <p className="text-sm text-gray-500">
              Weekly AI tool landscape per vertical — runs Tuesdays · Highlights free alternatives to paid tools
            </p>
          </div>
        </div>
        <button
          onClick={loadSummaries}
          disabled={loading}
          className="inline-flex items-center gap-1.5 text-sm font-semibold px-3 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {VERTICALS.map(v => (
            <div key={v} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {VERTICALS.map(v => (
            <VerticalPanel
              key={v}
              vertical={v}
              summary={summaries[v] ?? null}
              onGenerate={handleGenerate}
              generating={generating[v] ?? false}
            />
          ))}
        </div>
      )}
    </div>
  );
}
