"use client";

import React from 'react';
import { Star, MapPin, Users, TrendingUp, Sparkles, BarChart3, Search, Swords, Share2, ArrowRight, Calendar, Zap } from 'lucide-react';

interface BusinessOverview {
  businessSnapshot?: {
    name: string;
    rating: number | null;
    reviewCount: number | null;
    website: string | null;
    category: string;
  };
  marketPosition?: {
    competitorCount: number;
    saturationLevel: string;
    ranking: string;
    topCompetitors: { name: string; rating: number }[];
  };
  localEconomy?: {
    medianIncome: string | null;
    population: string | null;
    keyFact: string;
  };
  localBuzz?: {
    headline: string | null;
    events: { what: string; when: string }[];
    trend: string;
  } | null;
  keyOpportunities?: { title: string; detail: string; dataPoint: string }[];
  capabilityTeasers?: {
    margin: string | null;
    traffic: string | null;
    seo: string | null;
    competitive: string | null;
    social: string | null;
  };
  // Fallback for old format
  summary?: string;
}

interface OverviewCardProps {
  overview: BusinessOverview;
  onCapabilityClick?: (capId: string) => void;
  isAuthenticated?: boolean;
}

const saturationColor: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  moderate: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  saturated: 'bg-red-100 text-red-700',
};

const CAPABILITY_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  margin: { icon: <BarChart3 className="w-4 h-4" />, label: 'Price Optimization', color: 'from-indigo-500 to-violet-500' },
  traffic: { icon: <Users className="w-4 h-4" />, label: 'Foot Traffic Forecast', color: 'from-emerald-500 to-teal-500' },
  seo: { icon: <Search className="w-4 h-4" />, label: 'Google Presence Check', color: 'from-purple-500 to-indigo-500' },
  competitive: { icon: <Swords className="w-4 h-4" />, label: 'Competitive Analysis', color: 'from-orange-500 to-red-500' },
  social: { icon: <Share2 className="w-4 h-4" />, label: 'Social Media Audit', color: 'from-pink-500 to-rose-500' },
};

export default function OverviewCard({ overview, onCapabilityClick, isAuthenticated = false }: OverviewCardProps) {
  const { businessSnapshot, marketPosition, localEconomy, localBuzz, keyOpportunities, capabilityTeasers } = overview;

  // Fallback for old-format responses
  if (!businessSnapshot && overview.summary) {
    return (
      <div className="bg-white/90 border border-gray-100 rounded-2xl p-5 shadow-sm">
        <p className="text-sm text-gray-700">{overview.summary}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3 animate-fade-in">
      {/* Business Snapshot */}
      {businessSnapshot && (
        <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-bold text-gray-900 truncate">{businessSnapshot.name}</h3>
              <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full font-medium">{businessSnapshot.category}</span>
            </div>
            {businessSnapshot.rating && (
              <div className="flex items-center gap-1 shrink-0 bg-amber-50 px-2 py-1 rounded-lg">
                <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                <span className="text-sm font-bold text-amber-700">{businessSnapshot.rating}</span>
                {businessSnapshot.reviewCount && (
                  <span className="text-xs text-amber-500">({businessSnapshot.reviewCount})</span>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Market Position + Local Economy — side by side */}
      {(marketPosition || localEconomy) && (
        <div className="grid grid-cols-2 gap-3">
          {marketPosition && (
            <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
              <div className="flex items-center gap-1.5 mb-2">
                <MapPin className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Competition</span>
              </div>
              <div className="text-2xl font-black text-gray-900">{marketPosition.competitorCount}</div>
              <div className="text-xs text-gray-500 mb-2">nearby competitors</div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${saturationColor[marketPosition.saturationLevel] || 'bg-gray-100 text-gray-600'}`}>
                {marketPosition.saturationLevel} saturation
              </span>
              {marketPosition.ranking && (
                <p className="text-xs text-gray-600 mt-2">{marketPosition.ranking}</p>
              )}
            </div>
          )}

          {localEconomy && (
            <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
              <div className="flex items-center gap-1.5 mb-2">
                <TrendingUp className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Local Economy</span>
              </div>
              {localEconomy.medianIncome && (
                <div>
                  <div className="text-2xl font-black text-gray-900">{localEconomy.medianIncome}</div>
                  <div className="text-xs text-gray-500">median income</div>
                </div>
              )}
              {localEconomy.population && (
                <div className="text-xs text-gray-600 mt-1">{localEconomy.population} residents</div>
              )}
              {localEconomy.keyFact && (
                <p className="text-xs text-indigo-600 font-medium mt-2">{localEconomy.keyFact}</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Local Buzz (only if pulse data exists) */}
      {localBuzz && localBuzz.headline && (
        <div className="bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-2xl p-4">
          <div className="flex items-center gap-1.5 mb-2">
            <Zap className="w-3.5 h-3.5 text-indigo-500" />
            <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-wider">This Week&apos;s Local Intel</span>
          </div>
          <p className="text-sm font-semibold text-gray-900 mb-2">{localBuzz.headline}</p>
          {localBuzz.events?.length > 0 && (
            <div className="space-y-1 mb-2">
              {localBuzz.events.map((ev, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <Calendar className="w-3 h-3 text-indigo-400" />
                  <span className="text-gray-700">{ev.what}</span>
                  <span className="text-gray-400">{ev.when}</span>
                </div>
              ))}
            </div>
          )}
          {localBuzz.trend && (
            <p className="text-xs text-gray-600 italic">{localBuzz.trend}</p>
          )}
        </div>
      )}

      {/* Key Opportunities */}
      {keyOpportunities && keyOpportunities.length > 0 && (
        <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
          <div className="flex items-center gap-1.5 mb-3">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Opportunities</span>
          </div>
          <div className="space-y-2.5">
            {keyOpportunities.map((opp, i) => (
              <div key={i} className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{i + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-gray-900">{opp.title}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{opp.detail}</div>
                  {opp.dataPoint && (
                    <span className="inline-block text-[10px] px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-medium mt-1">{opp.dataPoint}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Capability Teasers */}
      {capabilityTeasers && onCapabilityClick && (
        <div className="space-y-2">
          <div className="flex items-center gap-1.5 px-1">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Unlock Free Analysis</span>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {Object.entries(capabilityTeasers).map(([key, teaser]) => {
              if (!teaser) return null;
              const meta = CAPABILITY_META[key];
              if (!meta) return null;
              return (
                <button
                  key={key}
                  onClick={() => onCapabilityClick(key === 'social' ? 'marketing' : key === 'margin' ? 'surgery' : key)}
                  className="group flex items-center gap-3 p-3 bg-white border border-gray-100 rounded-xl shadow-sm hover:shadow-md hover:border-indigo-200 transition-all text-left"
                >
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${meta.color} flex items-center justify-center text-white shrink-0`}>
                    {meta.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-gray-900">{meta.label}</div>
                    <div className="text-[11px] text-gray-500 leading-snug truncate">{teaser}</div>
                  </div>
                  <div className="shrink-0 text-gray-300 group-hover:text-indigo-500 transition-colors">
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </button>
              );
            })}
          </div>
          {!isAuthenticated && (
            <p className="text-center text-xs text-gray-400 mt-2">
              Register with your email to unlock these free capabilities
            </p>
          )}
        </div>
      )}
    </div>
  );
}
