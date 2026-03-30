/**
 * Transform real API response types into simplified card-display types.
 *
 * These adapters bridge the production data shapes (SurgicalReport, SeoReport,
 * ForecastResponse, BaseIdentity) into the Amethyst dashboard card interfaces.
 */

import type { SurgicalReport, SeoReport, BaseIdentity } from '@/types/api';
import type { DashboardData, MarginCardData, SeoCardData, TrafficCardData, DashBusiness } from './types';

/** Map the /api/overview response (already close to DashboardData) */
export function toDashboardData(overview: any): DashboardData | null {
  if (!overview) return null;

  const dash = overview.dashboard ?? {};
  const market = overview.marketPosition ?? {};
  const econ = overview.localEconomy ?? {};
  const dashStats = dash.stats ?? {};

  return {
    pulseHeadline: dash.pulseHeadline ?? overview.localBuzz?.headline ?? null,
    isNational: dash.coverage !== 'ultralocal',
    keyMetrics: dash.keyMetrics,
    topInsights: dash.topInsights,
    communityBuzz: dash.communityBuzz ?? overview.localBuzz?.summary ?? null,
    events: dash.events,
    stats: {
      population: econ.population ?? dashStats.population ?? null,
      medianIncome: econ.medianIncome ?? dashStats.medianIncome ?? null,
      city: econ.city ?? dashStats.city ?? dash.city ?? null,
      state: econ.state ?? dashStats.state ?? dash.state ?? null,
      county: econ.county ?? dashStats.county ?? null,
      competitorCount: market.competitorCount ?? dash.competitors?.length ?? dashStats.competitorCount ?? undefined,
      saturationLevel: market.saturationLevel ?? dashStats.saturationLevel ?? null,
      deliveryAdoption: dashStats.deliveryAdoption ?? null,
      eventCount: dash.events?.length ?? undefined,
      weatherOutlook: dashStats.weatherOutlook ?? dash.weatherNote ?? null,
      confirmedSources: dash.confirmedSources ?? undefined,
    },
    aiTools: dash.aiTools,
    competitors: dash.competitors,
    confirmedSources: dash.confirmedSources,
    localIntel: dash.localIntel,
    localFacts: dash.localFacts,
    // Digest fields (from synthesis pipeline)
    weeklyBrief: dash.weeklyBrief ?? null,
    actionItems: dash.actionItems ?? null,
    competitorWatch: dash.competitorWatch ?? null,
    playbooks: dash.playbooks ?? null,
    personalizedTools: dash.personalizedTools ?? null,
    researchSnippets: dash.researchSnippets ?? null,
  };
}

/** Aggregate SurgicalReport menu_items into margin card categories */
export function toMarginCardData(report: SurgicalReport | null): MarginCardData | null {
  if (!report) return null;

  // Group items by category and compute weighted averages
  const buckets: Record<string, { totalCost: number; totalPrice: number; count: number }> = {};
  for (const item of report.menu_items ?? []) {
    const cat = (item as any).category?.toLowerCase() ?? 'other';
    if (!buckets[cat]) buckets[cat] = { totalCost: 0, totalPrice: 0, count: 0 };
    buckets[cat].totalCost += (item as any).estimated_cost ?? 0;
    buckets[cat].totalPrice += item.current_price ?? 0;
    buckets[cat].count += 1;
  }

  const categories: MarginCardData['categories'] = {};
  for (const [key, b] of Object.entries(buckets)) {
    const marginPct = b.totalPrice > 0 ? ((b.totalPrice - b.totalCost) / b.totalPrice) * 100 : 0;
    categories[key] = {
      margin_pct: Math.round(marginPct * 10) / 10,
      cost_pct: Math.round((100 - marginPct) * 10) / 10,
      label: key.charAt(0).toUpperCase() + key.slice(1),
    };
  }

  const totalLeakage = report.menu_items?.reduce((s, i) => s + ((i as any).price_leakage ?? 0), 0) ?? 0;

  return {
    overall_score: report.overall_score,
    annual_leakage: Math.round(totalLeakage * 12), // monthly to annual
    top_opportunity: report.strategic_advice?.[0] ?? undefined,
    categories: Object.keys(categories).length > 0 ? categories : undefined,
  };
}

