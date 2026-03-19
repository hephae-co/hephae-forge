'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Zap,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Clock,
  TrendingUp,
  AlertTriangle,
  Calendar,
  Trash2,
  Search,
  Cloud,
  Sparkles,
  Database,
  CheckCircle2,
  XCircle,
  MinusCircle,
  SkipForward,
  Brain,
  Target,
  FileText,
  BarChart3,
  BookOpen,
  MessageSquare,
  Shield,
  Layers,
} from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────────────

interface PulseInsight {
  rank: number;
  title: string;
  analysis: string;
  recommendation: string;
  dataSources?: string[];
  signalSources?: string[];
  playbookUsed?: string;
  impactScore: number;
  impactLevel: 'high' | 'medium' | 'low';
  timeSensitivity: 'this_week' | 'this_month' | 'this_quarter';
}

interface PulseQuickStats {
  trendingSearches: string[];
  weatherOutlook: string;
  upcomingEvents: number;
  priceAlerts: number;
}

interface WeeklyPulseData {
  zipCode: string;
  businessType: string;
  weekOf: string;
  headline: string;
  insights: PulseInsight[];
  quickStats: PulseQuickStats;
}

interface PulseSummary {
  id: string;
  zipCode: string;
  businessType: string;
  weekOf: string;
  headline: string;
  insightCount: number;
  createdAt: string;
}

interface InsightCritique {
  insight_rank: number;
  obviousness_score: number;
  actionability_score: number;
  cross_signal_score: number;
  verdict: 'PASS' | 'REWRITE' | 'DROP';
  rewrite_instruction: string;
}

interface PipelineDetails {
  macroReport?: string;
  localReport?: string;
  trendNarrative?: string;
  socialPulse?: string;
  localCatalysts?: string;
  preComputedImpact?: Record<string, number>;
  matchedPlaybooks?: Array<{ name: string; category: string; play: string }>;
  critiqueResult?: { overall_pass?: boolean; insights?: InsightCritique[]; summary?: string };
  rawSignals?: Record<string, any>;
}

interface PulseDocument {
  id: string;
  zipCode: string;
  businessType: string;
  weekOf: string;
  pulse: WeeklyPulseData;
  signalsUsed: string[];
  diagnostics?: Record<string, any>;
  pipelineDetails?: PipelineDetails;
  createdAt: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const IMPACT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  high: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  medium: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  low: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
};

const TIME_LABELS: Record<string, string> = {
  this_week: 'Act this week',
  this_month: 'This month',
  this_quarter: 'This quarter',
};

const BUSINESS_TYPES = [
  'Restaurants', 'Bakeries', 'Cafes', 'Coffee Shops', 'Pizza',
  'Retail', 'Salons', 'Spas', 'Barbers', 'Grocery',
  'Boutique', 'Florist', 'Hardware', 'Pet Store',
];

// ── Collapsible Section ────────────────────────────────────────────────

