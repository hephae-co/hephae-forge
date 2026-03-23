'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Brain,
  Cpu,
  Zap,
  RefreshCw,
  Play,
  Pause,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  ChevronRight,
  TrendingUp,
  Layers,
  Sparkles,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface RegisteredIndustry {
  id: string;
  industryKey: string;
  displayName: string;
  status: 'active' | 'paused';
  registeredAt: string | null;
  lastPulseAt: string | null;
  lastPulseId: string | null;
  pulseCount: number;
}

interface LatestPulse {
  id: string;
  weekOf: string;
  trendSummary: string;
  signalsUsed: string[];
  playbooksMatched: number;
  createdAt: string | null;
}

interface TechIntelProfile {
  id: string;
  weekOf: string;
  weeklyHighlight: { title?: string; summary?: string } | null;
  aiOpportunitiesCount: number;
  platformsCount: number;
  generatedAt: string | null;
}

interface IndustryDetail {
  industry: RegisteredIndustry;
  pulse: LatestPulse | null;
  techIntel: TechIntelProfile | null;
  loadingPulse: boolean;
  loadingTechIntel: boolean;
  runningPulse: boolean;
  runningTechIntel: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(val: string | null | undefined): string {
  if (!val) return '—';
  const d = new Date(typeof val === 'string' && !val.includes('T') ? val + 'Z' : val);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

function timeAgo(val: string | null | undefined): string {
  if (!val) return '';
  const d = new Date(typeof val === 'string' && !val.includes('T') ? val + 'Z' : val);
  if (isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const h = Math.floor(diff / 3600000);
  const days = Math.floor(h / 24);
  if (days > 0) return `${days}d ago`;
  if (h > 0) return `${h}h ago`;
  return 'just now';
}

// ─── Cron Pipeline Banner ─────────────────────────────────────────────────────

function CronPipelineBanner() {
  const steps = [
    {
      icon: Cpu,
      label: 'Tech Intelligence',
      schedule: 'Sun 1 AM ET',
      color: 'violet',
      bg: 'bg-violet-50',
      border: 'border-violet-200',
      text: 'text-violet-700',
      iconBg: 'bg-violet-100',
    },
    {
      icon: Brain,
      label: 'Industry Pulse',
      schedule: 'Sun 3 AM ET',
      color: 'amber',
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      text: 'text-amber-700',
      iconBg: 'bg-amber-100',
    },
    {
      icon: Zap,
      label: 'Weekly Pulse',
      schedule: 'Mon 3 AM ET',
      color: 'indigo',
      bg: 'bg-indigo-50',
      border: 'border-indigo-200',
      text: 'text-indigo-700',
      iconBg: 'bg-indigo-100',
    },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">Weekly Cron Pipeline</p>
      <div className="flex items-center gap-2 flex-wrap">
        {steps.map((s, i) => (
          <div key={s.label} className="flex items-center gap-2">
            <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${s.bg} ${s.border}`}>
              <div className={`p-1.5 rounded-md ${s.iconBg}`}>
                <s.icon className={`w-4 h-4 ${s.text}`} />
              </div>
              <div>
                <p className={`text-sm font-semibold ${s.text}`}>{s.label}</p>
                <p className="text-xs text-gray-500">{s.schedule}</p>
              </div>
            </div>
            {i < steps.length - 1 && (
              <ChevronRight className="w-4 h-4 text-gray-300 shrink-0" />
            )}
          </div>
        ))}
        <div className="ml-auto text-xs text-gray-400 hidden md:block">
          Tech Intel → pre-fetched data → Zip Pulses consume it
        </div>
      </div>
    </div>
  );
}

// ─── Industry Card ─────────────────────────────────────────────────────────────

function IndustryCard({
  detail,
  onPause,
  onResume,
  onRunPulse,
  onRunTechIntel,
}: {
  detail: IndustryDetail;
  onPause: (key: string) => void;
  onResume: (key: string) => void;
  onRunPulse: (key: string) => void;
  onRunTechIntel: (key: string) => void;
}) {
  const { industry, pulse, techIntel, loadingPulse, loadingTechIntel, runningPulse, runningTechIntel } = detail;
  const isActive = industry.status === 'active';

  return (
    <div className={`bg-white border rounded-xl shadow-sm overflow-hidden transition-all ${isActive ? 'border-gray-200' : 'border-gray-200 opacity-70'}`}>
      {/* Header */}
      <div className="px-5 py-4 flex items-start justify-between gap-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-base font-bold ${isActive ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'}`}>
            {industry.displayName[0]}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">{industry.displayName}</h3>
            <p className="text-xs text-gray-400 font-mono">{industry.industryKey}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${isActive ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-gray-400'}`} />
            {isActive ? 'Active' : 'Paused'}
          </span>
          <span className="text-xs text-gray-400">{industry.pulseCount} pulses</span>
        </div>
      </div>

      {/* Data sections */}
      <div className="divide-y divide-gray-50">
        {/* Industry Pulse */}
        <div className="px-5 py-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Brain className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Industry Pulse</span>
          </div>
          {loadingPulse ? (
            <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
          ) : pulse ? (
            <div>
              <p className="text-xs text-gray-700 line-clamp-2 leading-relaxed">{pulse.trendSummary || 'No summary available.'}</p>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-xs text-gray-400">{pulse.weekOf}</span>
                <span className="text-xs text-gray-400">·</span>
                <span className="text-xs text-gray-400">{pulse.signalsUsed.length} signals</span>
                <span className="text-xs text-gray-400">·</span>
                <span className="text-xs text-gray-400">{pulse.playbooksMatched} playbooks</span>
                <span className="text-xs text-gray-400 ml-auto">{timeAgo(pulse.createdAt)}</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">No pulse this week yet</p>
          )}
        </div>

        {/* Tech Intelligence */}
        <div className="px-5 py-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Cpu className="w-3.5 h-3.5 text-violet-500" />
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Tech Intelligence</span>
          </div>
          {loadingTechIntel ? (
            <div className="h-4 bg-gray-100 rounded animate-pulse w-2/3" />
          ) : techIntel ? (
            <div>
              <p className="text-xs text-gray-700 line-clamp-2 leading-relaxed">
                {techIntel.weeklyHighlight?.title || techIntel.weeklyHighlight?.summary || 'No highlight available.'}
              </p>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-xs text-gray-400">{techIntel.weekOf}</span>
                <span className="text-xs text-gray-400">·</span>
                <span className="text-xs text-gray-400">{techIntel.aiOpportunitiesCount} AI opps</span>
                <span className="text-xs text-gray-400">·</span>
                <span className="text-xs text-gray-400">{techIntel.platformsCount} platforms</span>
                <span className="text-xs text-gray-400 ml-auto">{timeAgo(techIntel.generatedAt)}</span>
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">No tech intel this week yet</p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="px-5 py-3 bg-gray-50 flex items-center gap-2 flex-wrap">
        <button
          onClick={() => isActive ? onPause(industry.industryKey) : onResume(industry.industryKey)}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors ${isActive ? 'border-gray-200 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'}`}
        >
          {isActive ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          {isActive ? 'Pause' : 'Resume'}
        </button>
        <button
          onClick={() => onRunPulse(industry.industryKey)}
          disabled={runningPulse}
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-amber-200 text-amber-700 hover:bg-amber-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {runningPulse ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Brain className="w-3 h-3" />}
          {runningPulse ? 'Generating…' : 'Run Pulse'}
        </button>
        <button
          onClick={() => onRunTechIntel(industry.industryKey)}
          disabled={runningTechIntel}
          className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-violet-200 text-violet-700 hover:bg-violet-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {runningTechIntel ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Cpu className="w-3 h-3" />}
          {runningTechIntel ? 'Generating…' : 'Run Tech Intel'}
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

type IntelSubTab = 'industries' | 'pulse-history' | 'tech-intel';

export default function IntelligenceDashboard() {
  const [subTab, setSubTab] = useState<IntelSubTab>('industries');
  const [details, setDetails] = useState<IndustryDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Load industries + their pulse + tech intel in parallel
  const loadIndustries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/registered-industries');
      if (!res.ok) throw new Error('Failed to load industries');
      const data = await res.json();
      const industries: RegisteredIndustry[] = data.industries || [];

      // Build skeleton details first so the card renders immediately
      const skeletons: IndustryDetail[] = industries.map(ind => ({
        industry: ind,
        pulse: null,
        techIntel: null,
        loadingPulse: true,
        loadingTechIntel: true,
        runningPulse: false,
        runningTechIntel: false,
      }));
      setDetails(skeletons);
      setLoading(false);

      // Fetch pulse + tech intel for each industry in parallel
      await Promise.all(
        industries.map(async (ind, idx) => {
          const [pulseRes, techRes] = await Promise.all([
            fetch(`/api/registered-industries/${ind.industryKey}/latest-pulse`),
            fetch(`/api/registered-industries/${ind.industryKey}/latest-tech-intel`),
          ]);

          const pulseData = pulseRes.ok ? await pulseRes.json() : null;
          const techData = techRes.ok ? await techRes.json() : null;

          setDetails(prev => {
            const next = [...prev];
            if (next[idx]) {
              next[idx] = {
                ...next[idx],
                pulse: pulseData?.pulse ?? null,
                techIntel: techData?.profile ?? null,
                loadingPulse: false,
                loadingTechIntel: false,
              };
            }
            return next;
          });
        })
      );
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadIndustries(); }, [loadIndustries]);

  const handlePause = async (key: string) => {
    await fetch(`/api/registered-industries/${key}/pause`, { method: 'POST' });
    setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, industry: { ...d.industry, status: 'paused' } } : d));
    showToast(`${key} paused`);
  };

  const handleResume = async (key: string) => {
    await fetch(`/api/registered-industries/${key}/resume`, { method: 'POST' });
    setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, industry: { ...d.industry, status: 'active' } } : d));
    showToast(`${key} resumed`);
  };

  const handleRunPulse = async (key: string) => {
    setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningPulse: true } : d));
    try {
      const res = await fetch(`/api/registered-industries/${key}/generate-now`, { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data?.success) {
        showToast(`${key} pulse generated — ${data.signalCount} signals, ${data.playbooksMatched} playbooks`);
        // Refresh that industry's pulse
        const pulseRes = await fetch(`/api/registered-industries/${key}/latest-pulse`);
        const pulseData = pulseRes.ok ? await pulseRes.json() : null;
        setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, pulse: pulseData?.pulse ?? d.pulse, runningPulse: false } : d));
      } else {
        showToast(`Failed to generate pulse for ${key}`);
        setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningPulse: false } : d));
      }
    } catch {
      showToast(`Error generating pulse for ${key}`);
      setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningPulse: false } : d));
    }
  };

  const handleRunTechIntel = async (key: string) => {
    setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningTechIntel: true } : d));
    try {
      const res = await fetch(`/api/registered-industries/${key}/generate-tech-intel`, { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data?.success) {
        showToast(`${key} tech intel generated — ${data.aiOpportunitiesCount} AI opps, ${data.platformsCount} platforms`);
        const techRes = await fetch(`/api/registered-industries/${key}/latest-tech-intel`);
        const techData = techRes.ok ? await techRes.json() : null;
        setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, techIntel: techData?.profile ?? d.techIntel, runningTechIntel: false } : d));
      } else {
        showToast(`Failed to generate tech intel for ${key}: ${data?.error || 'unknown error'}`);
        setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningTechIntel: false } : d));
      }
    } catch {
      showToast(`Error generating tech intel for ${key}`);
      setDetails(prev => prev.map(d => d.industry.industryKey === key ? { ...d, runningTechIntel: false } : d));
    }
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
      {/* Toast */}
      {toastMsg && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-gray-900 text-white text-sm font-medium px-5 py-3 rounded-xl shadow-xl animate-in fade-in slide-in-from-bottom-2 duration-200">
          {toastMsg}
        </div>
      )}

      {/* Cron pipeline */}
      <CronPipelineBanner />

      {/* Sub-tabs */}
      <div className="flex items-center gap-1 bg-white p-1 rounded-lg border border-gray-200 shadow-sm w-fit">
        {([
          { key: 'industries', label: 'Industries', icon: Layers },
          { key: 'pulse-history', label: 'Pulse History', icon: TrendingUp },
          { key: 'tech-intel', label: 'Tech Intelligence', icon: Sparkles },
        ] as { key: IntelSubTab; label: string; icon: React.ComponentType<{ className?: string }> }[]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setSubTab(key)}
            className={`px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-all ${subTab === key ? 'bg-indigo-600 text-white shadow' : 'text-gray-500 hover:text-gray-900'}`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
        <button
          onClick={loadIndustries}
          className="ml-2 p-2 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {/* ── Industries Tab ─────────────────────────────────────────────── */}
      {subTab === 'industries' && (
        <div>
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-white border border-gray-200 rounded-xl h-64 animate-pulse" />
              ))}
            </div>
          ) : details.length === 0 ? (
            <div className="text-center py-16 text-gray-400 border border-dashed border-gray-300 rounded-xl">
              No registered industries.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {details.map(detail => (
                <IndustryCard
                  key={detail.industry.industryKey}
                  detail={detail}
                  onPause={handlePause}
                  onResume={handleResume}
                  onRunPulse={handleRunPulse}
                  onRunTechIntel={handleRunTechIntel}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Pulse History Tab ──────────────────────────────────────────── */}
      {subTab === 'pulse-history' && (
        <PulseHistoryTab />
      )}

      {/* ── Tech Intelligence Tab ─────────────────────────────────────── */}
      {subTab === 'tech-intel' && (
        <TechIntelTab />
      )}
    </div>
  );
}

// ─── Pulse History Tab ────────────────────────────────────────────────────────

function PulseHistoryTab() {
  const [pulses, setPulses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/registered-industries');
        if (!res.ok) return;
        const data = await res.json();
        const industries: RegisteredIndustry[] = data.industries || [];
        // Fetch latest pulse for each industry
        const results = await Promise.all(
          industries.map(async (ind) => {
            const r = await fetch(`/api/registered-industries/${ind.industryKey}/latest-pulse`);
            const d = r.ok ? await r.json() : null;
            return d?.pulse ? { ...d.pulse, industryKey: ind.industryKey, displayName: ind.displayName } : null;
          })
        );
        setPulses(results.filter(Boolean).sort((a, b) => new Date(b.createdAt || 0).getTime() - new Date(a.createdAt || 0).getTime()));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => <div key={i} className="h-24 bg-white border border-gray-200 rounded-xl animate-pulse" />)}
    </div>
  );

  if (pulses.length === 0) return (
    <div className="text-center py-16 text-gray-400 border border-dashed border-gray-300 rounded-xl">
      No industry pulses found.
    </div>
  );

  return (
    <div className="space-y-3">
      {pulses.map((p) => (
        <div key={p.id} className="bg-white border border-gray-200 rounded-xl px-5 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex items-center gap-2">
              <span className="bg-amber-100 text-amber-700 text-xs font-bold px-2 py-0.5 rounded-full">{p.displayName}</span>
              <span className="text-xs text-gray-400 font-mono">{p.weekOf}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-xs text-gray-400">
              <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3" /> {p.signalsUsed?.length ?? 0} signals</span>
              <span>{p.playbooksMatched} playbooks</span>
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {fmtDate(p.createdAt)}</span>
            </div>
          </div>
          <p className="text-sm text-gray-600 line-clamp-3 leading-relaxed">{p.trendSummary || 'No summary.'}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Tech Intelligence Tab ────────────────────────────────────────────────────

function TechIntelTab() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/registered-industries');
        if (!res.ok) return;
        const data = await res.json();
        const industries: RegisteredIndustry[] = data.industries || [];
        const results = await Promise.all(
          industries.map(async (ind) => {
            const r = await fetch(`/api/registered-industries/${ind.industryKey}/latest-tech-intel`);
            const d = r.ok ? await r.json() : null;
            return d?.profile ? { ...d.profile, industryKey: ind.industryKey, displayName: ind.displayName } : null;
          })
        );
        setProfiles(results.filter(Boolean).sort((a, b) => new Date(b.generatedAt || 0).getTime() - new Date(a.generatedAt || 0).getTime()));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return (
    <div className="space-y-3">
      {[1, 2, 3].map(i => <div key={i} className="h-28 bg-white border border-gray-200 rounded-xl animate-pulse" />)}
    </div>
  );

  if (profiles.length === 0) return (
    <div className="text-center py-16 text-gray-400 border border-dashed border-gray-300 rounded-xl">
      No tech intelligence profiles found.
    </div>
  );

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {profiles.map((p) => (
        <div key={p.id} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-violet-100 text-violet-700 flex items-center justify-center text-sm font-bold">
                {p.displayName?.[0] || '?'}
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">{p.displayName}</p>
                <p className="text-xs text-gray-400 font-mono">{p.weekOf}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Clock className="w-3 h-3" />
              {timeAgo(p.generatedAt)}
            </div>
          </div>
          <div className="px-5 py-4 space-y-3">
            {p.weeklyHighlight?.title && (
              <div>
                <p className="text-xs font-semibold text-violet-600 uppercase tracking-wide mb-1">Weekly Highlight</p>
                <p className="text-sm text-gray-700 font-medium">{p.weeklyHighlight.title}</p>
                {p.weeklyHighlight?.summary && (
                  <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{p.weeklyHighlight.summary}</p>
                )}
              </div>
            )}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Sparkles className="w-3.5 h-3.5 text-violet-400" />
                <span><strong className="text-gray-800">{p.aiOpportunitiesCount}</strong> AI opportunities</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <Cpu className="w-3.5 h-3.5 text-violet-400" />
                <span><strong className="text-gray-800">{p.platformsCount}</strong> platforms</span>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
