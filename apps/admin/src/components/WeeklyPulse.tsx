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
  ArrowUp,
  ArrowDown,
  Minus,
  Search,
  Cloud,
  Sparkles,
} from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────────────

interface PulseInsight {
  rank: number;
  title: string;
  analysis: string;
  recommendation: string;
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

interface PulseDocument {
  id: string;
  zipCode: string;
  businessType: string;
  weekOf: string;
  pulse: WeeklyPulseData;
  signalsUsed: string[];
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
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
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

// ── Insight Card ────────────────────────────────────────────────────────

function InsightCard({ insight }: { insight: PulseInsight }) {
  const [expanded, setExpanded] = useState(false);
  const colors = IMPACT_COLORS[insight.impactLevel] || IMPACT_COLORS.medium;

  return (
    <div className={`bg-white border rounded-xl shadow-sm overflow-hidden ${colors.border} border-l-4`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-5 py-4 flex items-start gap-3 hover:bg-gray-50/50 transition-colors"
      >
        <div className="flex items-center gap-2 shrink-0 mt-0.5">
          <span className="text-lg font-bold text-gray-300">#{insight.rank}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h4 className="font-semibold text-gray-900 text-sm">{insight.title}</h4>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full border ${colors.bg} ${colors.text} ${colors.border} font-medium`}>
              {insight.impactLevel} impact
            </span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {TIME_LABELS[insight.timeSensitivity] || insight.timeSensitivity}
            </span>
            <span className="text-xs font-mono text-gray-400">
              Score: {insight.impactScore}
            </span>
          </div>
        </div>
        {expanded ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0 mt-1" /> : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-1" />}
      </button>

      {expanded && (
        <div className="px-5 pb-5 pt-0 border-t border-gray-100 space-y-3 animate-in fade-in duration-200">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Analysis</p>
            <p className="text-sm text-gray-700 leading-relaxed">{insight.analysis}</p>
          </div>
          <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
            <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">Recommendation</p>
            <p className="text-sm text-indigo-900 leading-relaxed">{insight.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Quick Stats ─────────────────────────────────────────────────────────

function QuickStatsBar({ stats }: { stats: PulseQuickStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2.5">
        <div className="p-1.5 bg-blue-50 rounded-md">
          <Search className="w-4 h-4 text-blue-500" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500">Trending</p>
          <p className="text-sm font-medium text-gray-900 truncate">
            {stats.trendingSearches?.length ? stats.trendingSearches[0] : 'None'}
          </p>
        </div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2.5">
        <div className="p-1.5 bg-sky-50 rounded-md">
          <Cloud className="w-4 h-4 text-sky-500" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500">Weather</p>
          <p className="text-sm font-medium text-gray-900 truncate">{stats.weatherOutlook || 'N/A'}</p>
        </div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2.5">
        <div className="p-1.5 bg-purple-50 rounded-md">
          <Calendar className="w-4 h-4 text-purple-500" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500">Events</p>
          <p className="text-sm font-medium text-gray-900">{stats.upcomingEvents ?? 0}</p>
        </div>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-3 flex items-center gap-2.5">
        <div className="p-1.5 bg-amber-50 rounded-md">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500">Price Alerts</p>
          <p className="text-sm font-medium text-gray-900">{stats.priceAlerts ?? 0}</p>
        </div>
      </div>
    </div>
  );
}

// ── Pulse Viewer ────────────────────────────────────────────────────────

function PulseViewer({ doc, onBack }: { doc: PulseDocument; onBack: () => void }) {
  const pulse = doc.pulse;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <button onClick={onBack} className="text-sm text-indigo-600 hover:text-indigo-500 font-medium shrink-0 mt-1">
          &larr; Back to list
        </button>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {doc.signalsUsed?.length > 0 && (
            <span>{doc.signalsUsed.length} signals</span>
          )}
          <span>{relativeTime(doc.createdAt)}</span>
        </div>
      </div>

      {/* Headline card */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-6 text-white shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-5 h-5" />
          <span className="text-sm font-medium opacity-80">Weekly Pulse</span>
          <span className="text-sm opacity-60">|</span>
          <span className="text-sm opacity-80">{pulse.zipCode}</span>
          <span className="text-sm opacity-60">|</span>
          <span className="text-sm opacity-80">{pulse.businessType}</span>
          <span className="text-sm opacity-60">|</span>
          <span className="text-sm opacity-80">Week of {pulse.weekOf}</span>
        </div>
        <h2 className="text-xl font-bold leading-tight">{pulse.headline}</h2>
      </div>

      {/* Quick stats */}
      {pulse.quickStats && <QuickStatsBar stats={pulse.quickStats} />}

      {/* Insight cards */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          Insights ({pulse.insights?.length || 0})
        </h3>
        {pulse.insights?.length ? (
          pulse.insights.map((insight, i) => (
            <InsightCard key={i} insight={insight} />
          ))
        ) : (
          <div className="text-center py-10 border border-dashed border-gray-300 rounded-xl text-gray-400 text-sm">
            No insights generated.
          </div>
        )}
      </div>

      {/* Signal sources */}
      {doc.signalsUsed?.length > 0 && (
        <div className="pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 mb-2">Data sources used:</p>
          <div className="flex flex-wrap gap-1.5">
            {doc.signalsUsed.map((signal, i) => (
              <span key={i} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                {signal}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────

export default function WeeklyPulse() {
  // Generate form
  const [zipCode, setZipCode] = useState('');
  const [businessType, setBusinessType] = useState('Restaurants');
  const [weekOf, setWeekOf] = useState(() => new Date().toISOString().split('T')[0]);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  // List view
  const [pulses, setPulses] = useState<PulseSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // Detail view
  const [selectedPulse, setSelectedPulse] = useState<PulseDocument | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchPulses = useCallback(async () => {
    try {
      const res = await fetch('/api/weekly-pulse?limit=20');
      if (res.ok) {
        setPulses(await res.json());
      }
    } catch {
      // Silently fail — not critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPulses(); }, [fetchPulses]);

  const handleGenerate = async () => {
    if (!zipCode.match(/^\d{5}$/)) {
      setGenError('Enter a valid 5-digit zip code');
      return;
    }
    setGenerating(true);
    setGenError(null);
    try {
      const res = await fetch('/api/weekly-pulse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zipCode,
          businessType,
          weekOf,
          force: true,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Generation failed' }));
        throw new Error(err.detail || 'Generation failed');
      }
      const data = await res.json();
      // Show the generated pulse
      setSelectedPulse({
        id: data.pulseId,
        zipCode,
        businessType,
        weekOf,
        pulse: data.pulse,
        signalsUsed: data.signalsUsed || [],
        createdAt: new Date().toISOString(),
      });
      // Refresh list
      fetchPulses();
    } catch (e: any) {
      setGenError(e.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleViewPulse = async (pulseId: string) => {
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/weekly-pulse/id/${pulseId}`);
      if (res.ok) {
        setSelectedPulse(await res.json());
      }
    } catch {
      // Ignore
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDeletePulse = async (pulseId: string) => {
    if (!confirm('Delete this pulse?')) return;
    try {
      await fetch(`/api/weekly-pulse/id/${pulseId}`, { method: 'DELETE' });
      setPulses(prev => prev.filter(p => p.id !== pulseId));
      if (selectedPulse?.id === pulseId) setSelectedPulse(null);
    } catch {
      // Ignore
    }
  };

  // ── Render ──────────────────────────────────────────────────────────

  if (selectedPulse && !loadingDetail) {
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
        <PulseViewer
          doc={selectedPulse}
          onBack={() => setSelectedPulse(null)}
        />
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
            {BUSINESS_TYPES.map(bt => (
              <option key={bt} value={bt}>{bt}</option>
            ))}
          </select>
          <input
            type="date"
            value={weekOf}
            onChange={(e) => setWeekOf(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
          />
          <button
            onClick={handleGenerate}
            disabled={generating || !zipCode}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
          >
            {generating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Zap className="w-4 h-4" />
                Generate
              </>
            )}
          </button>
        </div>

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
              <div
                key={pulse.id}
                className="px-6 py-4 flex items-center gap-4 hover:bg-gray-50/50 transition-colors group"
              >
                <button
                  onClick={() => handleViewPulse(pulse.id)}
                  className="flex-1 min-w-0 text-left"
                >
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                      {pulse.zipCode}
                    </span>
                    <span className="text-xs text-gray-400">{pulse.businessType}</span>
                    <span className="text-xs text-gray-300">|</span>
                    <span className="text-xs text-gray-400">{pulse.weekOf}</span>
                  </div>
                  <p className="text-sm text-gray-700 truncate">{pulse.headline || 'No headline'}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400">{pulse.insightCount} insights</span>
                    {pulse.createdAt && (
                      <span className="text-xs text-gray-300">{relativeTime(pulse.createdAt)}</span>
                    )}
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

      {/* Loading overlay for detail */}
      {loadingDetail && (
        <div className="fixed inset-0 bg-white/60 z-30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
        </div>
      )}
    </div>
  );
}