function CollapsibleSection({
  title,
  icon: Icon,
  badge,
  badgeColor = 'bg-gray-100 text-gray-600',
  defaultOpen = false,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeColor?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-3.5 flex items-center gap-3 hover:bg-gray-50/50 transition-colors bg-white"
      >
        <Icon className="w-4 h-4 text-gray-400 shrink-0" />
        <span className="text-sm font-semibold text-gray-700 flex-1 text-left">{title}</span>
        {badge && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeColor}`}>{badge}</span>
        )}
        {open ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {open && <div className="border-t border-gray-100 bg-gray-50/30">{children}</div>}
    </div>
  );
}

// ── Insight Card ────────────────────────────────────────────────────────

function InsightCard({ insight, critique }: { insight: PulseInsight; critique?: InsightCritique }) {
  const [expanded, setExpanded] = useState(false);
  const colors = IMPACT_COLORS[insight.impactLevel] || IMPACT_COLORS.medium;

  return (
    <div className={`bg-white border rounded-xl shadow-sm overflow-hidden ${colors.border} border-l-4`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-5 py-4 flex items-start gap-3 hover:bg-gray-50/50 transition-colors"
      >
        <span className="text-lg font-bold text-gray-300 shrink-0 mt-0.5">#{insight.rank}</span>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-gray-900 text-sm mb-1">{insight.title}</h4>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full border ${colors.bg} ${colors.text} ${colors.border} font-medium`}>
              {insight.impactLevel} impact
            </span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {TIME_LABELS[insight.timeSensitivity] || insight.timeSensitivity}
            </span>
            <span className="text-xs font-mono text-gray-400">Score: {insight.impactScore}</span>
            {insight.playbookUsed && (
              <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full border border-indigo-100">
                {insight.playbookUsed}
              </span>
            )}
            {critique && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                critique.verdict === 'PASS' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
              }`}>
                {critique.verdict}
              </span>
            )}
          </div>
        </div>
        {expanded ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0 mt-1" /> : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-1" />}
      </button>

      {expanded && (
        <div className="px-5 pb-5 pt-0 border-t border-gray-100 space-y-3">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Analysis</p>
            <p className="text-sm text-gray-700 leading-relaxed">{insight.analysis}</p>
          </div>
          <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">Recommendation</p>
            <p className="text-sm text-indigo-900 leading-relaxed">{insight.recommendation}</p>
          </div>
          {(insight.dataSources?.length || insight.signalSources?.length) ? (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs text-gray-400">Sources:</span>
              {(insight.signalSources || insight.dataSources || []).map((src, i) => (
                <span key={i} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{src}</span>
              ))}
            </div>
          ) : null}
          {critique && (
            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-100">
              <div className="text-center">
                <p className="text-xs text-gray-400">Obviousness</p>
                <p className={`text-lg font-bold ${critique.obviousness_score < 30 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {critique.obviousness_score}
                </p>
                <p className="text-[10px] text-gray-400">&lt;30 to pass</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-400">Actionability</p>
                <p className={`text-lg font-bold ${critique.actionability_score >= 70 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {critique.actionability_score}
                </p>
                <p className="text-[10px] text-gray-400">&ge;70 to pass</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-400">Cross-Signal</p>
                <p className={`text-lg font-bold ${critique.cross_signal_score >= 60 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {critique.cross_signal_score}
                </p>
                <p className="text-[10px] text-gray-400">&ge;60 to pass</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Quick Stats ─────────────────────────────────────────────────────────

function QuickStatsBar({ stats }: { stats: PulseQuickStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[
        { icon: Search, label: 'Trending', value: stats.trendingSearches?.[0] || 'None', color: 'blue' },
        { icon: Cloud, label: 'Weather', value: stats.weatherOutlook || 'N/A', color: 'sky' },
        { icon: Calendar, label: 'Events', value: String(stats.upcomingEvents ?? 0), color: 'purple' },
        { icon: AlertTriangle, label: 'Price Alerts', value: String(stats.priceAlerts ?? 0), color: 'amber' },
      ].map(({ icon: Icon, label, value, color }) => (
        <div key={label} className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2.5">
          <div className={`p-1.5 bg-${color}-50 rounded-md`}>
            <Icon className={`w-4 h-4 text-${color}-500`} />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-gray-500">{label}</p>
            <p className="text-sm font-medium text-gray-900 truncate">{value}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Prose Block (for expert reports) ───────────────────────────────────

function ProseBlock({ text }: { text: string }) {
  if (!text) return <p className="text-sm text-gray-400 italic px-5 py-4">No data available</p>;
  return (
    <div className="px-5 py-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
      {text}
    </div>
  );
}

// ── JSON Viewer ────────────────────────────────────────────────────────

function JsonBlock({ data, maxHeight = 'max-h-64' }: { data: any; maxHeight?: string }) {
  if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) {
    return <p className="text-sm text-gray-400 italic px-5 py-4">No data</p>;
  }
  return (
    <pre className={`px-5 py-4 text-xs text-gray-600 bg-gray-50 overflow-auto ${maxHeight} font-mono`}>
      {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
    </pre>
  );
}

// ── Pulse Viewer ────────────────────────────────────────────────────────

function PulseViewer({ doc, onBack }: { doc: PulseDocument; onBack: () => void }) {
  const pulse = doc.pulse;
  const pd = doc.pipelineDetails || {};
  const critique = pd.critiqueResult || {};
  const critiqueInsights = critique.insights || [];

  // Map critique insights by rank for lookup
  const critiqueByRank: Record<number, InsightCritique> = {};
  critiqueInsights.forEach(ic => { critiqueByRank[ic.insight_rank] = ic; });

  const duration = doc.diagnostics?.startedAt && doc.diagnostics?.completedAt
    ? `${((new Date(doc.diagnostics.completedAt).getTime() - new Date(doc.diagnostics.startedAt).getTime()) / 1000).toFixed(1)}s`
    : '';

  return (
    <div className="space-y-5 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <button onClick={onBack} className="text-sm text-indigo-600 hover:text-indigo-500 font-medium shrink-0">
          &larr; Back to list
        </button>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {duration && <span>{duration}</span>}
          {doc.signalsUsed?.length > 0 && <span>{doc.signalsUsed.length} signals</span>}
          <span>{relativeTime(doc.createdAt)}</span>
        </div>
      </div>

      {/* Headline card */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-6 text-white shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-5 h-5" />
          <span className="text-sm font-medium opacity-80">Weekly Pulse</span>
          <span className="text-sm opacity-60">|</span>
          <span className="text-sm opacity-80">{pulse.zipCode} &middot; {pulse.businessType} &middot; {pulse.weekOf}</span>
        </div>
        <h2 className="text-xl font-bold leading-tight">{pulse.headline}</h2>
      </div>

      {/* Quick stats */}
      {pulse.quickStats && <QuickStatsBar stats={pulse.quickStats} />}

      {/* ═══ INSIGHTS (with critique scores) ═══ */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          Insights ({pulse.insights?.length || 0})
          {critique.overall_pass !== undefined && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              critique.overall_pass ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
            }`}>
              Critique: {critique.overall_pass ? 'PASSED' : 'REVISED'}
            </span>
          )}
        </h3>
        {pulse.insights?.length ? (
          pulse.insights.map((insight, i) => (
            <InsightCard key={i} insight={insight} critique={critiqueByRank[insight.rank]} />
          ))
        ) : (
          <div className="text-center py-10 border border-dashed border-gray-300 rounded-xl text-gray-400 text-sm">
            No insights generated.
          </div>
        )}
      </div>

      {/* ═══ PIPELINE DETAILS ═══ */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Layers className="w-4 h-4" />
          Pipeline Details
        </h3>

        {/* Stage 1: Raw Signals */}
        <CollapsibleSection
          title="Stage 1: Raw Signals"
          icon={Database}
          badge={`${Object.keys(pd.rawSignals || {}).length} sources`}
          badgeColor="bg-blue-50 text-blue-600"
        >
          {pd.rawSignals && Object.entries(pd.rawSignals).length > 0 ? (
            <div className="divide-y divide-gray-100">
              {Object.entries(pd.rawSignals).map(([key, value]) => (
                <RawSignalRow key={key} name={key} data={value} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic px-5 py-4">No raw signals captured</p>
          )}
        </CollapsibleSection>

        {/* Stage 1: Pre-Computed Impact */}
        <CollapsibleSection
          title="Pre-Computed Impact Multipliers"
          icon={BarChart3}
          badge={`${Object.keys(pd.preComputedImpact || {}).length} vars`}
          badgeColor="bg-purple-50 text-purple-600"
        >
          {pd.preComputedImpact && Object.keys(pd.preComputedImpact).length > 0 ? (
            <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(pd.preComputedImpact).map(([key, val]) => (
                <div key={key} className="bg-white border border-gray-100 rounded-lg p-2.5">
                  <p className="text-[11px] text-gray-400 font-mono truncate">{key}</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {typeof val === 'number' ? (Math.abs(val) < 1 ? `${(val * 100).toFixed(1)}%` : val.toLocaleString()) : String(val)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400 italic px-5 py-4">No impact multipliers computed</p>
          )}
        </CollapsibleSection>

        {/* Stage 1: Matched Playbooks */}
        {(pd.matchedPlaybooks?.length ?? 0) > 0 && (
          <CollapsibleSection
            title="Matched Playbooks"
            icon={Target}
            badge={`${pd.matchedPlaybooks!.length} matched`}
            badgeColor="bg-indigo-50 text-indigo-600"
          >
            <div className="px-5 py-4 space-y-3">
              {pd.matchedPlaybooks!.map((pb, i) => (
                <div key={i} className="bg-white border border-gray-100 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-semibold text-indigo-600">{pb.name}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{pb.category}</span>
                  </div>
                  <p className="text-sm text-gray-700">{pb.play}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {/* Stage 2: Economist Report */}
        <CollapsibleSection title="Stage 2: Economist Report" icon={BarChart3} badge={pd.macroReport ? 'Available' : 'Empty'} badgeColor={pd.macroReport ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.macroReport || ''} />
        </CollapsibleSection>

        {/* Stage 2: Local Scout Report */}
        <CollapsibleSection title="Stage 2: Local Scout Report" icon={Search} badge={pd.localReport ? 'Available' : 'Empty'} badgeColor={pd.localReport ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.localReport || ''} />
        </CollapsibleSection>

        {/* Stage 2: Trend Narrative */}
        <CollapsibleSection title="Stage 2: Trend Narrative" icon={TrendingUp} badge={pd.trendNarrative ? 'Available' : 'Empty'} badgeColor={pd.trendNarrative ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.trendNarrative || ''} />
        </CollapsibleSection>

        {/* Stage 1: Social Pulse */}
        <CollapsibleSection title="Stage 1: Social Pulse (LLM Research)" icon={MessageSquare} badge={pd.socialPulse ? 'Available' : 'Empty'} badgeColor={pd.socialPulse ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.socialPulse || ''} />
        </CollapsibleSection>

        {/* Stage 1: Local Catalysts */}
        <CollapsibleSection title="Stage 1: Local Catalysts (LLM Research)" icon={FileText} badge={pd.localCatalysts ? 'Available' : 'Empty'} badgeColor={pd.localCatalysts ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.localCatalysts || ''} />
        </CollapsibleSection>

        {/* Stage 4: Full Critique Result */}
        {critiqueInsights.length > 0 && (
          <CollapsibleSection
            title="Stage 4: Critique Scores"
            icon={Shield}
            badge={critique.overall_pass ? 'ALL PASS' : 'REVISED'}
            badgeColor={critique.overall_pass ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}
          >
            <div className="px-5 py-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-400 uppercase">
                    <th className="text-left py-1">Insight</th>
                    <th className="text-center py-1">Obvious</th>
                    <th className="text-center py-1">Actionable</th>
                    <th className="text-center py-1">Cross-Signal</th>
                    <th className="text-center py-1">Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {critiqueInsights.map((ic, i) => (
                    <tr key={i}>
                      <td className="py-2 text-gray-700">#{ic.insight_rank}</td>
                      <td className={`py-2 text-center font-mono font-bold ${ic.obviousness_score < 30 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {ic.obviousness_score}
                      </td>
                      <td className={`py-2 text-center font-mono font-bold ${ic.actionability_score >= 70 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {ic.actionability_score}
                      </td>
                      <td className={`py-2 text-center font-mono font-bold ${ic.cross_signal_score >= 60 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {ic.cross_signal_score}
                      </td>
                      <td className="py-2 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          ic.verdict === 'PASS' ? 'bg-emerald-50 text-emerald-700' :
                          ic.verdict === 'DROP' ? 'bg-red-50 text-red-700' :
                          'bg-amber-50 text-amber-700'
                        }`}>
                          {ic.verdict}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>
        )}
      </div>
    </div>
  );
}

// ── Raw Signal Row (expandable) ────────────────────────────────────────

function RawSignalRow({ name, data }: { name: string; data: any }) {
  const [open, setOpen] = useState(false);
  const preview = typeof data === 'string'
    ? data.slice(0, 80)
    : JSON.stringify(data).slice(0, 80);

  return (
    <div>
      <button onClick={() => setOpen(!open)} className="w-full px-5 py-3 flex items-center gap-3 hover:bg-gray-50/50 text-left">
        <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
        <span className="text-sm font-medium text-gray-800 w-40 shrink-0">{name}</span>
        <span className="text-xs text-gray-400 truncate flex-1">{preview}...</span>
        {open ? <ChevronDown className="w-3.5 h-3.5 text-gray-300 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-300 shrink-0" />}
      </button>
      {open && (
        <div className="px-5 pb-3 pl-12">
          <pre className="text-xs text-gray-500 bg-white rounded-lg p-3 overflow-x-auto max-h-48 border border-gray-100">
            {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function WeeklyPulse() {
  const [zipCode, setZipCode] = useState('');
  const [businessType, setBusinessType] = useState('Restaurants');
  const [weekOf, setWeekOf] = useState(() => new Date().toISOString().split('T')[0]);
  const [testMode, setTestMode] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genStatus, setGenStatus] = useState('');

  const [pulses, setPulses] = useState<PulseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedPulse, setSelectedPulse] = useState<PulseDocument | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchPulses = useCallback(async () => {
    try {
      const res = await fetch('/api/weekly-pulse?limit=20');
      if (res.ok) setPulses(await res.json());
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchPulses(); }, [fetchPulses]);

  const handleGenerate = async () => {
    if (!zipCode.match(/^\d{5}$/)) {
      setGenError('Enter a valid 5-digit zip code');
      return;
    }
    setGenerating(true);
    setGenError(null);
    setGenStatus('Submitting...');
    try {
      const res = await fetch('/api/weekly-pulse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zipCode, businessType, weekOf, force: true, testMode }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Submission failed' }));
        throw new Error(err.detail || 'Submission failed');
      }
      const { jobId } = await res.json();
      setGenStatus('Pipeline running...');

      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const pollRes = await fetch(`/api/weekly-pulse/jobs/${jobId}`);
        if (!pollRes.ok) continue;
        const job = await pollRes.json();

        if (job.status === 'RUNNING') {
          setGenStatus('Agents running — fetching signals, expert analysis, synthesis...');
        }

        if (job.status === 'COMPLETED') {
          setGenStatus('');
          if (job.pulse) {
            setSelectedPulse({
              id: job.pulseId || jobId,
              zipCode, businessType, weekOf,
              pulse: job.pulse,
              signalsUsed: job.signalsUsed || [],
              diagnostics: job.diagnostics || undefined,
              pipelineDetails: job.pipelineDetails || undefined,
              createdAt: new Date().toISOString(),
            });
          }
          fetchPulses();
          return;
        }
        if (job.status === 'FAILED') throw new Error(job.error || 'Generation failed');
      }
      throw new Error('Timed out after 6 minutes');
    } catch (e: any) {
      setGenError(e.message);
      setGenStatus('');
    } finally {
      setGenerating(false);
    }
  };

  const handleViewPulse = async (pulseId: string) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/weekly-pulse/id/${pulseId}`);
      if (res.ok) setSelectedPulse(await res.json());
    } catch { /* ignore */ } finally { setLoadingDetail(false); }
  };

  const handleDeletePulse = async (pulseId: string) => {
    if (!confirm('Delete this pulse?')) return;
    try {
      await fetch(`/api/weekly-pulse/id/${pulseId}`, { method: 'DELETE' });
      setPulses(prev => prev.filter(p => p.id !== pulseId));
      if (selectedPulse?.id === pulseId) setSelectedPulse(null);
    } catch { /* ignore */ }
  };

  // ── Render ──────────────────────────────────────────────────────────

  if (selectedPulse && !loadingDetail) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
        <PulseViewer doc={selectedPulse} onBack={() => setSelectedPulse(null)} />
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
      {/* Generate Form */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-bold text-gray-900">Generate Weekly Pulse</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            type="text"
            placeholder="Zip code (e.g. 07110)"
            value={zipCode}
            onChange={(e) => setZipCode(e.target.value.replace(/\D/g, '').slice(0, 5))}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
          />
          <select
            value={businessType}
            onChange={(e) => setBusinessType(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
          >
            {BUSINESS_TYPES.map(bt => <option key={bt} value={bt}>{bt}</option>)}
          </select>
          <input
            type="date"
            value={weekOf}
            onChange={(e) => setWeekOf(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
          />
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={testMode}
                onChange={(e) => setTestMode(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-amber-500 focus:ring-amber-200"
              />
              <span className="text-xs text-gray-500">Test mode</span>
              <span className="text-[10px] text-gray-400">(24h TTL)</span>
            </label>
            <button
              onClick={handleGenerate}
              disabled={generating || !zipCode}
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
            >
              {generating ? (
                <><Loader2 className="w-4 h-4 animate-spin" />Generating...</>
              ) : (
                <><Zap className="w-4 h-4" />Generate</>
              )}
            </button>
          </div>
        </div>

        {genStatus && (
          <div className="mt-3 p-3 bg-indigo-50 border border-indigo-100 rounded-lg text-indigo-700 text-sm flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            {genStatus}
          </div>
        )}

        {genError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            {genError}
          </div>
        )}
      </div>

      {/* Pulse List */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-gray-400" />
            Recent Pulses
          </h3>
          <button
            onClick={() => { setLoading(true); fetchPulses(); }}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="p-10 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
          </div>
        ) : pulses.length === 0 ? (
          <div className="p-10 text-center text-gray-400 text-sm">
            No pulses generated yet. Use the form above to create one.
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {pulses.map((pulse) => (
              <div key={pulse.id} className="px-6 py-4 flex items-center gap-4 hover:bg-gray-50/50 transition-colors group">
                <button onClick={() => handleViewPulse(pulse.id)} className="flex-1 min-w-0 text-left">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{pulse.zipCode}</span>
                    <span className="text-xs text-gray-400">{pulse.businessType}</span>
                    <span className="text-xs text-gray-300">|</span>
                    <span className="text-xs text-gray-400">{pulse.weekOf}</span>
                  </div>
                  <p className="text-sm text-gray-700 truncate">{pulse.headline || 'No headline'}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400">{pulse.insightCount} insights</span>
                    {pulse.createdAt && <span className="text-xs text-gray-300">{relativeTime(pulse.createdAt)}</span>}
                  </div>
                </button>
                <button
                  onClick={() => handleDeletePulse(pulse.id)}
                  className="p-2 text-gray-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {loadingDetail && (
        <div className="fixed inset-0 bg-white/60 z-30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      )}
    </div>
  );
}
