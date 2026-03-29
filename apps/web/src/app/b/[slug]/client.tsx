'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useApiClient } from '@/hooks/useApiClient';
import ChatInterface from '@/components/Chatbot/ChatInterface';
import { ChatMessage } from '@/components/Chatbot/types';
import {
  MapPin, Star, Users, TrendingUp, ExternalLink, BarChart3,
  Zap, Sparkles, Calendar, Newspaper, Activity, Building2,
  Globe, DollarSign, Flame, ArrowRight, Bot,
} from 'lucide-react';

interface PublicProfile {
  slug: string;
  name: string;
  address: string;
  identity: Record<string, any>;
  snapshot: Record<string, any>;
  publishedAt?: string;
}

function humanize(s: string): string {
  return s.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export default function BusinessProfileClient({
  slug,
  publicProfile,
}: {
  slug: string;
  publicProfile: PublicProfile | null;
}) {
  const { user, signInWithGoogle, signOut } = useAuth();
  const { apiFetch } = useApiClient();
  const [redirecting, setRedirecting] = useState(false);

  // Authenticated users → redirect to interactive app with preloaded data
  useEffect(() => {
    if (user && publicProfile?.identity) {
      setRedirecting(true);
      sessionStorage.setItem('forge_preload_slug', slug);
      sessionStorage.setItem('forge_preload_identity', JSON.stringify(publicProfile.identity));
      if (publicProfile.snapshot) {
        sessionStorage.setItem('forge_preload_snapshot', JSON.stringify(publicProfile.snapshot));
      }
      window.location.href = '/';
    }
  }, [user, publicProfile, slug]);

  useEffect(() => {
    if (!publicProfile && !user) return;
    if (!publicProfile && user) {
      fetch(`/api/b/${slug}`)
        .then(r => r.json())
        .then(data => {
          if (data?.identity?.name) {
            setRedirecting(true);
            sessionStorage.setItem('forge_preload_slug', slug);
            sessionStorage.setItem('forge_preload_identity', JSON.stringify(data.identity));
            if (data.snapshot) {
              sessionStorage.setItem('forge_preload_snapshot', JSON.stringify(data.snapshot));
            }
            window.location.href = '/';
          }
        })
        .catch(() => {});
    }
  }, [publicProfile, user, slug]);

  // ── Chat state ──────────────────────────────────────────────────────
  const msgId = useRef(0);
  const nextId = () => `pub-${Date.now()}-${++msgId.current}`;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);

  // Initialize welcome message once we have the profile
  useEffect(() => {
    if (publicProfile?.name && messages.length === 0) {
      setMessages([{
        id: nextId(),
        role: 'model',
        text: `Ask me anything about **${publicProfile.name}** — market position, competitors, opportunities, or this week's local intelligence.`,
        createdAt: Date.now(),
      }]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publicProfile?.name]);

  // Build chat context from the public profile data
  const chatContext = publicProfile ? (() => {
    const snapshot = publicProfile.snapshot || {};
    const overview = snapshot.overview || {};
    const dash = overview.dashboard || {};
    return {
      businessName: publicProfile.name,
      address: publicProfile.address,
      overview: {
        businessSnapshot: overview.businessSnapshot,
        marketPosition: overview.marketPosition,
        localEconomy: overview.localEconomy,
        keyOpportunities: overview.keyOpportunities?.slice(0, 3),
        dashboard: {
          topInsights: dash.topInsights?.slice(0, 3),
          communityBuzz: dash.communityBuzz,
          stats: dash.stats,
          aiTools: dash.aiTools?.slice(0, 5),
        },
      },
      ...(snapshot.seo?.data ? { seoReport: { overallScore: snapshot.seo.data.overallScore, summary: snapshot.seo.data.summary } } : {}),
      ...(snapshot.margin?.data ? { marginReport: { overall_score: snapshot.margin.data.overall_score, strategic_advice: snapshot.margin.data.strategic_advice } } : {}),
      ...(snapshot.traffic?.data ? { trafficForecast: { summary: snapshot.traffic.data.summary } } : {}),
      ...(snapshot.competitive?.data ? { competitiveReport: { market_summary: snapshot.competitive.data.market_summary } } : {}),
    };
  })() : {};

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = { id: nextId(), role: 'user', text, createdAt: Date.now() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setIsTyping(true);

    try {
      const res = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: chatSessionId ? [{ role: 'user', text }] : newMessages.map(m => ({ role: m.role, text: m.text })),
          sessionId: chatSessionId,
          businessLocated: true,
          context: chatContext,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.sessionId) setChatSessionId(data.sessionId);
        setMessages(prev => [...prev, { id: nextId(), role: 'model', text: data.text, createdAt: Date.now() }]);
      } else {
        setMessages(prev => [...prev, { id: nextId(), role: 'model', text: 'I had trouble processing that. Try rephrasing your question.', createdAt: Date.now() }]);
      }
    } catch {
      setMessages(prev => [...prev, { id: nextId(), role: 'model', text: 'Connection issue. Please try again.', createdAt: Date.now() }]);
    } finally {
      setIsTyping(false);
    }
  }, [messages, chatSessionId, chatContext, apiFetch]);

  // ── Loading / 404 states ────────────────────────────────────────────

  if (redirecting) {
    return (
      <div className="min-h-screen bg-[#f8f9ff] flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-500 text-sm">Loading {publicProfile?.name || 'profile'}…</p>
        </div>
      </div>
    );
  }

  if (!publicProfile) {
    return (
      <div className="min-h-screen bg-[#f8f9ff] flex items-center justify-center">
        <div className="text-center max-w-sm">
          <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center mx-auto mb-4">
            <Zap className="w-6 h-6 text-purple-500" />
          </div>
          <p className="text-slate-800 font-bold text-lg mb-2">Profile not found</p>
          <p className="text-slate-500 text-sm mb-6">This business profile hasn&apos;t been published yet.</p>
          <a href="/" className="px-5 py-2.5 rounded-xl bg-purple-700 hover:bg-purple-800 text-white text-sm font-bold transition-colors">
            Search for a business
          </a>
        </div>
      </div>
    );
  }

  // === PUBLIC PROFILE PAGE — Amethyst 2-column: content + chat rail ===
  const { name, address, snapshot } = publicProfile;
  const overview = snapshot?.overview || {};
  const bs = overview.businessSnapshot || {};
  const mp = overview.marketPosition || {};
  const le = overview.localEconomy || {};
  const dash = overview.dashboard || {};
  const dashStats = dash.stats || {};
  const insights = dash.topInsights || [];
  const events = dash.events || [];
  const buzz = dash.communityBuzz || '';
  const headline = dash.pulseHeadline || '';
  const opps = overview.keyOpportunities || [];
  const competitors = dash.competitors || [];
  const aiTools = dash.aiTools || [];
  const localIntel = dash.localIntel || {};

  const marginReport = snapshot?.margin?.data;
  const seoReport = snapshot?.seo?.data;
  const trafficReport = snapshot?.traffic?.data;
  const competitiveReport = snapshot?.competitive?.data;
  const hasAnyReport = marginReport || seoReport || trafficReport || competitiveReport;

  return (
    <div className="min-h-screen bg-[#f8f9ff]">
      {/* Nav */}
      <header className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl border-b border-purple-100/40 shadow-sm shadow-purple-900/5 h-14">
        <div className="h-full px-6 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-700 to-violet-600 flex items-center justify-center">
              <Zap className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-lg font-black tracking-tighter text-purple-900">hephae</span>
          </a>
          <div className="flex items-center gap-3">
            <a href="/" className="text-xs text-purple-600 hover:text-purple-800 font-semibold">Analyze your business →</a>
            {!user && (
              <button onClick={signInWithGoogle} className="px-3 py-1.5 rounded-lg bg-purple-700 text-white text-xs font-bold hover:bg-purple-800 transition-colors">
                Sign in
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Right chat rail — same as main app */}
      <aside className="fixed right-0 top-14 h-[calc(100vh-56px)] w-[420px] z-40 border-l border-purple-100/60 flex flex-col">
        <ChatInterface
          messages={messages}
          onSendMessage={sendMessage}
          isTyping={isTyping}
          isDiscovering={false}
          onReset={() => {
            setMessages([{ id: nextId(), role: 'model', text: `Ask me anything about **${name}** — market position, competitors, or opportunities.`, createdAt: Date.now() }]);
            setChatSessionId(null);
          }}
          capabilities={[]}
          isCentered={false}
          followUpChips={[
            { text: 'What are the biggest opportunities?', category: 'insight' },
            { text: 'How does this compare to competitors?', category: 'insight' },
            { text: 'What should the owner focus on?', category: 'action' },
          ]}
          isCollapsed={false}
          onToggleCollapse={() => {}}
          authUser={user}
          onSignIn={signInWithGoogle}
          onSignOut={signOut}
          lightMode
        />
      </aside>

      {/* Main content — scrollable, left of chat */}
      <main className="mr-[420px] pt-20 pb-16 px-8 min-h-screen">

        {/* Business Hero */}
        <div className="bg-gradient-to-br from-purple-900 to-violet-800 rounded-2xl p-8 text-white shadow-xl mb-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-black tracking-tight">{name}</h1>
              <div className="flex items-center gap-3 mt-2 flex-wrap">
                {address && <span className="flex items-center gap-1 text-sm text-purple-200"><MapPin className="w-3.5 h-3.5" /> {address}</span>}
                {bs.rating && (
                  <span className="flex items-center gap-1 text-sm text-amber-300">
                    <Star className="w-3.5 h-3.5 fill-amber-300" /> {bs.rating}/5
                    {bs.reviewCount && <span className="text-purple-300">({bs.reviewCount})</span>}
                  </span>
                )}
              </div>
              {bs.persona && <p className="text-purple-200 text-sm mt-2">{bs.persona}</p>}
            </div>
            {dash.confirmedSources > 0 && (
              <div className="text-right flex-shrink-0">
                <span className="text-3xl font-black">{dash.confirmedSources}</span>
                <p className="text-[10px] text-purple-300 uppercase tracking-widest">Sources</p>
              </div>
            )}
          </div>
        </div>

        {/* Pulse */}
        {headline && (
          <div className="bg-white rounded-2xl p-6 shadow-sm shadow-purple-900/5 border-l-4 border-purple-600 mb-6">
            <p className="text-[10px] font-bold uppercase tracking-widest text-purple-500 mb-1">This Week&apos;s Pulse</p>
            <p className="text-lg font-bold text-slate-900 leading-snug">{headline}</p>
          </div>
        )}

        {/* Buzz + Events */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {buzz && (
            <div className="bg-white rounded-2xl p-6 shadow-sm shadow-purple-900/5">
              <div className="flex items-center gap-2 mb-3"><Newspaper className="w-4 h-4 text-purple-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Community Buzz</p></div>
              <p className="text-sm text-slate-600 leading-relaxed">{buzz}</p>
            </div>
          )}
          {events.length > 0 && (
            <div className="bg-white rounded-2xl p-6 shadow-sm shadow-purple-900/5">
              <div className="flex items-center gap-2 mb-3"><Calendar className="w-4 h-4 text-purple-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Local Events</p></div>
              <div className="space-y-2.5">
                {events.slice(0, 5).map((ev: any, i: number) => (
                  <div key={i} className="flex items-start gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-violet-400 mt-1.5 flex-shrink-0" />
                    <div><p className="text-sm font-semibold text-slate-700">{ev.what}</p>{ev.when && <p className="text-xs text-slate-400">{ev.when}</p>}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Insights */}
        {insights.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3"><Activity className="w-4 h-4 text-purple-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Weekly Intelligence</p></div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {insights.map((ins: any, i: number) => (
                <div key={i} className="bg-white rounded-2xl p-5 shadow-sm shadow-purple-900/5 border-l-4 border-violet-400">
                  <h3 className="text-sm font-bold text-slate-800">{humanize(ins.title)}</h3>
                  <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{ins.recommendation}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {mp.competitorCount != null && (
            <div className="bg-white rounded-xl p-4 shadow-sm shadow-purple-900/5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Competitors</p>
              <p className="text-xl font-black text-purple-700 mt-0.5">{mp.competitorCount}</p>
            </div>
          )}
          {(le.medianIncome || dashStats.medianIncome) && (
            <div className="bg-white rounded-xl p-4 shadow-sm shadow-purple-900/5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Median Income</p>
              <p className="text-xl font-black text-emerald-600 mt-0.5">{le.medianIncome || dashStats.medianIncome}</p>
            </div>
          )}
          {localIntel.spendingPower && (
            <div className="bg-white rounded-xl p-4 shadow-sm shadow-purple-900/5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Spending Power</p>
              <p className="text-xl font-black text-violet-600 mt-0.5 capitalize">{localIntel.spendingPower}</p>
            </div>
          )}
          {(le.population || dashStats.population) && (
            <div className="bg-white rounded-xl p-4 shadow-sm shadow-purple-900/5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Population</p>
              <p className="text-xl font-black text-sky-600 mt-0.5">{le.population || dashStats.population}</p>
            </div>
          )}
        </div>

        {/* AI Tools */}
        {aiTools.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3"><Sparkles className="w-4 h-4 text-violet-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">AI Tools Competitors Are Adopting</p></div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {aiTools.slice(0, 4).map((t: any, i: number) => (
                <div key={i} className="bg-white rounded-xl p-4 shadow-sm shadow-purple-900/5 flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center flex-shrink-0"><Zap className="w-4 h-4 text-purple-500" /></div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-800">{(t.tool || '').replace(/\*\*/g, '')}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{t.capability}</p>
                    {t.url && <a href={t.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-purple-600 hover:text-purple-800 font-semibold flex items-center gap-1 mt-1">Visit <ExternalLink className="w-2.5 h-2.5" /></a>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reports */}
        {hasAnyReport && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3"><BarChart3 className="w-4 h-4 text-purple-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Analysis Reports</p></div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {marginReport && (
                <div className="bg-white rounded-2xl p-5 shadow-sm shadow-purple-900/5 border-l-4 border-purple-700">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Margin Analysis</p>
                  <p className="text-sm font-bold text-slate-800 mt-1">Score: {marginReport.overall_score}/100</p>
                  {marginReport.strategic_advice && <p className="text-xs text-slate-500 mt-2">{Array.isArray(marginReport.strategic_advice) ? marginReport.strategic_advice[0] : marginReport.strategic_advice}</p>}
                </div>
              )}
              {seoReport && (
                <div className="bg-white rounded-2xl p-5 shadow-sm shadow-purple-900/5 border-l-4 border-emerald-500">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">SEO Health</p>
                  <p className="text-sm font-bold text-slate-800 mt-1">Score: {seoReport.overallScore}/100</p>
                  {seoReport.summary && <p className="text-xs text-slate-500 mt-2">{seoReport.summary.slice(0, 150)}…</p>}
                </div>
              )}
              {trafficReport && (
                <div className="bg-white rounded-2xl p-5 shadow-sm shadow-purple-900/5 border-l-4 border-sky-500">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Foot Traffic</p>
                  <p className="text-sm font-bold text-slate-800 mt-1">{trafficReport.forecast?.length || 0}-Day Forecast</p>
                  {trafficReport.summary && <p className="text-xs text-slate-500 mt-2">{trafficReport.summary.slice(0, 150)}…</p>}
                </div>
              )}
              {competitiveReport && (
                <div className="bg-white rounded-2xl p-5 shadow-sm shadow-purple-900/5 border-l-4 border-orange-500">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Competitive Intel</p>
                  <p className="text-sm font-bold text-slate-800 mt-1">{competitiveReport.competitors?.length || 0} Analyzed</p>
                  {competitiveReport.market_summary && <p className="text-xs text-slate-500 mt-2">{competitiveReport.market_summary.slice(0, 150)}…</p>}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Competitors */}
        {competitors.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-3"><Building2 className="w-4 h-4 text-purple-400" /><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Nearby ({competitors.length})</p></div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {competitors.slice(0, 9).map((c: any, i: number) => (
                <div key={i} className="bg-white rounded-xl p-3 shadow-sm shadow-purple-900/5 flex items-center gap-2.5">
                  <MapPin className="w-3 h-3 text-slate-400 flex-shrink-0" />
                  <div className="min-w-0"><p className="text-xs font-semibold text-slate-700 truncate">{c.name}</p><p className="text-[10px] text-slate-400">{c.cuisine || c.category} · {c.distanceM < 1000 ? `${c.distanceM}m` : `${(c.distanceM / 1000).toFixed(1)}km`}</p></div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CTA */}
        <div className="bg-gradient-to-br from-purple-700 to-violet-600 rounded-2xl p-8 text-center shadow-xl mb-6">
          <h3 className="text-xl font-black text-white mb-2">Get This For Your Business</h3>
          <p className="text-sm text-purple-200 mb-5 max-w-md mx-auto">Free analysis in minutes — market position, pricing, SEO, traffic, and competitive intel.</p>
          <a href="/" className="inline-flex items-center gap-2 px-6 py-3 bg-white text-purple-700 font-bold text-sm rounded-xl hover:bg-purple-50 transition-colors shadow-md">
            <Sparkles className="w-4 h-4" /> Analyze Your Business
          </a>
        </div>

        <footer className="pt-4 border-t border-purple-100/60 text-center">
          <p className="text-[10px] text-slate-400">
            Data from BLS, Census, USDA, OSM, NWS, IRS, FDA, CDC, and Google. Analysis by <a href="/" className="text-purple-500">Hephae AI</a>.
            {publicProfile.publishedAt && ` · ${new Date(publicProfile.publishedAt).toLocaleDateString()}`}
          </p>
        </footer>
      </main>
    </div>
  );
}
