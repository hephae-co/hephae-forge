'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  MapPin,
  Loader2,
  RefreshCw,
  Plus,
  Trash2,
  Pause,
  Play,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Calendar,
  XCircle,
  Eye,
  FlaskConical,
  TrendingUp,
  ChevronDown,
  ChevronRight,
  Search,
  Cloud,
  Sparkles,
  Database,
  Shield,
  Layers,
  Target,
  FileText,
  BarChart3,
  BookOpen,
  MessageSquare,
  MinusCircle,
  SkipForward,
  Brain,
} from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────────────

interface RegisteredZipcode {
  id: string;
  zipCode: string;
  businessTypes: string[];
  city: string;
  state: string;
  county: string;
  status: 'active' | 'paused';
  onboardingStatus: 'onboarding' | 'onboarded';
  onboardedAt: string | null;
  registeredAt: string;
  lastPulseAt: string | null;
  lastPulseId: string | null;
  lastPulseHeadline: string;
  lastPulseInsightCount: number;
  pulseCount: number;
  nextScheduledAt: string | null;
}

interface CronRun {
  jobId: string;
  zipCode: string;
  businessType: string;
  status: string;
  createdAt: string | null;
  completedAt: string | null;
  error: string | null;
}

interface CronStatus {
  activeZipcodes: number;
  pausedZipcodes: number;
  nextRunAt: string;
  schedule: string;
  recentRuns: CronRun[];
}

interface PulseSummary {
  id: string;
  zipCode: string;
  businessType: string;
  weekOf: string;
  headline: string;
  insightCount: number;
  testMode: boolean;
  createdAt: string;
}

// ── Pulse Viewer Types ──────────────────────────────────────────────────

interface LocalEvent {
  what: string;
  where: string;
  when: string;
  businessImpact: string;
  source: string;
}

interface CompetitorNote {
  business: string;
  observation: string;
  implication: string;
  source: string;
}

interface LocalBriefing {
  thisWeekInTown?: LocalEvent[];
  competitorWatch?: CompetitorNote[];
  communityBuzz?: string;
  governmentWatch?: string;
}

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
  localBriefing?: LocalBriefing;
  insights: PulseInsight[];
  quickStats: PulseQuickStats;
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

const BUSINESS_TYPES = [
  'Restaurants', 'Bakeries', 'Cafes', 'Coffee Shops', 'Pizza',
  'Retail', 'Salons', 'Spas', 'Barbers', 'Grocery',
  'Boutique', 'Florist', 'Hardware', 'Pet Store',
];

// ── Helpers ─────────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function getNextFriday(): Date {
  const now = new Date();
  const day = now.getDay();
  const daysUntilFri = (5 - day + 7) % 7 || 7;
  const next = new Date(now);
  next.setDate(now.getDate() + daysUntilFri);
  next.setHours(6, 0, 0, 0);
  return next;
}

