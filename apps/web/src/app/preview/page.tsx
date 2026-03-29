'use client';

/**
 * /preview — Amethyst Insight layout prototype
 *
 * Design sandbox for the new 3-column dashboard layout before migrating to the main page.
 * Ships with demo seed data pre-loaded so the layout is instantly visible.
 *
 * Data availability pattern for every bento card:
 *   empty  → no business selected            → greyed placeholder + search prompt
 *   locked → business selected, no analysis  → locked card + "Run X" CTA
 *   loaded → analysis data available         → full visualization
 */

import { useState, useCallback, useRef } from 'react';
import {
  Building2, DollarSign, TrendingUp, Users, MapPin, Zap,
  BarChart3, ExternalLink, Search, Activity, Brain, Calendar,
  ArrowRight, Cpu, ChevronRight, Send,
  Flame, Globe, Lock, Sparkles, X, LogIn, CheckCircle,
  AlertTriangle,
} from 'lucide-react';
import dynamic from 'next/dynamic';

// ─── Recharts (client-only) ───────────────────────────────────────────────────

const MiniBar = dynamic(() => import('recharts').then(m => {
  const { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } = m;
  const C = ({ data, colors }: { data: { label: string; value: number }[]; colors?: string[] }) => (
    <ResponsiveContainer width="100%" height={90}>
      <BarChart data={data} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis hide domain={[0, 100]} />
        <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,.08)', fontSize: 11 }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={20}>
          {data.map((_, i) => (
            <Cell key={i} fill={colors?.[i % (colors?.length ?? 1)] ?? '#7c3aed'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
  C.displayName = 'MiniBar';
  return C;
}), { ssr: false });

// ─── Types ────────────────────────────────────────────────────────────────────

interface AiTool { tool: string; capability: string; url?: string | null; actionForOwner?: string; }
interface Insight { title: string; recommendation: string; }
interface Event { what: string; when: string; }
interface Competitor { name: string; category: string; cuisine: string; distanceM: number; }

interface DashboardData {
  pulseHeadline?: string | null;
  isNational?: boolean; // true = national benchmarks only, zip not monitored
  keyMetrics?: Record<string, number>;
  topInsights?: Insight[];
  communityBuzz?: string | null;
  events?: Event[];
  stats?: { population?: string | null; medianIncome?: string | null; city?: string | null; state?: string | null; competitorCount?: number; };
  aiTools?: AiTool[];
  competitors?: Competitor[];
  confirmedSources?: number;
}

interface MarginData {
  overall_score?: number;
  annual_leakage?: number;
  top_opportunity?: string;
  categories?: Record<string, { margin_pct?: number; cost_pct?: number; label?: string }>;
}

interface SeoData {
  overallScore?: number;
  findings?: { title: string; severity: string }[];
}

interface TrafficData {
  weeklyScore: number;
  peakDay: string;
  peakHour: string;
  forecast: string;
  byDay: { day: string; score: number }[];
  hourly: { hour: string; score: number }[];
}

interface Business {
  name: string;
  address?: string;
  officialUrl?: string;
  lat?: number;
  lng?: number;
  persona?: string;
  logoUrl?: string;
  favicon?: string;
  primaryColor?: string;
}

// ─── Demo seed data ───────────────────────────────────────────────────────────

const DEMO_BUSINESS: Business = {
  name: 'Bosphorus Mediterranean Grill',
  address: '123 Franklin Ave, Nutley, NJ 07110',
  officialUrl: 'https://bosphorusnutley.com',
  persona: 'Family-owned Mediterranean restaurant since 2004',
  lat: 40.8196,
  lng: -74.1571,
  primaryColor: '#7c3aed',
};

const DEMO_DASHBOARD: DashboardData = {
  pulseHeadline: 'Labor costs up 8% in NJ food service — AI scheduling tools gaining fast adoption among independents',
  keyMetrics: { 'Labor Cost %': 32, 'Food Cost %': 28, 'Revenue Index': 74, 'Foot Traffic': 65 },
  topInsights: [
    { title: 'Menu Pricing Gap', recommendation: 'Your avg check is $18 vs $24 market avg — leaving ~$800/week on the table' },
    { title: 'Peak Hours Missed', recommendation: 'Lunch rush 12–1pm has 40% lower cover count than nearby competitors' },
    { title: 'Tech Lag', recommendation: 'Competitors using AI scheduling tools save 6h/week of manager time' },
  ],
  communityBuzz: '"Authentic" and "family-owned" trending in local food searches this week. A food blog covered new Mediterranean spots in Nutley — organic SEO opportunity.',
  events: [
    { what: 'Nutley Street Fair', when: 'Saturday — outdoor festival, expect +40% foot traffic near you' },
    { what: 'Monday Night Football', when: 'Monday — sports bar spillover effect; advertise drink specials' },
    { what: 'Friday Farmers Market', when: 'Friday morning — foot traffic spike at nearby Franklin Park' },
    { what: 'Easter Weekend', when: 'Sunday — family dining surge, pre-book reservations now' },
  ],
  stats: { population: '28,000', medianIncome: '$72,400', competitorCount: 14, city: 'Nutley', state: 'NJ' },
  aiTools: [
    { tool: 'Toast IQ', capability: 'AI menu engineering + upsell prompts at checkout', url: 'https://pos.toasttab.com', actionForOwner: 'Free trial — integrates with your POS' },
    { tool: 'Lightspeed OCR', capability: 'Automated vendor invoice processing & cost tracking', url: 'https://www.lightspeedhq.com', actionForOwner: 'Eliminates manual data entry' },
    { tool: 'Winnow Vision', capability: 'Food waste tracking via computer vision', url: 'https://www.winnowsolutions.com', actionForOwner: 'Target 15–30% waste reduction' },
    { tool: '7shifts', capability: 'AI labor scheduling & real-time cost forecasting', url: 'https://www.7shifts.com', actionForOwner: 'Integrates with Toast' },
  ],
  competitors: [
    { name: 'Olive Garden', category: 'restaurant', cuisine: 'italian', distanceM: 340 },
    { name: 'Casa di Trevi', category: 'restaurant', cuisine: 'mediterranean', distanceM: 520 },
    { name: 'Mediterra', category: 'restaurant', cuisine: 'mediterranean', distanceM: 780 },
    { name: 'Sultan Palace', category: 'restaurant', cuisine: 'turkish', distanceM: 1100 },
  ],
  confirmedSources: 12,
};

const DEMO_MARGIN: MarginData = {
  overall_score: 62,
  annual_leakage: 38400,
  top_opportunity: 'Negotiate bulk protein pricing — projected $800/mo savings',
  categories: {
    proteins:  { margin_pct: 58.4, cost_pct: 41.6, label: 'Proteins' },
    produce:   { margin_pct: 72.1, cost_pct: 27.9, label: 'Produce' },
    dry_goods: { margin_pct: 66.8, cost_pct: 33.2, label: 'Dry Goods' },
    beverages: { margin_pct: 84.5, cost_pct: 15.5, label: 'Beverages' },
  },
};

const DEMO_SEO: SeoData = {
  overallScore: 58,
  findings: [
    { title: 'Missing Google Business hours', severity: 'high' },
    { title: 'No schema markup on homepage', severity: 'high' },
    { title: 'Slow mobile load time (4.2s)', severity: 'medium' },
    { title: 'Missing alt text on 7 images', severity: 'low' },
  ],
};

const DEMO_TRAFFIC: TrafficData = {
  weeklyScore: 74,
  peakDay: 'Saturday',
  peakHour: '7:00 PM',
  forecast: 'Easter weekend surge expected: +34% vs last week. Recommend extending dinner service to 10:30 PM Saturday and adding a prix-fixe brunch Sunday.',
  byDay: [
    { day: 'Mon', score: 32 },
    { day: 'Tue', score: 38 },
    { day: 'Wed', score: 49 },
    { day: 'Thu', score: 64 },
    { day: 'Fri', score: 87 },
    { day: 'Sat', score: 100 },
    { day: 'Sun', score: 82 },
  ],
  hourly: [
    { hour: '11a', score: 18 },
    { hour: '12p', score: 65 },
    { hour: '1p',  score: 55 },
    { hour: '2p',  score: 22 },
    { hour: '5p',  score: 48 },
    { hour: '6p',  score: 80 },
    { hour: '7p',  score: 100 },
    { hour: '8p',  score: 86 },
    { hour: '9p',  score: 40 },
  ],
};

// ─── Unmonitored zip scenario ─────────────────────────────────────────────────
// Simulates a business whose zip code has never been added to the weekly pulse.
// Only basic identity + raw OSM competitor proximity is available.

const UNMONITORED_BUSINESS: Business = {
  name: "Mario's Coal-Fired Pizza",
  address: '412 Washington St, Hoboken, NJ 07030',
  officialUrl: 'https://marioscoalfiredpizza.com',
  persona: 'Coal-fired Neapolitan pizzeria, cash only',
  lat: 40.7440,
  lng: -74.0324,
};

// Partial dashboard: national BLS/USDA benchmarks shown since zip is not monitored.
const UNMONITORED_DASHBOARD: DashboardData = {
  pulseHeadline: 'National benchmarks: Food service labor up 4.2% YoY (BLS) · Food-at-home CPI +2.8% (USDA) · Independent restaurant 3-year survival rate: 59%',
  isNational: true,
  keyMetrics: { 'Avg Labor %': 31, 'Avg Food Cost %': 29, 'Revenue Index': 62, 'Survival Rate': 59 },
  topInsights: [
    { title: 'Labor Cost Benchmark', recommendation: 'US independents average 31% labor cost — are you above or below? Run a Margin Analysis to find out.' },
    { title: 'Food Cost Trend', recommendation: 'USDA reports food-at-home prices up 2.8% — audit your vendor contracts before your next order cycle.' },
    { title: 'Digital Visibility Gap', recommendation: '67% of independent restaurants have an incomplete Google Business profile (BrightLocal 2024) — a quick fix with outsized impact.' },
  ],
  communityBuzz: 'Zip 07030 (Hoboken, NJ) is not yet in our weekly monitoring pipeline. Showing national benchmarks from BLS and USDA instead. Nominate this zip to get hyperlocal weekly intelligence.',
  stats: { city: 'Hoboken', state: 'NJ' },
  aiTools: DEMO_DASHBOARD.aiTools, // generic — always shown regardless of zip monitoring
  competitors: [
    { name: "Grimaldi's Pizzeria", category: 'restaurant', cuisine: 'pizza', distanceM: 210 },
    { name: 'Bello Giardino', category: 'restaurant', cuisine: 'italian', distanceM: 490 },
    { name: 'Karma Kafe', category: 'restaurant', cuisine: 'american', distanceM: 660 },
  ],
  confirmedSources: 0,
};

// ─── Shared card shell ─────────────────────────────────────────────────────────

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl shadow-sm shadow-purple-900/5 ${className}`}>
      {children}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{children}</p>;
}

// ─── Locked / Empty placeholder ───────────────────────────────────────────────

function LockedCard({
  title,
  icon: Icon,
  action,
  onAction,
  className = '',
}: {
  title: string;
  icon: React.ElementType;
  action: string;
  onAction?: () => void;
  className?: string;
}) {
  return (
    <Card className={`flex flex-col items-center justify-center gap-3 min-h-[160px] opacity-60 hover:opacity-80 transition-opacity ${className}`}>
      <div className="w-12 h-12 rounded-full bg-purple-50 flex items-center justify-center">
        <Icon className="w-5 h-5 text-purple-400" />
      </div>
      <div className="text-center px-4">
        <p className="text-sm font-semibold text-slate-700">{title}</p>
        <p className="text-xs text-slate-400 mt-0.5">No data yet</p>
      </div>
      <button
        onClick={onAction}
        className="text-xs font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5"
      >
        {action} <ArrowRight className="w-3 h-3" />
      </button>
    </Card>
  );
}

// ─── Weekly Pulse card (gradient) ─────────────────────────────────────────────

function WeeklyPulseCard({ dashboard, onNominateZip }: { dashboard: DashboardData | null; onNominateZip?: () => void }) {
  if (!dashboard?.pulseHeadline) {
    return <LockedCard title="Weekly Pulse" icon={TrendingUp} action="Load Business" className="h-full" />;
  }

  const metrics = dashboard.keyMetrics
    ? Object.entries(dashboard.keyMetrics).map(([label, value]) => ({ label, value }))
    : [];

  if (dashboard.isNational) {
    return (
      <div className="bg-gradient-to-br from-amber-700 to-orange-600 rounded-2xl p-6 flex flex-col justify-between h-full shadow-lg shadow-amber-900/20 text-white">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-amber-200">National Benchmarks</p>
            <span className="text-[9px] font-bold uppercase tracking-widest bg-amber-600/40 px-1.5 py-0.5 rounded text-amber-100">BLS · USDA</span>
          </div>
          <p className="text-white font-black text-lg mt-2 leading-snug">{dashboard.pulseHeadline}</p>
          <p className="text-amber-200 text-xs mt-2 leading-relaxed">Local weekly pulse unavailable — zip 07030 not yet monitored</p>
        </div>
        {metrics.length > 0 && (
          <div className="mt-4">
            <MiniBar data={metrics} colors={['#fde68a', '#fcd34d', '#fbbf24', '#f59e0b']} />
          </div>
        )}
        {onNominateZip && (
          <button
            onClick={onNominateZip}
            className="mt-4 flex items-center justify-center gap-2 bg-white/15 hover:bg-white/25 border border-white/25 text-white px-4 py-2.5 rounded-xl text-xs font-bold transition-colors"
          >
            <MapPin className="w-3.5 h-3.5" /> Get local data — nominate this zip
          </button>
        )}
      </div>
    );
  }

  const COLORS = ['#c4b5fd', '#a78bfa', '#8b5cf6', '#7c3aed'];

  return (
    <div className="bg-gradient-to-br from-purple-900 to-violet-800 rounded-2xl p-6 flex flex-col justify-between h-full shadow-lg shadow-purple-900/20 text-white">
      <div>
        <Label>Weekly Pulse</Label>
        <p className="text-white font-black text-xl mt-2 leading-tight">{dashboard.pulseHeadline}</p>
        {dashboard.confirmedSources && (
          <p className="text-purple-300 text-xs mt-2">{dashboard.confirmedSources} verified sources</p>
        )}
      </div>
      {metrics.length > 0 && (
        <div className="mt-4">
          <MiniBar data={metrics} colors={COLORS} />
        </div>
      )}
    </div>
  );
}

// ─── Market Position card ──────────────────────────────────────────────────────

function MarketPositionCard({ dashboard }: { dashboard: DashboardData | null }) {
  if (!dashboard?.stats) {
    return <LockedCard title="Market Position" icon={Users} action="Load Business" />;
  }
  const { stats } = dashboard;
  const items = [
    { label: 'Competitors Nearby', value: stats.competitorCount ?? '—', accent: 'text-purple-700' },
    { label: 'Median Income', value: stats.medianIncome ?? '—', accent: 'text-emerald-600' },
    { label: 'Population', value: stats.population ?? '—', accent: 'text-sky-600' },
    { label: 'Location', value: stats.city && stats.state ? `${stats.city}, ${stats.state}` : '—', accent: 'text-slate-700' },
  ];
  return (
    <Card className="p-5">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 flex-shrink-0">
          <MapPin className="w-4 h-4 text-purple-400" />
          <Label>Market Position</Label>
        </div>
        <div className="flex-1 grid grid-cols-4 gap-4">
          {items.map(({ label, value, accent }) => (
            <div key={label} className="bg-purple-50/60 rounded-xl px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{label}</p>
              <p className={`text-xl font-black mt-0.5 ${accent}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

// ─── Margin Analysis card (full-width, border-left) ────────────────────────────

function MarginCard({ margin, onRun }: { margin: MarginData | null; onRun?: () => void }) {
  if (!margin) {
    return (
      <LockedCard
        title="Margin Analysis"
        icon={DollarSign}
        action="Run Cost Analysis"
        onAction={onRun}
        className="min-h-[200px]"
      />
    );
  }
  const cats = Object.values(margin.categories ?? {});
  const scoreColor = (margin.overall_score ?? 0) >= 70 ? 'text-emerald-600' : (margin.overall_score ?? 0) >= 50 ? 'text-amber-500' : 'text-red-500';

  return (
    <Card className="p-6 border-l-4 border-purple-700 h-full flex flex-col">
      <div className="flex justify-between items-start mb-4">
        <div>
          <Label>Margin Analysis</Label>
          <h3 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Food Cost Breakdown</h3>
          {margin.top_opportunity && (
            <p className="text-slate-500 text-xs mt-1 max-w-xs leading-relaxed">{margin.top_opportunity}</p>
          )}
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          <span className={`block text-3xl font-black ${scoreColor}`}>{margin.overall_score ?? '—'}</span>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">/100</span>
          {margin.annual_leakage && (
            <div className="mt-0.5 text-xs font-bold text-red-500">
              ${(margin.annual_leakage / 1000).toFixed(0)}k/yr leak
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 grid grid-cols-2 gap-3">
        {cats.map((cat, i) => {
          const pct = cat.margin_pct ?? 0;
          const color = pct >= 75 ? 'bg-emerald-500' : pct >= 60 ? 'bg-purple-600' : 'bg-amber-500';
          return (
            <div key={i} className="p-4 rounded-xl bg-slate-50 border border-slate-100 flex flex-col justify-between">
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{cat.label ?? `Cat ${i + 1}`}</p>
                <p className="text-2xl font-black text-slate-900 mt-1">{pct.toFixed(1)}%</p>
              </div>
              <div>
                <div className="w-full bg-slate-200 h-1.5 mt-3 rounded-full overflow-hidden">
                  <div className={`${color} h-full rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Cost: {(cat.cost_pct ?? 0).toFixed(1)}%</p>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── AI Tools card ─────────────────────────────────────────────────────────────

function AiToolsCard({ tools }: { tools: AiTool[] | null | undefined }) {
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
        {tools.map((t, i) => (
          <div key={i} className="rounded-xl border border-slate-100 p-4 hover:border-purple-200 hover:bg-purple-50/30 transition-all group flex flex-col">
            <div className="flex items-center gap-2.5 mb-2">
              {t.url ? (
                <img
                  src={`${new URL(t.url).origin}/favicon.ico`}
                  alt=""
                  className="w-5 h-5 rounded object-contain"
                  onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <div className="w-5 h-5 rounded bg-purple-100 flex items-center justify-center">
                  <Zap className="w-3 h-3 text-purple-500" />
                </div>
              )}
              {t.url ? (
                <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-sm font-bold text-slate-800 group-hover:text-purple-700 transition-colors flex items-center gap-1">
                  {t.tool} <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </a>
              ) : (
                <span className="text-sm font-bold text-slate-800">{t.tool}</span>
              )}
            </div>
            <p className="text-xs text-slate-500 leading-relaxed">{t.capability}</p>
            {t.actionForOwner && (
              <p className="text-[10px] font-bold text-purple-600 mt-2 flex items-center gap-1">
                <ChevronRight className="w-3 h-3" /> {t.actionForOwner}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Week Calendar card ────────────────────────────────────────────────────────

const DAY_KEYWORDS: Record<string, string[]> = {
  Mon: ['monday', 'mon '],
  Tue: ['tuesday', 'tue '],
  Wed: ['wednesday', 'wed '],
  Thu: ['thursday', 'thu '],
  Fri: ['friday', 'fri '],
  Sat: ['saturday', 'sat '],
  Sun: ['sunday', 'sun ', 'easter', 'brunch'],
};
const DOT_COLORS = ['bg-purple-500', 'bg-violet-500', 'bg-indigo-500', 'bg-sky-500', 'bg-teal-500', 'bg-emerald-500', 'bg-amber-500'];

function WeekCalendarCard({ events }: { events: Event[] | null | undefined }) {
  if (!events?.length) {
    return <LockedCard title="This Week's Events" icon={Calendar} action="Load Business" />;
  }
  const assignedEvents = events.map((ev, idx) => {
    const lower = (ev.what + ' ' + ev.when).toLowerCase();
    const day = Object.entries(DAY_KEYWORDS).find(([, kws]) => kws.some(kw => lower.includes(kw)))?.[0] ?? null;
    return { ...ev, day, color: DOT_COLORS[idx % DOT_COLORS.length] };
  });
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <Label>This Week's Events</Label>
        <Calendar className="w-4 h-4 text-purple-300" />
      </div>
      <div className="grid grid-cols-7 gap-1 mb-4">
        {DAYS.map(day => {
          const dayEvents = assignedEvents.filter(e => e.day === day);
          const isToday = new Date().toLocaleDateString('en-US', { weekday: 'short' }).slice(0, 3) === day;
          return (
            <div
              key={day}
              className={`rounded-xl p-2 text-center transition-all ${isToday ? 'bg-purple-700 text-white' : 'bg-slate-50 text-slate-600'}`}
            >
              <p className="text-[10px] font-bold uppercase">{day}</p>
              <div className="flex justify-center gap-0.5 mt-1.5 flex-wrap">
                {dayEvents.map((e, i) => (
                  <div key={i} className={`w-2 h-2 rounded-full ${e.color}`} title={e.what} />
                ))}
                {dayEvents.length === 0 && <div className="w-2 h-2 rounded-full bg-slate-200" />}
              </div>
            </div>
          );
        })}
      </div>
      <div className="space-y-2">
        {assignedEvents.slice(0, 4).map((e, i) => (
          <div key={i} className="flex items-start gap-2.5 text-xs">
            <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${e.color}`} />
            <div>
              <span className="font-bold text-slate-700">{e.what}</span>
              {e.day && <span className="text-purple-600 font-semibold ml-1.5">· {e.day}</span>}
              <p className="text-slate-400 leading-tight mt-0.5">{e.when}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Community Buzz card ───────────────────────────────────────────────────────

function BuzzCard({ buzz, insights }: { buzz: string | null | undefined; insights: Insight[] | null | undefined }) {
  if (!buzz && !insights?.length) {
    return <LockedCard title="Community & Insights" icon={Activity} action="Load Business" />;
  }
  return (
    <Card className="p-6">
      <Label>Community Pulse</Label>
      {buzz && (
        <p className="text-sm text-slate-600 mt-3 leading-relaxed border-l-2 border-amber-400 pl-3">{buzz}</p>
      )}
      {insights?.length ? (
        <div className="mt-4 space-y-3">
          {insights.slice(0, 3).map((ins, i) => (
            <div key={i} className="rounded-xl bg-violet-50 border border-violet-100 p-3">
              <p className="text-xs font-bold text-violet-800">{ins.title}</p>
              <p className="text-xs text-violet-600 mt-0.5 leading-relaxed">{ins.recommendation}</p>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}

// ─── SEO Health card ───────────────────────────────────────────────────────────

function SeoCard({ seo, onRun }: { seo: SeoData | null; onRun?: () => void }) {
  if (!seo) {
    return <LockedCard title="SEO Health" icon={Globe} action="Run SEO Check" onAction={onRun} />;
  }
  const score = seo.overallScore ?? 0;
  const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
  const high = seo.findings?.filter(f => f.severity === 'high').length ?? 0;
  return (
    <Card className="p-6">
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

// ─── Map card ─────────────────────────────────────────────────────────────────

function MapCard({ business }: { business: Business | null }) {
  if (!business?.lat || !business?.lng) {
    return (
      <LockedCard title="Location Map" icon={MapPin} action="Load Business" className="h-full" />
    );
  }
  const query = business.address
    ? `${business.name}, ${business.address}`
    : `${business.lat},${business.lng}`;
  const src = `https://www.google.com/maps?q=${encodeURIComponent(query)}&z=15&output=embed`;

  return (
    <div className="relative w-full h-full rounded-2xl overflow-hidden shadow-sm shadow-purple-900/5 min-h-[260px]">
      <iframe
        key={src}
        src={src}
        className="absolute inset-0 w-full h-full border-0"
        title="Business location"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      {/* Business name overlay */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-4">
        <p className="text-white font-bold text-sm truncate">{business.name}</p>
        {business.address && (
          <p className="text-white/70 text-xs truncate mt-0.5">{business.address}</p>
        )}
      </div>
    </div>
  );
}

// ─── Nearby Competitors strip (compact) ───────────────────────────────────────

function CompetitorsStrip({ competitors }: { competitors: Competitor[] | null | undefined }) {
  if (!competitors?.length) return null;
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 flex-shrink-0">
        {competitors.length} nearby rivals:
      </span>
      {competitors.map((c, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1.5 bg-white border border-slate-100 rounded-full px-3 py-1 text-xs text-slate-600 shadow-sm"
        >
          <span className="font-semibold text-slate-800">{c.name}</span>
          <span className="text-slate-400">
            {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}
          </span>
        </span>
      ))}
    </div>
  );
}

// ─── Locked analysis card (sign-in gate) ──────────────────────────────────────
// Renders actual card content blurred behind a lock overlay. Shows what the user
// is missing without fabricating separate teaser data.

function LockedAnalysisCard({
  children,
  title,
  subtitle,
  onSignIn,
}: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  onSignIn?: () => void;
}) {
  return (
    <div className="relative rounded-2xl overflow-hidden h-full min-h-[240px] border border-slate-100 shadow-sm shadow-purple-900/5 bg-white">
      {/* Blurred card content — visible hint of what's behind */}
      <div className="absolute inset-0 pointer-events-none select-none" style={{ filter: 'blur(5px)', opacity: 0.25 }}>
        {children}
      </div>
      {/* Frosted overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-white/70 backdrop-blur-[3px]">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-100 to-violet-100 flex items-center justify-center shadow-sm">
          <Lock className="w-5 h-5 text-purple-600" />
        </div>
        <div className="text-center px-8">
          <p className="text-sm font-bold text-slate-800">Unlock {title}</p>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            {subtitle ?? 'Sign in and create your business profile to run this analysis'}
          </p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <button
            onClick={onSignIn}
            className="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white px-6 py-2.5 rounded-xl text-xs font-bold shadow-md shadow-purple-900/20 transition-all hover:scale-[1.02] active:scale-95"
          >
            <LogIn className="w-3.5 h-3.5" /> Sign in with Google
          </button>
          <p className="text-[10px] text-slate-400">Free · No credit card required</p>
        </div>
      </div>
    </div>
  );
}

// ─── Foot Traffic report card ─────────────────────────────────────────────────

const TrafficBar = dynamic(() => import('recharts').then(m => {
  const { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } = m;
  const C = ({ data, colorFn }: { data: { label: string; value: number }[]; colorFn?: (v: number) => string }) => (
    <ResponsiveContainer width="100%" height={100}>
      <BarChart data={data} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis hide domain={[0, 110]} />
        <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,.08)', fontSize: 11 }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={24}>
          {data.map((d, i) => (
            <Cell key={i} fill={colorFn ? colorFn(d.value) : '#7c3aed'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
  C.displayName = 'TrafficBar';
  return C;
}), { ssr: false });

function FootTrafficCard({ traffic }: { traffic: TrafficData }) {
  const scoreColor = traffic.weeklyScore >= 75 ? 'text-emerald-600' : traffic.weeklyScore >= 50 ? 'text-amber-500' : 'text-red-500';
  const barColor = (v: number) => v >= 80 ? '#7c3aed' : v >= 50 ? '#a78bfa' : '#ddd6fe';

  const dayData  = traffic.byDay.map(d => ({ label: d.day, value: d.score }));
  const hourData = traffic.hourly.map(d => ({ label: d.hour, value: d.score }));

  return (
    <Card className="p-6 border-l-4 border-sky-500 h-full flex flex-col">
      <div className="flex justify-between items-start mb-4">
        <div>
          <Label>Foot Traffic Forecast</Label>
          <h3 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Weekly Traffic Analysis</h3>
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          <span className={`block text-3xl font-black ${scoreColor}`}>{traffic.weeklyScore}</span>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">/100</span>
        </div>
      </div>

      {/* Key stats row */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Peak Day</p>
          <p className="text-base font-black text-slate-900 mt-0.5">{traffic.peakDay}</p>
        </div>
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Peak Hour</p>
          <p className="text-base font-black text-slate-900 mt-0.5">{traffic.peakHour}</p>
        </div>
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">This Week</p>
          <p className="text-base font-black text-emerald-600 mt-0.5">+34% ↑</p>
        </div>
      </div>

      {/* Day chart */}
      <div className="mb-1">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Day of Week</p>
        <TrafficBar data={dayData} colorFn={barColor} />
      </div>

      {/* Hourly chart */}
      <div className="mb-4">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Hourly Pattern</p>
        <TrafficBar data={hourData} colorFn={barColor} />
      </div>

      {/* AI forecast */}
      <div className="mt-auto bg-sky-50 border border-sky-100 rounded-xl p-3 flex items-start gap-2.5">
        <Brain className="w-4 h-4 text-sky-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-sky-800 leading-relaxed">{traffic.forecast}</p>
      </div>
    </Card>
  );
}

// ─── Profile Setup (chat-based) ───────────────────────────────────────────────
// Conversational onboarding — Hephae asks questions, user responds inline.

interface SetupMessage {
  role: 'bot' | 'user';
  text: string;
  quickReplies?: string[];
  inputPlaceholder?: string;
  isAction?: boolean; // final CTA row
}

type SetupStep = 'confirm' | 'website' | 'menu' | 'hours' | 'done';

function ProfileSetupChat({ business }: { business: Business | null }) {
  const [step, setStep] = useState<SetupStep>('confirm');
  const [messages, setMessages] = useState<SetupMessage[]>([
    {
      role: 'bot',
      text: `I found **${business?.name ?? 'your business'}** at ${business?.address ?? 'unknown address'}. Is this your business?`,
      quickReplies: ["Yes, that's mine", 'No, search again'],
    },
  ]);
  const [inputVal, setInputVal] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 60);

  const addUserMessage = (text: string) => {
    setMessages(prev => [...prev, { role: 'user', text }]);
    scrollToBottom();
  };

  const addBotMessage = (msg: Omit<SetupMessage, 'role'>) => {
    setMessages(prev => [...prev, { role: 'bot', ...msg }]);
    scrollToBottom();
  };

  const handleQuickReply = (reply: string) => {
    addUserMessage(reply);

    if (step === 'confirm') {
      if (reply.startsWith('Yes')) {
        setStep('website');
        setTimeout(() => addBotMessage({
          text: `I found a website at **${business?.officialUrl ?? 'unknown'}** — is that still current?`,
          quickReplies: ['Yes, that\'s correct', 'No, let me update it'],
        }), 400);
      } else {
        addBotMessage({ text: 'No problem — use the search bar in the left sidebar to find the right business.' });
      }
    } else if (step === 'website') {
      setStep('menu');
      setTimeout(() => addBotMessage({
        text: 'Can you share your menu URL? This powers the Margin Analysis. DoorDash, Toast, your own website — anything works. Or skip for now.',
        inputPlaceholder: 'https://your-menu-or-doordash-link…',
        quickReplies: ['Skip for now'],
      }), 400);
    } else if (step === 'menu' && reply === 'Skip for now') {
      setStep('hours');
      setTimeout(() => addBotMessage({
        text: "What are your typical operating hours? Just a rough answer works — e.g. *Tue–Sun 11am–10pm*.",
        inputPlaceholder: 'e.g. Mon–Fri 11am–9pm, Sat–Sun 12pm–11pm',
        quickReplies: ['Skip for now'],
      }), 400);
    } else if (step === 'hours' && reply === 'Skip for now') {
      setStep('done');
      setTimeout(() => addBotMessage({
        text: "All set! I'm ready to run your first analysis. Pick one to start — it takes about 30 seconds.",
        isAction: true,
      }), 400);
    }
  };

  const handleInputSubmit = () => {
    const val = inputVal.trim();
    if (!val) return;
    setInputVal('');
    addUserMessage(val);

    if (step === 'menu') {
      setStep('hours');
      setTimeout(() => addBotMessage({
        text: "Got it! Now, what are your typical operating hours? e.g. *Tue–Sun 11am–10pm*. Skip if you prefer.",
        inputPlaceholder: 'e.g. Mon–Fri 11am–9pm, Sat–Sun 12pm–11pm',
        quickReplies: ['Skip for now'],
      }), 400);
    } else if (step === 'hours') {
      setStep('done');
      setTimeout(() => addBotMessage({
        text: "Perfect! I'm ready to start. Pick your first analysis — it takes about 30 seconds.",
        isAction: true,
      }), 400);
    }
  };

  // Determine which step's input/replies are currently active (last bot message)
  const lastBot = [...messages].reverse().find(m => m.role === 'bot');
  const activeQuickReplies = lastBot?.quickReplies ?? [];
  const activePlaceholder = lastBot?.inputPlaceholder;
  const showTextInput = !!activePlaceholder && step !== 'done';
  const showDoneActions = lastBot?.isAction;

  const ANALYSIS_ACTIONS = [
    { label: 'Margin Analysis', icon: DollarSign, color: 'bg-purple-700 hover:bg-purple-800' },
    { label: 'SEO Health Check', icon: Globe, color: 'bg-violet-700 hover:bg-violet-800' },
    { label: 'Foot Traffic', icon: BarChart3, color: 'bg-sky-700 hover:bg-sky-800' },
  ];

  return (
    <div className="max-w-xl mx-auto">
      {/* Chat thread */}
      <div className="space-y-4 mb-4 max-h-[520px] overflow-y-auto custom-scrollbar pr-1">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} gap-3`}>
            {m.role === 'bot' && (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-700 to-violet-600 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-md">
                <Sparkles className="w-3.5 h-3.5 text-white" />
              </div>
            )}
            <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
              m.role === 'user'
                ? 'bg-purple-700 text-white rounded-tr-sm shadow-purple-900/10'
                : 'bg-white text-slate-700 rounded-tl-sm shadow-purple-900/5 border border-slate-100'
            }`}
              dangerouslySetInnerHTML={{ __html: m.text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>') }}
            />
          </div>
        ))}

        {/* Quick replies */}
        {activeQuickReplies.length > 0 && step !== 'done' && (
          <div className="flex gap-2 flex-wrap pl-11">
            {activeQuickReplies.map(r => (
              <button
                key={r}
                onClick={() => handleQuickReply(r)}
                className="bg-purple-50 hover:bg-purple-100 border border-purple-200 text-purple-700 px-4 py-2 rounded-xl text-xs font-semibold transition-colors"
              >
                {r}
              </button>
            ))}
          </div>
        )}

        {/* Text input for open answers */}
        {showTextInput && (
          <div className="pl-11">
            <div className="flex gap-2">
              <input
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleInputSubmit()}
                placeholder={activePlaceholder}
                className="flex-1 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-700 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-300/30 shadow-sm"
              />
              <button
                onClick={handleInputSubmit}
                disabled={!inputVal.trim()}
                className="bg-purple-700 hover:bg-purple-800 disabled:opacity-40 text-white px-4 py-2.5 rounded-xl transition-colors flex-shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Final analysis CTA */}
        {showDoneActions && (
          <div className="pl-11 flex gap-3 flex-wrap">
            {ANALYSIS_ACTIONS.map(({ label, icon: Icon, color }) => (
              <button
                key={label}
                className={`flex items-center gap-2 ${color} text-white px-4 py-2.5 rounded-xl text-xs font-bold shadow-md transition-all hover:scale-[1.02] active:scale-95`}
              >
                <Icon className="w-3.5 h-3.5" /> {label}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Progress dots */}
      <div className="flex items-center gap-2 justify-center mt-6">
        {(['confirm', 'website', 'menu', 'hours', 'done'] as SetupStep[]).map((s) => (
          <div
            key={s}
            className={`rounded-full transition-all ${
              s === step ? 'w-4 h-2 bg-purple-600' : 'w-2 h-2 bg-slate-200'
            }`}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Nominate Zip modal ────────────────────────────────────────────────────────

function NominateZipModal({ zipCode, onClose }: { zipCode: string; onClose: () => void }) {
  const [submitted, setSubmitted] = useState(false);

  if (submitted) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
        <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-sm w-full mx-4 text-center" onClick={e => e.stopPropagation()}>
          <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-7 h-7 text-emerald-600" />
          </div>
          <h3 className="text-lg font-black text-slate-900">Nomination submitted!</h3>
          <p className="text-sm text-slate-500 mt-2">Zip <span className="font-bold text-slate-700">{zipCode}</span> is in the queue. We'll add it to the weekly pipeline within 24 hours.</p>
          <button onClick={onClose} className="mt-6 w-full bg-purple-700 text-white py-3 rounded-xl text-sm font-bold hover:bg-purple-800 transition-all">Done</button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-2xl p-8 shadow-2xl max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-black text-slate-900">Nominate zip for monitoring</h3>
            <p className="text-xs text-slate-500 mt-1">We'll add weekly pulse coverage for this area</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs font-bold text-slate-600 uppercase tracking-widest mb-1.5 block">Zip Code</label>
            <input defaultValue={zipCode} className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold text-slate-800 focus:outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-100" />
          </div>
          <div>
            <label className="text-xs font-bold text-slate-600 uppercase tracking-widest mb-1.5 block">Business type in this area</label>
            <select className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 bg-white focus:outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-100">
              <option>Restaurant / Food & Beverage</option>
              <option>Retail</option>
              <option>Service Business</option>
              <option>Healthcare</option>
              <option>Other</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-bold text-slate-600 uppercase tracking-widest mb-1.5 block">Your role</label>
            <select className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 bg-white focus:outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-100">
              <option>Business owner</option>
              <option>Manager</option>
              <option>Consultant / Advisor</option>
              <option>Other</option>
            </select>
          </div>
        </div>
        <div className="mt-6 bg-amber-50 border border-amber-100 rounded-xl p-3 flex items-start gap-2 mb-5">
          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-700">Nominations are reviewed before activation. You'll be emailed when coverage goes live.</p>
        </div>
        <button onClick={() => setSubmitted(true)} className="w-full bg-purple-700 text-white py-3 rounded-xl text-sm font-bold hover:bg-purple-800 transition-all flex items-center justify-center gap-2 shadow-md shadow-purple-900/15">
          <MapPin className="w-4 h-4" /> Submit Nomination
        </button>
      </div>
    </div>
  );
}

// ─── Bottom Intelligence Banner ────────────────────────────────────────────────

function IntelligenceBanner({
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
    <div className="fixed bottom-0 left-56 right-96 z-40 px-6 pb-4">
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

// ─── Right Rail (simplified chat/assistant) ────────────────────────────────────

interface RailMessage { role: 'user' | 'assistant'; text: string; }

function RightRail({
  business,
  onRunAnalysis,
}: {
  business: Business | null;
  onRunAnalysis: (type: string) => void;
}) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<RailMessage[]>([
    { role: 'assistant', text: business ? `I'm analyzing **${business.name}**. What would you like to explore?` : 'Search for a business to get started. Type a business name or address below.' },
  ]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const QUICK_ACTIONS = [
    { label: 'Margin Analysis', id: 'margin', icon: DollarSign },
    { label: 'SEO Check', id: 'seo', icon: Globe },
    { label: 'Foot Traffic', id: 'traffic', icon: BarChart3 },
    { label: 'Competitive Intel', id: 'competitive', icon: Flame },
  ];

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text }]);
    setLoading(true);
    // Stub: replace with real /api/chat call when wiring up
    await new Promise(r => setTimeout(r, 600));
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: `I'm a preview stub — the full AI chat will be wired in when this layout moves to the main page. For now, use the quick actions above to explore.`,
    }]);
    setLoading(false);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }, [input, loading]);

  return (
    <aside className="fixed right-0 top-16 h-[calc(100vh-64px)] w-96 bg-[#f8f9ff] border-l border-purple-100/60 flex flex-col z-40">
      {/* Header */}
      <div className="px-5 py-4 border-b border-purple-100/60 flex items-center justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-widest text-purple-700">AI Concierge</p>
          {business && <p className="text-[10px] text-slate-400 mt-0.5 truncate">{business.name}</p>}
        </div>
        <Sparkles className="w-4 h-4 text-purple-300" />
      </div>

      {/* Quick actions */}
      <div className="px-4 pt-4 pb-2 grid grid-cols-2 gap-2">
        {QUICK_ACTIONS.map(({ label, id, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onRunAnalysis(id)}
            disabled={!business}
            className="flex items-center gap-1.5 bg-white rounded-xl px-3 py-2.5 text-xs font-semibold text-slate-600 border border-slate-100 hover:border-purple-200 hover:text-purple-700 hover:bg-purple-50/50 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 custom-scrollbar">
        {messages.map((m, i) => (
          <div key={i} className={`${m.role === 'user' ? 'ml-6' : 'mr-4'}`}>
            <div className={`rounded-xl rounded-${m.role === 'user' ? 'tr' : 'tl'}-none p-3 text-xs leading-relaxed shadow-sm ${
              m.role === 'user'
                ? 'bg-purple-700 text-white shadow-purple-900/10'
                : 'bg-white text-slate-600 shadow-purple-900/5'
            }`}>
              {m.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 mr-4">
            <div className="bg-white rounded-xl rounded-tl-none p-3 shadow-sm">
              <div className="flex gap-1">
                {[0,1,2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-purple-300 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-20 pt-3 border-t border-purple-100/60">
        <div className="relative">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            placeholder="Ask anything about this business…"
            className="w-full bg-white border border-slate-200 rounded-xl py-3 pl-4 pr-10 text-sm text-slate-700 placeholder-slate-300 shadow-sm focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-400/20"
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-purple-600 disabled:text-slate-300 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-center text-slate-400 mt-2">Hephae AI · Full chat in main app</p>
      </div>
    </aside>
  );
}

// ─── Left Sidebar ──────────────────────────────────────────────────────────────

type ActiveSection = 'overview' | 'margin' | 'seo' | 'traffic' | 'competitive';

const GATED_SECTIONS: ActiveSection[] = ['margin', 'seo', 'traffic', 'competitive'];

function LeftSidebar({
  active,
  onSelect,
  onSearch,
  showNominateZip,
  onNominateZip,
  isLoggedIn = true,
}: {
  active: ActiveSection;
  onSelect: (s: ActiveSection) => void;
  onSearch: (query: string) => void;
  showNominateZip?: boolean;
  onNominateZip?: () => void;
  isLoggedIn?: boolean;
}) {
  const [q, setQ] = useState('');

  const NAV: { id: ActiveSection; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'margin', label: 'Margin', icon: DollarSign },
    { id: 'seo', label: 'SEO Health', icon: Globe },
    { id: 'traffic', label: 'Foot Traffic', icon: TrendingUp },
    { id: 'competitive', label: 'Competitive', icon: Flame },
  ];

  return (
    <aside className="fixed left-0 top-16 h-[calc(100vh-64px)] w-56 bg-white border-r border-purple-100/60 flex flex-col p-4 gap-2 z-40">
      {/* Search */}
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
        <input
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { onSearch(q); setQ(''); } }}
          placeholder="Search business…"
          className="w-full bg-purple-50/60 border border-purple-100 rounded-xl pl-8 pr-3 py-2 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:border-purple-400 focus:ring-1 focus:ring-purple-300/30"
        />
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1">
        {NAV.map(({ id, label, icon: Icon }) => {
          const isLocked = !isLoggedIn && GATED_SECTIONS.includes(id);
          return (
            <div key={id} className="relative group/navitem">
              <button
                onClick={() => !isLocked && onSelect(id)}
                disabled={isLocked}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-widest transition-all text-left ${
                  isLocked
                    ? 'text-slate-400 cursor-not-allowed opacity-50'
                    : active === id
                      ? 'bg-white text-purple-700 shadow-sm shadow-purple-900/8 border border-purple-100'
                      : 'text-slate-500 hover:bg-purple-50/60 hover:text-purple-600 hover:translate-x-0.5'
                }`}
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">{label}</span>
                {isLocked && <Lock className="w-3 h-3 opacity-70 flex-shrink-0" />}
              </button>
              {isLocked && (
                <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 hidden group-hover/navitem:block z-50 pointer-events-none">
                  <div className="bg-slate-800 text-white text-[10px] font-semibold px-2.5 py-1.5 rounded-lg whitespace-nowrap shadow-lg">
                    Sign in to unlock
                    <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="mt-auto pt-4 border-t border-slate-100 space-y-3">
        {showNominateZip && (
          <button
            onClick={onNominateZip}
            className="w-full flex items-center justify-center gap-2 bg-amber-50 border border-amber-200 text-amber-700 rounded-xl px-3 py-2.5 text-xs font-bold hover:bg-amber-100 transition-colors"
          >
            <MapPin className="w-3.5 h-3.5" /> Nominate this zip
          </button>
        )}
        <div>
          <div className="text-[9px] font-bold uppercase tracking-widest text-slate-400 px-3 mb-2">Data Sources</div>
          <div className="flex flex-wrap gap-1 px-2">
            {['BLS', 'USDA', 'Census', 'NWS', 'OSM', 'IRS'].map(s => (
              <span key={s} className="text-[9px] font-bold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded">{s}</span>
            ))}
          </div>
          <p className="text-[9px] text-slate-400 px-3 mt-2">12 verified data sources</p>
        </div>
      </div>
    </aside>
  );
}

// ─── Scenario type (used by TopNav + MainPage) ────────────────────────────────
type Scenario = 'monitored' | 'unmonitored' | 'logged-out' | 'profile-setup' | 'with-report' | 'blank';

// ─── Top Nav ───────────────────────────────────────────────────────────────────

function TopNav({
  business,
  scenario,
  scenarios,
  onSwitchScenario,
}: {
  business: Business | null;
  scenario: Scenario;
  scenarios: { id: Scenario; label: string; description: string }[];
  onSwitchScenario: (s: Scenario) => void;
}) {
  const SCENARIO_STYLES: Record<Scenario, string> = {
    monitored:     'bg-emerald-50 border-emerald-200 text-emerald-700',
    unmonitored:   'bg-amber-50 border-amber-200 text-amber-700',
    'logged-out':  'bg-purple-50 border-purple-200 text-purple-700',
    'profile-setup':'bg-violet-50 border-violet-200 text-violet-700',
    'with-report': 'bg-sky-50 border-sky-200 text-sky-700',
    blank:         'bg-slate-100 border-slate-200 text-slate-500',
  };
  const SCENARIO_DOT: Record<Scenario, string> = {
    monitored:      'bg-emerald-400',
    unmonitored:    'bg-amber-400',
    'logged-out':   'bg-purple-400',
    'profile-setup':'bg-violet-400',
    'with-report':  'bg-sky-400',
    blank:          'bg-slate-300',
  };

  return (
    <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl flex justify-between items-center px-6 h-16 shadow-sm shadow-purple-900/5 border-b border-purple-100/40">
      {/* Left: Logo + business context */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-700 to-violet-600 flex items-center justify-center shadow-md">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-xl font-black tracking-tighter text-purple-900">hephae</span>
        </div>
        {business && (
          <div className="hidden md:flex items-center gap-2.5 bg-purple-50/80 px-3.5 py-1.5 rounded-xl border border-purple-100">
            <Building2 className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <div>
              <span className="text-sm font-bold text-slate-800">{business.name}</span>
              {business.address && (
                <span className="text-[10px] text-slate-400 ml-2">{business.address.split(',').slice(0, 2).join(',')}</span>
              )}
            </div>
            {business.officialUrl && (
              <a href={business.officialUrl} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-600 transition-colors">
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        )}
      </div>

      {/* Centre: scenario switcher */}
      <div className="flex items-center gap-1.5 bg-slate-100/80 rounded-xl p-1">
        {scenarios.map(s => (
          <button
            key={s.id}
            onClick={() => onSwitchScenario(s.id)}
            title={s.description}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              scenario === s.id
                ? `${SCENARIO_STYLES[s.id]} border shadow-sm`
                : 'text-slate-500 hover:text-slate-700 hover:bg-white/60'
            }`}
          >
            {scenario === s.id && (
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${SCENARIO_DOT[s.id]} ${s.id !== 'blank' ? 'animate-pulse' : ''}`} />
            )}
            {s.label}
          </button>
        ))}
      </div>

      {/* Right: action */}
      <div className="flex items-center gap-3">
        <p className="hidden lg:block text-[10px] text-slate-400 max-w-[180px] truncate" title={scenarios.find(s => s.id === scenario)?.description}>
          {scenarios.find(s => s.id === scenario)?.description}
        </p>
        <button className="bg-gradient-to-br from-purple-700 to-violet-600 text-white px-5 py-2 rounded-xl text-xs font-bold shadow-md shadow-purple-900/20 hover:shadow-lg hover:scale-[1.02] active:scale-95 transition-all">
          Run Analysis
        </button>
      </div>
    </nav>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

const SCENARIOS: { id: Scenario; label: string; description: string }[] = [
  { id: 'monitored',    label: 'Full data',       description: 'Nutley NJ 07110 — monitored zip, logged in, reports run' },
  { id: 'unmonitored',  label: 'No pulse',        description: 'Hoboken NJ 07030 — zip not in system' },
  { id: 'logged-out',   label: 'Logged out',      description: 'Found business, not signed in — analyses locked' },
  { id: 'profile-setup',label: 'Profile setup',   description: 'Signed in, creating business profile' },
  { id: 'with-report',  label: 'Report view',     description: 'Foot traffic report has been run' },
  { id: 'blank',        label: 'Empty',           description: 'No business loaded' },
];

export default function PreviewPage() {
  const [activeSection, setActiveSection] = useState<ActiveSection>('overview');
  const [scenario, setScenario] = useState<Scenario>('monitored');
  const [dismissedInsight, setDismissedInsight] = useState(false);

  const [showNominateModal, setShowNominateModal] = useState(false);

  // Derive state from scenario
  const hasBusiness   = scenario !== 'blank';
  const isLoggedIn    = scenario === 'monitored' || scenario === 'profile-setup' || scenario === 'with-report';
  const hasProfile    = scenario === 'monitored' || scenario === 'with-report';

  const business   = scenario === 'unmonitored' ? UNMONITORED_BUSINESS
                   : hasBusiness                ? DEMO_BUSINESS
                   : null;
  const dashboard  = scenario === 'monitored'   ? DEMO_DASHBOARD
                   : scenario === 'unmonitored' ? UNMONITORED_DASHBOARD
                   : scenario === 'logged-out'  ? DEMO_DASHBOARD   // pulse is public; analyses are gated
                   : scenario === 'with-report' ? DEMO_DASHBOARD
                   : null;
  const margin     = hasProfile ? DEMO_MARGIN : null;
  const seo        = hasProfile ? DEMO_SEO    : null;
  const traffic    = scenario === 'with-report' ? DEMO_TRAFFIC : null;

  const topInsight = !dismissedInsight ? (dashboard?.topInsights?.[0] ?? null) : null;

  // Reset banner when switching scenarios
  const switchScenario = useCallback((s: Scenario) => {
    setScenario(s);
    setDismissedInsight(false);
  }, []);

  const handleSearch = useCallback((query: string) => {
    alert(`Search stub: "${query}"\n\nIn the real implementation this calls /api/locate then /api/overview.`);
  }, []);

  const handleRunAnalysis = useCallback((type: string) => {
    const labels: Record<string, string> = {
      margin: 'Margin Analysis',
      seo: 'SEO Health Check',
      traffic: 'Foot Traffic Forecast',
      competitive: 'Competitive Intelligence',
    };
    alert(`Run ${labels[type] ?? type}\n\nStub — will call the relevant API endpoint.`);
    setActiveSection(type as ActiveSection);
  }, []);

  return (
    <div className="min-h-screen bg-[#f8f9ff] text-slate-900">
      <TopNav business={business} scenario={scenario} scenarios={SCENARIOS} onSwitchScenario={switchScenario} />
      <LeftSidebar
        active={activeSection}
        onSelect={setActiveSection}
        onSearch={handleSearch}
        showNominateZip={scenario === 'unmonitored'}
        onNominateZip={() => setShowNominateModal(true)}
        isLoggedIn={isLoggedIn}
      />
      <RightRail business={business} onRunAnalysis={handleRunAnalysis} />

      {/* Main scrollable content */}
      <main className="ml-56 mr-96 pt-24 pb-28 px-8 min-h-screen">

        {/* Page header */}
        <header className="mb-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-purple-700">
            {business ? 'Business Intelligence' : 'Preview — Search for a business to begin'}
          </p>
          <h1 className="text-4xl font-black tracking-tighter text-slate-900 mt-1">
            {business?.name ?? 'Dashboard'}
          </h1>
          {business?.persona && (
            <p className="text-slate-500 text-sm mt-1">{business.persona}</p>
          )}
          {scenario === 'unmonitored' && (
            <div className="mt-4 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm">
              <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
              </div>
              <div className="flex-1">
                <span className="font-bold text-amber-800">Zip 07030 not monitored</span>
                <span className="text-amber-600 ml-2">— weekly pulse data unavailable. Run on-demand analyses, or </span>
                <button onClick={() => setShowNominateModal(true)} className="font-bold text-amber-800 underline underline-offset-2 hover:text-amber-900">nominate this zip</button>
                <span className="text-amber-600"> to add it to the weekly pipeline.</span>
              </div>
            </div>
          )}
          {scenario === 'logged-out' && (
            <div className="mt-4 flex items-center gap-3 bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 text-sm">
              <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                <LogIn className="w-4 h-4 text-purple-600" />
              </div>
              <div className="flex-1">
                <span className="font-bold text-purple-800">Sign in to unlock analyses</span>
                <span className="text-purple-600 ml-2">— Margin, SEO, Foot Traffic, and Competitive reports require a free account.</span>
              </div>
              <button className="flex items-center gap-1.5 bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-bold hover:bg-purple-800 transition-colors flex-shrink-0">
                <LogIn className="w-3.5 h-3.5" /> Sign in
              </button>
            </div>
          )}
        </header>

        {/* Profile setup — chat-based onboarding replaces bento grid */}
        {scenario === 'profile-setup' ? (
          <ProfileSetupChat business={business} />
        ) : (

        /* Bento Grid */
        <div className="grid grid-cols-12 gap-6">

          {/* Row 1: Map (5-col) + Weekly Pulse (7-col) */}
          <div className="col-span-12 md:col-span-5" style={{ minHeight: 280 }}>
            <MapCard business={business} />
          </div>
          <div className="col-span-12 md:col-span-7" style={{ minHeight: 280 }}>
            <WeeklyPulseCard
              dashboard={dashboard}
              onNominateZip={scenario === 'unmonitored' ? () => setShowNominateModal(true) : undefined}
            />
          </div>

          {/* Row 2: Market Position (full-width compact) */}
          <div className="col-span-12">
            <MarketPositionCard dashboard={dashboard} />
          </div>

          {/* Row 3: AI Tools (6-col, always free) + Calendar (6-col) */}
          <div className="col-span-12 md:col-span-6 flex flex-col">
            {/* AI Tools is generic intel — always shown, never gated */}
            <AiToolsCard tools={dashboard?.aiTools ?? DEMO_DASHBOARD.aiTools} />
          </div>
          <div className="col-span-12 md:col-span-6 flex flex-col">
            <BuzzCard buzz={dashboard?.communityBuzz} insights={dashboard?.topInsights} />
          </div>

          {/* Row 4: Week Calendar (4-col) + Buzz moved + something */}
          <div className="col-span-12 md:col-span-4">
            <WeekCalendarCard events={dashboard?.events} />
          </div>
          <div className="col-span-12 md:col-span-8">
            {/* Nearby rivals embedded here as a card for non-locked views */}
            {dashboard?.competitors?.length ? (
              <Card className="p-5 h-full flex flex-col justify-center">
                <Label>Nearby Rivals</Label>
                <div className="mt-3">
                  <CompetitorsStrip competitors={dashboard.competitors} />
                </div>
              </Card>
            ) : null}
          </div>

          {/* Locked analyses section separator (logged-out only) */}
          {!isLoggedIn && (
            <div className="col-span-12 flex items-center gap-4 py-2">
              <div className="flex-1 h-px bg-slate-200" />
              <div className="flex items-center gap-2 bg-purple-50 border border-purple-100 rounded-full px-4 py-1.5 flex-shrink-0">
                <Lock className="w-3 h-3 text-purple-500" />
                <span className="text-xs font-semibold text-purple-600">Sign in to unlock these analyses</span>
              </div>
              <div className="flex-1 h-px bg-slate-200" />
            </div>
          )}

          {/* Row 5: Margin (6-col) + SEO (6-col) — locked for logged-out, real for logged-in */}
          <div className="col-span-12 md:col-span-6 flex flex-col">
            {!isLoggedIn ? (
              <LockedAnalysisCard title="Margin Analysis" subtitle="Sign in to see your full food cost breakdown and profit leakage">
                <MarginCard margin={DEMO_MARGIN} />
              </LockedAnalysisCard>
            ) : (
              <MarginCard margin={activeSection === 'margin' || margin ? margin : null} onRun={() => handleRunAnalysis('margin')} />
            )}
          </div>
          <div className="col-span-12 md:col-span-6 flex flex-col">
            {!isLoggedIn ? (
              <LockedAnalysisCard title="SEO Health" subtitle="Sign in to audit your Google presence score">
                <SeoCard seo={DEMO_SEO} />
              </LockedAnalysisCard>
            ) : (
              <SeoCard seo={activeSection === 'seo' || seo ? seo : null} onRun={() => handleRunAnalysis('seo')} />
            )}
          </div>

          {/* Row 6: Foot Traffic report (only in with-report scenario) */}
          {traffic && (
            <div className="col-span-12 md:col-span-8 flex flex-col">
              <FootTrafficCard traffic={traffic} />
            </div>
          )}
          {traffic && (
            <div className="col-span-12 md:col-span-4 flex flex-col">
              <LockedAnalysisCard title="Competitive Intel" subtitle="Run the competitive report to see how you rank vs nearby rivals">
                <BuzzCard buzz={DEMO_DASHBOARD.communityBuzz} insights={DEMO_DASHBOARD.topInsights} />
              </LockedAnalysisCard>
            </div>
          )}

        </div>
        )}
      </main>

      <IntelligenceBanner
        insight={topInsight}
        onApply={() => {}}
        onDismiss={() => setDismissedInsight(true)}
      />

      {showNominateModal && (
        <NominateZipModal
          zipCode={scenario === 'unmonitored' ? '07030' : '07110'}
          onClose={() => setShowNominateModal(false)}
        />
      )}

      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2d9f3; border-radius: 10px; }
      `}</style>
    </div>
  );
}
