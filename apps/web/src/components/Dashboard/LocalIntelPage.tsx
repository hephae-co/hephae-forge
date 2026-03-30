'use client';

import { Radio, TrendingUp, Users, Newspaper, FileText, Calendar, MapPin, Activity, Building2 } from 'lucide-react';
import { Card, Label } from './Card';
import FeedbackButton from '@/components/Feedback/FeedbackButton';
import type { DashboardData, DashEvent, Insight } from './types';

export function LocalIntelPage({
  dashboard,
  businessName,
  zipCode,
  businessSlug,
  vertical,
}: {
  dashboard: DashboardData | null;
  businessName?: string;
  zipCode?: string;
  businessSlug?: string;
  vertical?: string;
}) {
  const stats = dashboard?.stats;
  const events = dashboard?.events;
  const insights = dashboard?.topInsights;
  const buzz = dashboard?.communityBuzz;
  const headline = dashboard?.pulseHeadline;
  const localFacts = dashboard?.localFacts;
  const localIntel = dashboard?.localIntel;
  const competitors = dashboard?.competitors;
  const isUltralocal = dashboard && !dashboard.isNational;
  const weeklyBrief = dashboard?.weeklyBrief;
  const actionItems = dashboard?.actionItems;
  const competitorWatch = dashboard?.competitorWatch;
  const playbooks = dashboard?.playbooks;
  const researchSnippets = dashboard?.researchSnippets;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Radio className="w-5 h-5 text-purple-500" />
            <h1 className="text-2xl font-black text-slate-900">Local Intelligence</h1>
            {isUltralocal && (
              <span className="text-[9px] font-bold uppercase tracking-widest bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded">Live</span>
            )}
          </div>
          <p className="text-sm text-slate-500">
            {stats?.city && stats?.state ? `${stats.city}, ${stats.state}` : ''} {zipCode ? `(${zipCode})` : ''} — data from {dashboard?.confirmedSources || 0}+ verified sources
          </p>
        </div>
      </div>

      {/* Pulse Headline */}
      {headline && (
        <Card className="p-6 bg-gradient-to-br from-purple-50 to-violet-50 border border-purple-100">
          <Label>This Week&apos;s Pulse</Label>
          <p className="text-lg font-bold text-slate-900 mt-2 leading-snug">{headline}</p>
        </Card>
      )}

      {/* Weekly Brief — the synthesized narrative */}
      {weeklyBrief && (
        <Card className="p-6 border-l-4 border-purple-500">
          <Label>Weekly Brief</Label>
          <p className="text-sm text-slate-700 mt-2 leading-relaxed whitespace-pre-line">{weeklyBrief}</p>
        </Card>
      )}

      {/* Action Items + Competitor Watch side by side */}
      {(actionItems?.length || competitorWatch?.length) ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {actionItems && actionItems.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-emerald-500" />
                <Label>Action Items This Week</Label>
              </div>
              <Card className="p-5 h-full">
                <div className="space-y-2.5">
                  {actionItems.map((item, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <div className="w-5 h-5 rounded-full bg-emerald-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-[10px] font-black text-emerald-600">{i + 1}</span>
                      </div>
                      <p className="text-slate-700 leading-relaxed">{item}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
          {competitorWatch && competitorWatch.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Building2 className="w-4 h-4 text-orange-400" />
                <Label>Competitor Watch</Label>
              </div>
              <Card className="p-5 h-full">
                <div className="space-y-3">
                  {competitorWatch.map((c, i) => (
                    <div key={i} className="border-l-2 border-orange-300 pl-3">
                      <p className="text-sm font-semibold text-slate-800">{c.business || c.name || 'Competitor'}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{c.observation || c.change}</p>
                      {c.implication && <p className="text-xs text-orange-600 mt-1 font-medium">{c.implication}</p>}
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>
      ) : null}

      {/* Community Buzz + Events — the most immediate value */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {buzz && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Newspaper className="w-4 h-4 text-purple-400" />
              <Label>Community Buzz</Label>
              {businessSlug && (
                <FeedbackButton
                  businessSlug={businessSlug}
                  dataType="community_buzz"
                  itemId="community_buzz"
                  itemLabel="Community Buzz"
                  zipCode={zipCode}
                  vertical={vertical}
                  className="ml-auto"
                />
              )}
            </div>
            <Card className="p-5 h-full">
              <p className="text-sm text-slate-600 leading-relaxed">{buzz}</p>
            </Card>
          </div>
        )}

        {events && events.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-purple-400" />
              <Label>Local Events</Label>
            </div>
            <Card className="p-5 h-full">
              <div className="space-y-3">
                {events.map((ev, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-2 h-2 rounded-full bg-violet-400 mt-1.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-800">{ev.what}</p>
                      {ev.when && <p className="text-xs text-slate-400 mt-0.5">{ev.when}</p>}
                    </div>
                    {businessSlug && (
                      <FeedbackButton
                        businessSlug={businessSlug}
                        dataType="event"
                        itemId={`event-${i}`}
                        itemLabel={ev.what}
                        zipCode={zipCode}
                        vertical={vertical}
                      />
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </div>

      {/* Key Insights */}
      {insights && insights.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-purple-400" />
            <Label>Weekly Insights</Label>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {insights.map((ins, i) => (
              <Card key={i} className="p-5 border-l-4 border-violet-400">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-bold text-slate-800">{ins.title}</h3>
                  {businessSlug && (
                    <FeedbackButton
                      businessSlug={businessSlug}
                      dataType="pulse_insight"
                      itemId={`insight-${i}`}
                      itemLabel={ins.title}
                      zipCode={zipCode}
                      vertical={vertical}
                      className="flex-shrink-0 mt-0.5"
                    />
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{ins.recommendation}</p>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Local Facts */}
      {localFacts && localFacts.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-purple-400" />
            <Label>Discovered Facts</Label>
          </div>
          <Card className="p-5">
            <div className="space-y-2.5">
              {localFacts.map((fact, i) => (
                <div key={i} className="flex items-start gap-3 text-sm">
                  <div className="w-5 h-5 rounded-full bg-purple-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <span className="text-[10px] font-black text-purple-600">{i + 1}</span>
                  </div>
                  <p className="text-slate-700 leading-relaxed">{fact}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Market Stats */}
      {stats && (stats.population || stats.medianIncome || localIntel) && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-4 h-4 text-purple-400" />
            <Label>Market Demographics</Label>
          </div>
          <Card className="p-5">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {stats.population && (
                <div className="bg-slate-50 rounded-xl px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Population</p>
                  <p className="text-lg font-black text-slate-700 mt-0.5">{stats.population}</p>
                </div>
              )}
              {stats.medianIncome && (
                <div className="bg-slate-50 rounded-xl px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Median Income</p>
                  <p className="text-lg font-black text-emerald-600 mt-0.5">{stats.medianIncome}</p>
                </div>
              )}
              {localIntel?.spendingPower && (
                <div className="bg-slate-50 rounded-xl px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Spending Power</p>
                  <p className="text-lg font-black text-purple-600 mt-0.5 capitalize">{localIntel.spendingPower}</p>
                </div>
              )}
              {localIntel?.priceSensitivity && (
                <div className="bg-slate-50 rounded-xl px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Price Sensitivity</p>
                  <p className="text-lg font-black text-amber-600 mt-0.5 capitalize">{localIntel.priceSensitivity}</p>
                </div>
              )}
              {stats.county && (
                <div className="bg-slate-50 rounded-xl px-4 py-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">County</p>
                  <p className="text-lg font-black text-slate-600 mt-0.5">{stats.county}</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Nearby Competitors */}
      {competitors && competitors.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-purple-400" />
            <Label>Nearby Businesses ({competitors.length})</Label>
          </div>
          <Card className="p-5">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {competitors.map((c, i) => (
                <div key={i} className="flex items-center gap-2.5 bg-slate-50 rounded-xl px-3 py-2.5">
                  <MapPin className="w-3 h-3 text-slate-400 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-700 truncate">{c.name}</p>
                    <p className="text-[10px] text-slate-400">{c.cuisine || c.category} · {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Research Snippets */}
      {researchSnippets && (researchSnippets.keyFindings?.length || researchSnippets.landscape) ? (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-purple-400" />
            <Label>Industry Research</Label>
          </div>
          {researchSnippets.landscape && (
            <Card className="p-5 mb-4">
              <p className="text-sm text-slate-600 leading-relaxed">{researchSnippets.landscape}</p>
            </Card>
          )}
          {researchSnippets.keyFindings && researchSnippets.keyFindings.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              {researchSnippets.keyFindings.map((finding, i) => (
                <Card key={i} className="p-4 border-l-4 border-indigo-300">
                  <p className="text-xs text-slate-700 leading-relaxed">{finding}</p>
                </Card>
              ))}
            </div>
          )}
          {researchSnippets.recommendedReading && researchSnippets.recommendedReading.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {researchSnippets.recommendedReading.map((r, i) => (
                <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                  className="text-[10px] font-medium px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-600 hover:bg-indigo-100 transition-colors flex items-center gap-1">
                  {r.title.slice(0, 40)}{r.title.length > 40 ? '...' : ''}
                </a>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {/* Not ultralocal — CTA */}
      {!isUltralocal && (
        <Card className="p-6 bg-amber-50 border border-amber-200">
          <h3 className="text-sm font-bold text-amber-800">Want deeper local intelligence?</h3>
          <p className="text-xs text-amber-600 mt-1 leading-relaxed">
            This area is using national benchmarks. Enable ultralocal monitoring for weekly pulse updates, local news tracking, government contract alerts, and community sentiment analysis.
          </p>
        </Card>
      )}
    </div>
  );
}