function formatCountdown(target: Date): string {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return 'Running now';
  const hrs = Math.floor(diff / 3600000);
  const days = Math.floor(hrs / 24);
  const remainHrs = hrs % 24;
  if (days > 0) return `${days}d ${remainHrs}h`;
  return `${hrs}h`;
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

// ── Prose Block ─────────────────────────────────────────────────────────

function ProseBlock({ text }: { text: string }) {
  if (!text) return <p className="text-sm text-gray-400 italic px-5 py-4">No data available</p>;
  return (
    <div className="px-5 py-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
      {text}
    </div>
  );
}

// ── Local Briefing Card ─────────────────────────────────────────────────

function LocalBriefingCard({ briefing, zipCode }: { briefing: LocalBriefing; zipCode: string }) {
  const events = briefing.thisWeekInTown || [];
  const competitors = briefing.competitorWatch || [];
  const buzz = briefing.communityBuzz || '';
  const gov = briefing.governmentWatch || '';

  const hasContent = events.length > 0 || competitors.length > 0 || buzz || gov;
  if (!hasContent) return null;

  return (
    <div className="border border-emerald-200 rounded-xl overflow-hidden bg-emerald-50/30">
      <div className="px-5 py-3.5 bg-emerald-50 border-b border-emerald-100 flex items-center gap-2">
        <Calendar className="w-4 h-4 text-emerald-600" />
        <h3 className="text-sm font-semibold text-emerald-800">This Week in {zipCode}</h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium">
          {events.length} events, {competitors.length} competitors
        </span>
      </div>

      <div className="p-5 space-y-4">
        {events.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Events This Week</p>
            <div className="space-y-2">
              {events.map((evt, i) => (
                <div key={i} className="bg-white border border-gray-100 rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <h4 className="text-sm font-medium text-gray-900">{evt.what}</h4>
                    {evt.when && (
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full whitespace-nowrap shrink-0">{evt.when}</span>
                    )}
                  </div>
                  {evt.where && <p className="text-xs text-gray-500 mb-1">{evt.where}</p>}
                  {evt.businessImpact && <p className="text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded">{evt.businessImpact}</p>}
                  {evt.source && <p className="text-[10px] text-gray-400 mt-1">Source: {evt.source}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {competitors.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Competitor Watch</p>
            <div className="space-y-2">
              {competitors.map((comp, i) => (
                <div key={i} className="bg-white border border-gray-100 rounded-lg p-3">
                  <h4 className="text-sm font-semibold text-gray-900 mb-0.5">{comp.business}</h4>
                  <p className="text-sm text-gray-700 mb-1">{comp.observation}</p>
                  {comp.implication && (
                    <p className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded">{comp.implication}</p>
                  )}
                  {comp.source && <p className="text-[10px] text-gray-400 mt-1">Source: {comp.source}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {buzz && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Community Buzz</p>
            <p className="text-sm text-gray-700 leading-relaxed">{buzz}</p>
          </div>
        )}

        {gov && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Government Watch</p>
            <p className="text-sm text-gray-700 leading-relaxed">{gov}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Raw Signal Row ────────────────────────────────────────────────────

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

// ── Pulse Viewer ────────────────────────────────────────────────────────

function PulseViewer({ doc, onBack, testBadge = false }: { doc: PulseDocument; onBack: () => void; testBadge?: boolean }) {
  const pulse = doc.pulse;
  const pd = doc.pipelineDetails || {};
  const critique = pd.critiqueResult || {};
  const critiqueInsights = critique.insights || [];

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
          {testBadge && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold border border-amber-200">TEST</span>
          )}
          {duration && <span>{duration}</span>}
          {doc.signalsUsed?.length > 0 && <span>{doc.signalsUsed.length} signals</span>}
          <span>{relativeTime(doc.createdAt)}</span>
        </div>
      </div>

      {/* Test mode banner */}
      {testBadge && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2 text-amber-800 text-sm">
          <FlaskConical className="w-4 h-4 shrink-0" />
          <span className="font-medium">Test Run</span>
          <span className="text-amber-600">- This data auto-deletes after 24 hours</span>
        </div>
      )}

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

      {pulse.quickStats && <QuickStatsBar stats={pulse.quickStats} />}

      {pulse.localBriefing && <LocalBriefingCard briefing={pulse.localBriefing} zipCode={pulse.zipCode} />}

      {/* Insights */}
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

      {/* Pipeline Details */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Layers className="w-4 h-4" />
          Pipeline Details
        </h3>

        <CollapsibleSection title="Stage 1: Raw Signals" icon={Database} badge={`${Object.keys(pd.rawSignals || {}).length} sources`} badgeColor="bg-blue-50 text-blue-600">
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

        <CollapsibleSection title="Pre-Computed Impact Multipliers" icon={BarChart3} badge={`${Object.keys(pd.preComputedImpact || {}).length} vars`} badgeColor="bg-purple-50 text-purple-600">
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

        {(pd.matchedPlaybooks?.length ?? 0) > 0 && (
          <CollapsibleSection title="Matched Playbooks" icon={Target} badge={`${pd.matchedPlaybooks!.length} matched`} badgeColor="bg-indigo-50 text-indigo-600">
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

        <CollapsibleSection title="Stage 2: Economist Report" icon={BarChart3} badge={pd.macroReport ? 'Available' : 'Empty'} badgeColor={pd.macroReport ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.macroReport || ''} />
        </CollapsibleSection>

        <CollapsibleSection title="Stage 2: Local Scout Report" icon={Search} badge={pd.localReport ? 'Available' : 'Empty'} badgeColor={pd.localReport ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.localReport || ''} />
        </CollapsibleSection>

        <CollapsibleSection title="Stage 2: Trend Narrative" icon={TrendingUp} badge={pd.trendNarrative ? 'Available' : 'Empty'} badgeColor={pd.trendNarrative ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.trendNarrative || ''} />
        </CollapsibleSection>

        <CollapsibleSection title="Stage 1: Social Pulse (LLM Research)" icon={MessageSquare} badge={pd.socialPulse ? 'Available' : 'Empty'} badgeColor={pd.socialPulse ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.socialPulse || ''} />
        </CollapsibleSection>

        <CollapsibleSection title="Stage 1: Local Catalysts (LLM Research)" icon={FileText} badge={pd.localCatalysts ? 'Available' : 'Empty'} badgeColor={pd.localCatalysts ? 'bg-emerald-50 text-emerald-600' : 'bg-gray-100 text-gray-400'}>
          <ProseBlock text={pd.localCatalysts || ''} />
        </CollapsibleSection>

        {critiqueInsights.length > 0 && (
          <CollapsibleSection title="Stage 4: Critique Scores" icon={Shield} badge={critique.overall_pass ? 'ALL PASS' : 'REVISED'} badgeColor={critique.overall_pass ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}>
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

// ══════════════════════════════════════════════════════════════════════════
// ── MAIN COMPONENT ─────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════

export default function RegisteredZipcodes({ activeSubTab }: { activeSubTab: 'onboarded' | 'weekly' | 'tests' }) {
  // ── Shared state ──────────────────────────────────────────────────────
  const [zipcodes, setZipcodes] = useState<RegisteredZipcode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Pulse viewer state (shared across sub-tabs)
  const [selectedPulse, setSelectedPulse] = useState<PulseDocument | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [viewingTestPulse, setViewingTestPulse] = useState(false);

  // ── Onboarded tab state ───────────────────────────────────────────────
  const [zipInput, setZipInput] = useState('');
  const [registering, setRegistering] = useState(false);
  const [regSuccess, setRegSuccess] = useState<string | null>(null);
  const [cronStatus, setCronStatus] = useState<CronStatus | null>(null);
  const [cronLoading, setCronLoading] = useState(true);

  // ── Weekly runs state ─────────────────────────────────────────────────
  const [productionPulses, setProductionPulses] = useState<PulseSummary[]>([]);
  const [productionLoading, setProductionLoading] = useState(true);
  const [showAllHistory, setShowAllHistory] = useState(false);

  // ── Test runs state ───────────────────────────────────────────────────
  const [testZipCode, setTestZipCode] = useState('');
  const [testBizType, setTestBizType] = useState('Restaurants');
  const [testWeekOf, setTestWeekOf] = useState(() => new Date().toISOString().split('T')[0]);
  const [testGenerating, setTestGenerating] = useState(false);
  const [testGenError, setTestGenError] = useState<string | null>(null);
  const [testGenStatus, setTestGenStatus] = useState('');
  const [testPulses, setTestPulses] = useState<PulseSummary[]>([]);
  const [testPulsesLoading, setTestPulsesLoading] = useState(true);

  // ── Fetch functions ───────────────────────────────────────────────────

  const fetchZipcodes = useCallback(async () => {
    try {
      const res = await fetch('/api/registered-zipcodes');
      if (res.ok) setZipcodes(await res.json());
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  const fetchCronStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/registered-zipcodes/cron-status');
      if (res.ok) setCronStatus(await res.json());
    } catch { /* ignore */ } finally { setCronLoading(false); }
  }, []);

  const fetchProductionPulses = useCallback(async () => {
    try {
      const res = await fetch('/api/weekly-pulse?limit=50&testMode=false');
      if (res.ok) setProductionPulses(await res.json());
    } catch { /* ignore */ } finally { setProductionLoading(false); }
  }, []);

  const fetchTestPulses = useCallback(async () => {
    try {
      const res = await fetch('/api/weekly-pulse?limit=20&testMode=true');
      if (res.ok) setTestPulses(await res.json());
    } catch { /* ignore */ } finally { setTestPulsesLoading(false); }
  }, []);

  useEffect(() => {
    fetchZipcodes();
    fetchCronStatus();
  }, [fetchZipcodes, fetchCronStatus]);

  useEffect(() => {
    if (activeSubTab === 'weekly') fetchProductionPulses();
    if (activeSubTab === 'tests') fetchTestPulses();
  }, [activeSubTab, fetchProductionPulses, fetchTestPulses]);

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleRegister = async () => {
    // Parse multiple zip codes (comma, space, or newline separated)
    const zips = zipInput
      .split(/[\s,]+/)
      .map(z => z.trim())
      .filter(z => /^\d{5}$/.test(z));

    if (zips.length === 0) {
      setError('Enter one or more valid 5-digit zip codes');
      return;
    }

    setRegistering(true);
    setError(null);
    setRegSuccess(null);

    const results: string[] = [];
    const errors: string[] = [];

    // Register all in parallel
    await Promise.allSettled(
      zips.map(async (zip) => {
        try {
          const res = await fetch('/api/registered-zipcodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ zipCode: zip }),
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Failed' }));
            errors.push(`${zip}: ${err.detail || 'Failed'}`);
            return;
          }
          const data = await res.json();
          results.push(`${zip} (${data.city}, ${data.state})`);
        } catch (e: any) {
          errors.push(`${zip}: ${e.message}`);
        }
      })
    );

    if (results.length > 0) {
      setRegSuccess(`Registered ${results.length} zipcode${results.length > 1 ? 's' : ''}: ${results.join(', ')}`);
    }
    if (errors.length > 0) {
      setError(errors.join(' | '));
    }
    setZipInput('');
    fetchZipcodes();
    setRegistering(false);
  };

  const handleUnregister = async (zip: RegisteredZipcode) => {
    if (!confirm(`Unregister ${zip.zipCode}? This cannot be undone.`)) return;
    const key = `del-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(`/api/registered-zipcodes/${zip.zipCode}`, { method: 'DELETE' });
      if (res.ok) setZipcodes(prev => prev.filter(z => z.id !== zip.id));
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleToggleStatus = async (zip: RegisteredZipcode) => {
    const action = zip.status === 'active' ? 'pause' : 'resume';
    const key = `toggle-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(`/api/registered-zipcodes/${zip.zipCode}/${action}`, { method: 'POST' });
      if (res.ok) {
        setZipcodes(prev => prev.map(z =>
          z.id === zip.id ? { ...z, status: action === 'pause' ? 'paused' : 'active' } : z
        ));
      }
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleApprove = async (zip: RegisteredZipcode) => {
    const key = `approve-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(`/api/registered-zipcodes/${zip.zipCode}/approve`, { method: 'POST' });
      if (res.ok) {
        setZipcodes(prev => prev.map(z =>
          z.id === zip.id ? { ...z, onboardingStatus: 'onboarded' as const, onboardedAt: new Date().toISOString() } : z
        ));
      }
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleRunNow = async (zip: RegisteredZipcode) => {
    const key = `run-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch('/api/weekly-pulse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zipCode: zip.zipCode,
          businessType: (zip.businessTypes || ['Restaurants'])[0],
          force: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to trigger pulse');
      const { jobId } = await res.json();

      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const pollRes = await fetch(`/api/weekly-pulse/jobs/${jobId}`);
        if (!pollRes.ok) continue;
        const job = await pollRes.json();
        if (job.status === 'COMPLETED') {
          fetchZipcodes();
          return;
        }
        if (job.status === 'FAILED') throw new Error(job.error || 'Pulse generation failed');
      }
      throw new Error('Timed out');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleViewPulse = async (pulseId: string, isTest = false) => {
    setLoadingDetail(true);
    setViewingTestPulse(isTest);
    try {
      const res = await fetch(`/api/weekly-pulse/id/${pulseId}`);
      if (res.ok) setSelectedPulse(await res.json());
    } catch { /* ignore */ } finally { setLoadingDetail(false); }
  };

  const handleDeletePulse = async (pulseId: string, isTest = false) => {
    if (!confirm('Delete this pulse?')) return;
    try {
      await fetch(`/api/weekly-pulse/id/${pulseId}`, { method: 'DELETE' });
      if (isTest) {
        setTestPulses(prev => prev.filter(p => p.id !== pulseId));
      } else {
        setProductionPulses(prev => prev.filter(p => p.id !== pulseId));
      }
      if (selectedPulse?.id === pulseId) setSelectedPulse(null);
    } catch { /* ignore */ }
  };

  const handleTestGenerate = async () => {
    if (!testZipCode.match(/^\d{5}$/)) {
      setTestGenError('Enter a valid 5-digit zip code');
      return;
    }
    setTestGenerating(true);
    setTestGenError(null);
    setTestGenStatus('Submitting...');
    try {
      const res = await fetch('/api/weekly-pulse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zipCode: testZipCode, businessType: testBizType, weekOf: testWeekOf, force: true, testMode: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Submission failed' }));
        throw new Error(err.detail || 'Submission failed');
      }
      const { jobId } = await res.json();
      setTestGenStatus(`Pipeline running — Job: ${jobId}`);

      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        const pollRes = await fetch(`/api/weekly-pulse/jobs/${jobId}`);
        if (!pollRes.ok) continue;
        const job = await pollRes.json();

        if (job.status === 'RUNNING') {
          setTestGenStatus(`Agents running — Job: ${jobId}`);
        }

        if (job.status === 'COMPLETED') {
          setTestGenStatus('');
          if (job.pulse) {
            setViewingTestPulse(true);
            setSelectedPulse({
              id: job.pulseId || jobId,
              zipCode: testZipCode,
              businessType: testBizType,
              weekOf: testWeekOf,
              pulse: job.pulse,
              signalsUsed: job.signalsUsed || [],
              diagnostics: job.diagnostics || undefined,
              pipelineDetails: job.pipelineDetails || undefined,
              createdAt: new Date().toISOString(),
            });
          }
          fetchTestPulses();
          return;
        }
        if (job.status === 'FAILED') throw new Error(job.error || 'Generation failed');
      }
      throw new Error('Timed out after 6 minutes');
    } catch (e: any) {
      setTestGenError(e.message);
      setTestGenStatus('');
    } finally {
      setTestGenerating(false);
    }
  };

  // ── If viewing a pulse detail, show it ───────────────────────────────

  if (selectedPulse && !loadingDetail) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
        <PulseViewer doc={selectedPulse} onBack={() => setSelectedPulse(null)} testBadge={viewingTestPulse} />
      </div>
    );
  }

  // ── Derived data ──────────────────────────────────────────────────────

  const activeCount = zipcodes.filter(z => z.status === 'active').length;
  const pausedCount = zipcodes.filter(z => z.status === 'paused').length;
  const onboardingCount = zipcodes.filter(z => z.onboardingStatus === 'onboarding').length;
  const onboardedCount = zipcodes.filter(z => z.onboardingStatus === 'onboarded').length;

  const nextFriday = getNextFriday();

  // Failed recent cron runs
  const failedRuns = cronStatus?.recentRuns.filter(r => r.status === 'FAILED') || [];

  // ══════════════════════════════════════════════════════════════════════
  // ── SUB-TAB: ONBOARDED ─────────────────────────────────────────────
  // ══════════════════════════════════════════════════════════════════════

  if (activeSubTab === 'onboarded') {
    return (
      <div className="space-y-6">
        {/* Registration Form */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <MapPin className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-bold text-gray-900">Register Zipcode</h2>
          </div>
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              placeholder="Zip codes (e.g. 07110, 07042, 07003)"
              value={zipInput}
              onChange={(e) => setZipInput(e.target.value.replace(/[^\d\s,]/g, ''))}
              className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm flex-1 min-w-[280px]"
            />
            <button
              onClick={handleRegister}
              disabled={registering || !zipInput}
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
            >
              {registering ? (
                <><Loader2 className="w-4 h-4 animate-spin" />Registering...</>
              ) : (
                <><Plus className="w-4 h-4" />Register</>
              )}
            </button>
          </div>

          {regSuccess && (
            <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              {regSuccess}
            </div>
          )}

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}
        </div>

        {/* Registered Zipcodes Table */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <MapPin className="w-4 h-4 text-gray-400" />
              Registered Zipcodes
              <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-medium">{onboardedCount} onboarded</span>
              {onboardingCount > 0 && (
                <span className="text-xs px-2 py-0.5 bg-yellow-50 text-yellow-700 rounded-full font-medium">{onboardingCount} onboarding</span>
              )}
              {pausedCount > 0 && (
                <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full font-medium">{pausedCount} paused</span>
              )}
            </h3>
            <button
              onClick={() => { setLoading(true); fetchZipcodes(); }}
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
          ) : zipcodes.length === 0 ? (
            <div className="p-10 text-center text-gray-400 text-sm">
              No zipcodes registered yet. Use the form above to add one.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
                    <th className="text-left px-6 py-3">Zip Code</th>
                    <th className="text-left px-4 py-3">City / State</th>
                    <th className="text-center px-4 py-3">Status</th>
                    <th className="text-left px-4 py-3">Last Pulse</th>
                    <th className="text-left px-4 py-3">Next Run</th>
                    <th className="text-center px-4 py-3">Count</th>
                    <th className="text-right px-6 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {zipcodes.map((zip) => (
                    <tr key={zip.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3">
                        <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                          {zip.zipCode}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {zip.city}, {zip.state}
                        {zip.county && (
                          <span className="text-xs text-gray-400 ml-1">({zip.county})</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex flex-col items-center gap-1">
                          {/* Onboarding status */}
                          {zip.onboardingStatus === 'onboarding' ? (
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-yellow-50 text-yellow-700 border border-yellow-200 flex items-center gap-1">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              onboarding
                            </span>
                          ) : (
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              onboarded
                            </span>
                          )}
                          {/* Active/paused status */}
                          {zip.status === 'paused' && (
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-amber-50 text-amber-700 border border-amber-200">
                              paused
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="min-w-0">
                          {zip.lastPulseHeadline ? (
                            <>
                              <p className="text-xs text-gray-700 truncate max-w-[200px]">{zip.lastPulseHeadline}</p>
                              <p className="text-[10px] text-gray-400">{relativeTime(zip.lastPulseAt)}</p>
                            </>
                          ) : (
                            <span className="text-xs text-gray-400">{relativeTime(zip.lastPulseAt)}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {zip.status === 'active' ? (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            Friday 6 AM
                          </span>
                        ) : (
                          <span className="text-amber-600">Paused</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs font-mono text-gray-600">{zip.pulseCount ?? 0}</span>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Run Now */}
                          <button
                            onClick={() => handleRunNow(zip)}
                            disabled={!!actionLoading[`run-${zip.id}`]}
                            className="p-1.5 rounded-lg text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                            title="Run pulse now"
                          >
                            {actionLoading[`run-${zip.id}`] ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Zap className="w-4 h-4" />
                            )}
                          </button>
                          {/* Approve (only if onboarding) */}
                          {zip.onboardingStatus === 'onboarding' && (
                            <button
                              onClick={() => handleApprove(zip)}
                              disabled={!!actionLoading[`approve-${zip.id}`]}
                              className="p-1.5 rounded-lg text-emerald-500 hover:text-emerald-700 hover:bg-emerald-50 transition-colors disabled:opacity-50"
                              title="Approve (mark as onboarded)"
                            >
                              {actionLoading[`approve-${zip.id}`] ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <CheckCircle2 className="w-4 h-4" />
                              )}
                            </button>
                          )}
                          {/* Pause / Resume */}
                          <button
                            onClick={() => handleToggleStatus(zip)}
                            disabled={!!actionLoading[`toggle-${zip.id}`]}
                            className={`p-1.5 rounded-lg transition-colors disabled:opacity-50 ${
                              zip.status === 'active'
                                ? 'text-amber-500 hover:text-amber-700 hover:bg-amber-50'
                                : 'text-emerald-500 hover:text-emerald-700 hover:bg-emerald-50'
                            }`}
                            title={zip.status === 'active' ? 'Pause' : 'Resume'}
                          >
                            {actionLoading[`toggle-${zip.id}`] ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : zip.status === 'active' ? (
                              <Pause className="w-4 h-4" />
                            ) : (
                              <Play className="w-4 h-4" />
                            )}
                          </button>
                          {/* View Latest */}
                          {zip.lastPulseId && (
                            <button
                              onClick={() => handleViewPulse(zip.lastPulseId!)}
                              className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                              title="View latest pulse"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                          )}
                          {/* Delete */}
                          <button
                            onClick={() => handleUnregister(zip)}
                            disabled={!!actionLoading[`del-${zip.id}`]}
                            className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                            title="Unregister"
                          >
                            {actionLoading[`del-${zip.id}`] ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Cron Status */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              Weekly Cron Status
            </h3>
            <button
              onClick={() => { setCronLoading(true); fetchCronStatus(); }}
              className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>

          {cronLoading ? (
            <div className="p-10 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
            </div>
          ) : cronStatus ? (
            <div className="p-6 space-y-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                  <p className="text-xs text-gray-400">Schedule</p>
                  <p className="text-sm font-semibold text-gray-800">{cronStatus.schedule}</p>
                </div>
                <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                  <p className="text-xs text-gray-400">Next Run</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {new Date(cronStatus.nextRunAt).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                    {' '}
                    {new Date(cronStatus.nextRunAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </p>
                </div>
                <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
                  <p className="text-xs text-emerald-500">Active in Cron</p>
                  <p className="text-sm font-semibold text-emerald-800">{cronStatus.activeZipcodes} zipcodes</p>
                </div>
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                  <p className="text-xs text-amber-500">Paused</p>
                  <p className="text-sm font-semibold text-amber-800">{cronStatus.pausedZipcodes} zipcodes</p>
                </div>
              </div>

              {cronStatus.recentRuns.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Recent Cron Runs</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
                          <th className="text-left px-4 py-2">Zip / Type</th>
                          <th className="text-center px-4 py-2">Status</th>
                          <th className="text-left px-4 py-2">Started</th>
                          <th className="text-left px-4 py-2">Completed</th>
                          <th className="text-left px-4 py-2">Job ID</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {cronStatus.recentRuns.map((run, i) => (
                          <tr key={i} className="hover:bg-gray-50/50">
                            <td className="px-4 py-2">
                              <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{run.zipCode}</span>
                              <span className="text-xs text-gray-400 ml-1">{run.businessType}</span>
                            </td>
                            <td className="px-4 py-2 text-center">
                              {run.status === 'COMPLETED' ? (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">Completed</span>
                              ) : run.status === 'FAILED' ? (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 font-medium" title={run.error || ''}>Failed</span>
                              ) : run.status === 'RUNNING' ? (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">Running</span>
                              ) : (
                                <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">{run.status}</span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-xs text-gray-500">{run.createdAt ? relativeTime(run.createdAt) : '-'}</td>
                            <td className="px-4 py-2 text-xs text-gray-500">{run.completedAt ? relativeTime(run.completedAt) : '-'}</td>
                            <td className="px-4 py-2 text-xs font-mono text-gray-400 truncate max-w-[120px]">{run.jobId}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {cronStatus.recentRuns.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-4">No cron runs yet. The first run will happen at the next scheduled time.</p>
              )}
            </div>
          ) : (
            <div className="p-10 text-center text-gray-400 text-sm">
              Could not load cron status.
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

  // ══════════════════════════════════════════════════════════════════════
  // ── SUB-TAB: WEEKLY RUNS ───────────────────────────────────────────
  // ══════════════════════════════════════════════════════════════════════

  if (activeSubTab === 'weekly') {
    return (
      <div className="space-y-6">
        {/* Next Run Card */}
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-6 text-white shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Calendar className="w-5 h-5 opacity-80" />
                <span className="text-sm font-medium opacity-80">Next Scheduled Run</span>
              </div>
              <h2 className="text-xl font-bold">
                {nextFriday.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}, 6:00 AM ET
              </h2>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold">{formatCountdown(nextFriday)}</p>
              <p className="text-sm opacity-70">{activeCount} active zip{activeCount !== 1 ? 's' : ''}</p>
            </div>
          </div>
        </div>

        {/* Failed Runs Alert */}
        {failedRuns.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <XCircle className="w-5 h-5 text-red-600" />
              <h3 className="font-semibold text-red-800">Failed Runs ({failedRuns.length})</h3>
            </div>
            <div className="space-y-2">
              {failedRuns.map((run, i) => (
                <div key={i} className="flex items-center justify-between bg-white border border-red-100 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{run.zipCode}</span>
                    <span className="text-xs text-gray-500">{run.businessType}</span>
                    <span className="text-xs text-red-500 truncate max-w-[300px]">{run.error}</span>
                  </div>
                  <button
                    onClick={() => {
                      const zip = zipcodes.find(z => z.zipCode === run.zipCode);
                      if (zip) handleRunNow(zip);
                    }}
                    className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-500 transition-colors font-medium"
                  >
                    Retry
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Latest Results — Per-zip cards */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-gray-400" />
              Latest Results
            </h3>
            <button
              onClick={() => { setLoading(true); fetchZipcodes(); }}
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
          ) : zipcodes.filter(z => z.lastPulseId).length === 0 ? (
            <div className="p-10 text-center text-gray-400 text-sm">
              No pulses generated yet. Run a pulse from the Onboarded Zips tab.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-6">
              {zipcodes.filter(z => z.lastPulseId).map((zip) => (
                <div key={zip.id} className="border border-gray-200 rounded-xl p-4 hover:border-indigo-200 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{zip.zipCode}</span>
                      <span className="text-xs text-gray-500">{zip.city}, {zip.state}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {zip.onboardingStatus === 'onboarded' ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 inline mr-0.5" />
                          onboarded
                        </span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-50 text-yellow-700 font-medium border border-yellow-200">
                          onboarding
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-gray-800 font-medium mb-1 truncate">{zip.lastPulseHeadline || 'No headline'}</p>
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span>{zip.lastPulseInsightCount} insights</span>
                    <span>{relativeTime(zip.lastPulseAt)}</span>
                  </div>
                  <button
                    onClick={() => handleViewPulse(zip.lastPulseId!)}
                    className="mt-3 text-xs text-indigo-600 hover:text-indigo-500 font-medium flex items-center gap-1"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    View Report
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* View All History */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
          <button
            onClick={() => {
              setShowAllHistory(!showAllHistory);
              if (!showAllHistory && productionPulses.length === 0) {
                setProductionLoading(true);
                fetchProductionPulses();
              }
            }}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50/50 transition-colors"
          >
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              All Production Run History
            </h3>
            {showAllHistory ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
          </button>

          {showAllHistory && (
            <div className="border-t border-gray-100">
              {productionLoading ? (
                <div className="p-10 flex items-center justify-center">
                  <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
                </div>
              ) : productionPulses.length === 0 ? (
                <div className="p-10 text-center text-gray-400 text-sm">
                  No production pulses found.
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {productionPulses.map((pulse) => (
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

  // ══════════════════════════════════════════════════════════════════════
  // ── SUB-TAB: TEST RUNS ─────────────────────────────────────────────
  // ══════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6">
      {/* Generate Test Pulse Form */}
      <div className="bg-white border border-amber-200 rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <FlaskConical className="w-5 h-5 text-amber-600" />
          <h2 className="text-lg font-bold text-gray-900">Generate Test Pulse</h2>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold border border-amber-200">TEST MODE</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            type="text"
            placeholder="Zip code (e.g. 07110)"
            value={testZipCode}
            onChange={(e) => setTestZipCode(e.target.value.replace(/\D/g, '').slice(0, 5))}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100 transition-all text-sm"
          />
          <select
            value={testBizType}
            onChange={(e) => setTestBizType(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100 transition-all text-sm"
          >
            {BUSINESS_TYPES.map(bt => <option key={bt} value={bt}>{bt}</option>)}
          </select>
          <input
            type="date"
            value={testWeekOf}
            onChange={(e) => setTestWeekOf(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100 transition-all text-sm"
          />
          <button
            onClick={handleTestGenerate}
            disabled={testGenerating || !testZipCode}
            className="bg-amber-500 hover:bg-amber-400 text-white font-semibold px-5 py-2.5 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
          >
            {testGenerating ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Generating...</>
            ) : (
              <><FlaskConical className="w-4 h-4" />Generate Test</>
            )}
          </button>
        </div>

        {testGenStatus && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-100 rounded-lg text-amber-700 text-sm flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            {testGenStatus}
          </div>
        )}

        {testGenError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
            {testGenError}
          </div>
        )}
      </div>

      {/* Test Pulse List */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-amber-500" />
            Recent Test Pulses
          </h3>
          <button
            onClick={() => { setTestPulsesLoading(true); fetchTestPulses(); }}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {testPulsesLoading ? (
          <div className="p-10 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
          </div>
        ) : testPulses.length === 0 ? (
          <div className="p-10 text-center text-gray-400 text-sm">
            No test pulses found. Use the form above to generate one.
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {testPulses.map((pulse) => (
              <div key={pulse.id} className="px-6 py-4 flex items-center gap-4 hover:bg-gray-50/50 transition-colors group">
                <button onClick={() => handleViewPulse(pulse.id, true)} className="flex-1 min-w-0 text-left">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold border border-amber-200">TEST</span>
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
                  onClick={() => handleDeletePulse(pulse.id, true)}
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

      {/* Auto-delete note */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2 text-amber-700 text-sm">
        <Clock className="w-4 h-4 shrink-0" />
        <span>Test data auto-deletes after 24 hours.</span>
      </div>

      {loadingDetail && (
        <div className="fixed inset-0 bg-white/60 z-30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      )}
    </div>
  );
}