/** Map SeoReport sections into the simplified card display */
export function toSeoCardData(report: SeoReport | null): SeoCardData | null {
  if (!report) return null;

  const findings = report.sections
    ?.flatMap(s =>
      s.recommendations?.map(r => ({
        title: r.title,
        severity: r.severity === 'Critical' ? 'high' : r.severity === 'Warning' ? 'medium' : 'low',
      })) ?? []
    )
    .slice(0, 6);

  return {
    overallScore: report.overallScore,
    findings,
  };
}

/** Compute summary scores from ForecastResponse slot data */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function toTrafficCardData(forecast: any | null): TrafficCardData | null {
  if (!forecast?.forecast?.length) return null;

  const days: any[] = forecast.forecast;

  // Compute day-level average scores
  const byDay = days.map((d: any) => {
    const avg = d.slots.length > 0
      ? d.slots.reduce((s: number, sl: any) => s + sl.score, 0) / d.slots.length
      : 0;
    return { day: d.dayOfWeek.slice(0, 3), score: Math.round(avg) };
  });

  // Find peak day
  const peakDayEntry = byDay.reduce((best: { day: string; score: number }, d: { day: string; score: number }) => d.score > best.score ? d : best, byDay[0]);

  // Flatten all slots to find peak hour and compute hourly averages
  const to24h = (t: string): number => {
    if (!t) return 0;
    const clean = t.trim().toUpperCase();
    const match = clean.match(/^(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?$/);
    if (!match) return 0;
    let h = parseInt(match[1]);
    const ampm = match[3];
    if (ampm === 'PM' && h !== 12) h += 12;
    if (ampm === 'AM' && h === 12) h = 0;
    return h;
  };
  const toLabel = (t: string): string => {
    const clean = t.trim();
    // Shorten "10:00 AM" → "10a", "3:00 PM" → "3p"
    const match = clean.match(/^(\d{1,2})(?::00)?\s*(AM|PM)?$/i);
    if (match) {
      const suffix = (match[2] || '').toLowerCase().charAt(0); // 'a' or 'p'
      return `${match[1]}${suffix}`;
    }
    return clean.replace(':00', '');
  };

  const hourBuckets: Record<string, { scores: number[]; sort: number }> = {};
  for (const d of days as any[]) {
    for (const sl of d.slots as any[]) {
      const raw = sl.time ?? sl.label ?? '';
      const label = toLabel(raw);
      if (!hourBuckets[label]) hourBuckets[label] = { scores: [], sort: to24h(raw) };
      hourBuckets[label].scores.push(sl.score);
    }
  }

  const hourly = Object.entries(hourBuckets)
    .map(([hour, { scores, sort }]) => ({
      hour,
      score: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length),
      _sort: sort,
    }))
    .sort((a, b) => a._sort - b._sort)
    .map(({ hour, score }) => ({ hour, score }))
    .slice(0, 12);

  const peakHourEntry = hourly.reduce((best, h) => h.score > best.score ? h : best, hourly[0] || { hour: '—', score: 0 });

  const weeklyScore = byDay.length > 0
    ? Math.round(byDay.reduce((s, d) => s + d.score, 0) / byDay.length)
    : 0;

  return {
    weeklyScore,
    peakDay: peakDayEntry?.day ?? '—',
    peakHour: peakHourEntry?.hour ?? '—',
    forecast: forecast.summary ?? 'Traffic forecast generated from multi-source analysis.',
    byDay,
    hourly,
  };
}

/** Map BaseIdentity (+ enriched fields) into DashBusiness for cards */
export function toBusiness(identity: BaseIdentity | null, overview?: any): DashBusiness | null {
  if (!identity) return null;
  const enriched = identity as any;
  const snap = overview?.businessSnapshot;
  return {
    name: identity.name,
    address: identity.address,
    officialUrl: identity.officialUrl,
    lat: identity.coordinates?.lat ?? enriched.lat,
    lng: identity.coordinates?.lng ?? enriched.lng,
    persona: snap?.persona ?? enriched.persona,
    logoUrl: enriched.logoUrl,
    favicon: enriched.favicon,
    primaryColor: enriched.primaryColor,
  };
}
