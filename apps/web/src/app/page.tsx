'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search as SearchIcon, MapPin, Building2, Store, Loader2, ArrowRight, Activity, Percent, DollarSign, TrendingUp, AlertTriangle, Scale, Target, Swords, X, Download, BarChart3, Users, Search, Share2, Zap, Shield, Eye, MessageCircle, Map, Sparkles, Calendar, LogIn, LogOut, Lock, Globe, Flame } from 'lucide-react';
import { SurgicalReport } from '@/types/api';
import { SuggestionChip } from '@/components/Chatbot/types';
import { computeSuggestionChips, ACTION_CHIP_MAP } from '@/lib/suggestionChips';
import clsx from 'clsx';

/** Convert snake_case/kebab-case to Title Case */
const humanize = (s: string) => s.replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
import dynamic from 'next/dynamic';

const RechartsBarChart = dynamic(() => import('recharts').then(m => {
  const { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } = m;
  const ChartComponent = ({ data, barKey, nameKey, colors, layout, height }: any) => (
    <ResponsiveContainer width="100%" height={height || 200}>
      <BarChart data={data} layout={layout || 'vertical'} margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
        {layout === 'vertical' ? (
          <>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey={nameKey} width={100} tick={{ fontSize: 11, fill: '#64748b' }} />
          </>
        ) : (
          <>
            <XAxis dataKey={nameKey} tick={{ fontSize: 11, fill: '#64748b' }} />
            <YAxis hide />
          </>
        )}
        <Tooltip formatter={(v: any) => typeof v === 'number' ? `$${v.toFixed(2)}` : v} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }} />
        <Bar dataKey={barKey} radius={[0, 6, 6, 0]} barSize={18}>
          {data.map((_: any, i: number) => (
            <Cell key={i} fill={colors?.[i % colors.length] || '#6366f1'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
  ChartComponent.displayName = 'ChartComponent';
  return ChartComponent;
}), { ssr: false });

const RadialScoreChart = dynamic(() => import('@/components/Chatbot/seo/RadialScore'), { ssr: false });
import ChatInterface from '@/components/Chatbot/ChatInterface';
import HephaeLogo from '@/components/HephaeLogo';
import { DailyForecast, TimeSlot } from '@/components/Chatbot/types';
import DetailPanel from '@/components/Chatbot/DetailPanel';
import MapVisualizer from '@/components/Chatbot/MapVisualizer';
import HeatmapGrid from '@/components/Chatbot/HeatmapGrid';
import { ChatMessage, ForecastResponse } from '@/components/Chatbot/types';
import { BaseIdentity } from '@/types/api';
import { NeuralBackground } from '@/components/Chatbot/NeuralBackground';
import BlobBackground from '@/components/BlobBackground';
import { AuthWall } from '@/components/Chatbot/AuthWall';
import { HeartbeatSetup } from '@/components/Chatbot/HeartbeatSetup';
import { HeartbeatBadge } from '@/components/Chatbot/HeartbeatBadge';
import ResultsDashboard from '@/components/Chatbot/seo/ResultsDashboard';
import { useAuth } from '@/contexts/AuthContext';
import { useApiClient } from '@/hooks/useApiClient';
// DiscoveryProgress import kept for ChatInterface/MapVisualizer; useRotatingMessage now used inside LoadingOverlay
import { SeoReport } from '@/types/api';
import LoadingOverlay from '@/components/Chatbot/LoadingExperience';
import SocialSharePanel from '@/components/Chatbot/SocialSharePanel';
import {
  TopNav, LeftSidebar, WeeklyPulseCard, MarketPositionCard, MarginCard,
  AiToolsCard, WeekCalendarCard, BuzzCard, SeoCard, MapCard, FootTrafficCard,
  CompetitorsStrip, IntelligenceBanner, LockedAnalysisCard, Card, Label,
  RunningAnalysisCard, ProfileDiscoveryCard, LocalIntelPage,
  toDashboardData, toMarginCardData, toSeoCardData, toTrafficCardData, toBusiness,
} from '@/components/Dashboard';
import type { ActiveSection } from '@/components/Dashboard';

export default function Home() {
  const { user, signInWithGoogle, signOut } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { apiFetch } = useApiClient();

  // Admin check — NEXT_PUBLIC_ADMIN_EMAILS must be set in .env.local
  const ADMIN_EMAILS = (process.env.NEXT_PUBLIC_ADMIN_EMAILS || '').split(',').map(e => e.trim().toLowerCase()).filter(Boolean);
  const isAdmin = !!user?.email && ADMIN_EMAILS.includes(user.email.toLowerCase());
  const router = useRouter();
  const [showAuthWall, setShowAuthWall] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: '1', role: 'model', text: 'Hi! I am Hephae.\nSearch for your business to get started.', createdAt: Date.now() }
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);

  // App States
  const [locatedBusiness, setLocatedBusiness] = useState<BaseIdentity | null>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [capabilities, setCapabilities] = useState<{ id: string, label: string, icon?: React.ReactNode }[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [businessOverview, setBusinessOverview] = useState<any>(null);

  const [report, setReport] = useState<SurgicalReport | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [seoReport, setSeoReport] = useState<SeoReport | null>(null);
  const [competitiveReport, setCompetitiveReport] = useState<any | null>(null);
  const [socialAuditReport, setSocialAuditReport] = useState<any | null>(null);

  // Report share URLs
  const [profileReportUrl, setProfileReportUrl] = useState<string | null>(null);
  const [marginReportUrl, setMarginReportUrl] = useState<string | null>(null);
  const [trafficReportUrl, setTrafficReportUrl] = useState<string | null>(null);
  const [seoReportUrl, setSeoReportUrl] = useState<string | null>(null);
  const [competitiveReportUrl, setCompetitiveReportUrl] = useState<string | null>(null);
  const [marketingReportUrl, setMarketingReportUrl] = useState<string | null>(null);
  const [copyToast, setCopyToast] = useState(false);
  const [showSharePanel, setShowSharePanel] = useState(false);
  const [showHeartbeatSetup, setShowHeartbeatSetup] = useState(false);
  const [activeHeartbeatId, setActiveHeartbeatId] = useState<string | null>(null);
  const [isChatCollapsed, setIsChatCollapsed] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<'chat' | 'visualizer'>('chat');

  // Detail Panel State for Traffic Forecast Phase 14
  const [selectedDay, setSelectedDay] = useState<DailyForecast | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);

  // Active capability tracking for loading experience
  const [activeCapability, setActiveCapability] = useState<string | null>(null);
  const [capabilityStartTime, setCapabilityStartTime] = useState<number | null>(null);

  // Menu URL prompt: when margin analysis can't find a menu, we ask the user
  const [awaitingMenuUrl, setAwaitingMenuUrl] = useState(false);

  // Ultralocal coverage CTA card state
  const [addMyAreaCity, setAddMyAreaCity] = useState<string | null>(null);

  // Unique business URL slug
  const [businessSlug, setBusinessSlug] = useState<string | null>(null);

  // Profile building mode: guided Q&A after sign-in
  const [isProfileBuilding, setIsProfileBuilding] = useState(false);
  const [profileSessionId, setProfileSessionId] = useState<string | null>(null);

  // Unique message ID generator
  const msgIdCounter = useRef(0);
  const nextMsgId = () => `msg-${Date.now()}-${++msgIdCounter.current}`;
  const msg = (role: 'user' | 'model', text: string, id?: string): ChatMessage => ({ id: id || nextMsgId(), role, text, createdAt: Date.now() });

  // Email Lead Capture States
  const [searchDocId, setSearchDocId] = useState<string | null>(null);
  const [showEmailWall, setShowEmailWall] = useState(false);
  const [hasProvidedEmail, setHasProvidedEmail] = useState(false);
  const [pendingCapability, setPendingCapability] = useState<string | null>(null);
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('hephae_has_provided_email');
      if (stored === 'true') {
        setHasProvidedEmail(true);
        const storedEmail = localStorage.getItem('hephae_user_email');
        if (storedEmail) setUserEmail(storedEmail);
      }
    }
  }, []);

  // Auto-expand chat when AI is responding or discovering
  useEffect(() => {
    if (isTyping || isDiscovering) setIsChatCollapsed(false);
  }, [isTyping, isDiscovering]);

  // Auto-switch to visualizer panel on mobile when a report loads
  useEffect(() => {
    if (report || forecast || seoReport || competitiveReport || socialAuditReport) {
      setMobilePanel('visualizer');
    }
  }, [report, forecast, seoReport, competitiveReport, socialAuditReport]);

  // Rotating messages for the discovery overlay
  // Discovery messages now handled inside LoadingOverlay

  // On mount: check for business profile preload (from /b/[slug] redirect)
  useEffect(() => {
    const preloadSlug = sessionStorage.getItem('forge_preload_slug');
    const preloadIdentityStr = sessionStorage.getItem('forge_preload_identity');
    const preloadSnapshotStr = sessionStorage.getItem('forge_preload_snapshot');
    if (preloadSlug && preloadIdentityStr) {
      sessionStorage.removeItem('forge_preload_slug');
      sessionStorage.removeItem('forge_preload_identity');
      sessionStorage.removeItem('forge_preload_snapshot');
      try {
        const identity = JSON.parse(preloadIdentityStr);
        setBusinessSlug(preloadSlug);

        // If a full snapshot is available, restore all state instantly
        if (preloadSnapshotStr) {
          const snap = JSON.parse(preloadSnapshotStr);
          setLocatedBusiness(identity);
          if (snap.overview) setBusinessOverview(snap.overview);
          if (snap.margin?.data) { setReport(snap.margin.data); setMarginReportUrl(snap.margin.reportUrl || null); }
          if (snap.traffic?.data) { setForecast(snap.traffic.data); setTrafficReportUrl(snap.traffic.reportUrl || null); if (snap.traffic.data.forecast?.length) { setSelectedDay(snap.traffic.data.forecast[0]); setSelectedSlot(snap.traffic.data.forecast[0].slots?.[0] || null); } }
          if (snap.seo?.data) { setSeoReport(snap.seo.data); setSeoReportUrl(snap.seo.reportUrl || null); }
          if (snap.marketing?.data) { setSocialAuditReport(snap.marketing.data); setMarketingReportUrl(snap.marketing.reportUrl || null); }
          if (snap.competitive?.data) { setCompetitiveReport(snap.competitive.data); setCompetitiveReportUrl(snap.competitive.reportUrl || null); }
          if (snap.profileReportUrl) setProfileReportUrl(snap.profileReportUrl);
          const msg_ = (role: 'user' | 'model', text: string) => ({ id: Math.random().toString(36), role, text, timestamp: Date.now() });
          setMessages([msg_('model', `Loaded saved analysis for **${identity.name}**. All previously discovered insights are restored below.`)]);
        } else {
          // No snapshot — trigger fresh overview
          handlePlaceSelect(identity);
        }
      } catch {
        // ignore malformed data
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEmailSubmit = async (email: string) => {
    let docId = searchDocId;

    // If no tracking doc exists yet, create one on the fly
    if (!docId) {
      try {
        const trackRes = await apiFetch('/api/track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: locatedBusiness?.name || 'unknown' })
        });
        if (trackRes.ok) {
          const trackData = await trackRes.json();
          docId = trackData.id;
          setSearchDocId(docId);
        }
      } catch (e) { /* proceed without tracking */ }
    }

    // Save email to tracking doc if available
    if (docId) {
      const res = await apiFetch('/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: docId, email })
      });
      if (!res.ok) throw new Error("Failed to save email");
    }

    // Unlock regardless of tracking success
    setUserEmail(email);
    setShowEmailWall(false);
    setHasProvidedEmail(true);
    localStorage.setItem('hephae_has_provided_email', 'true');
    localStorage.setItem('hephae_user_email', email);

    // Resume the capability execution if one was pending
    if (pendingCapability) {
      const capToRun = pendingCapability;
      setPendingCapability(null);
      executeCapability(capToRun);
    }
  };

  // ACTION_CHIP_MAP imported from @/lib/suggestionChips

  // Re-run margin surgery with a user-provided menu URL
  const executeCapabilityWithMenuUrl = async (menuUrl: string) => {
    if (!locatedBusiness) return;
    setIsTyping(true);
    setActiveCapability('surgery');
    setCapabilityStartTime(Date.now());
    setMessages(prev => [...prev, msg('model', "Got it! Analyzing your menu now... ⏱️")]);

    try {
      const { menuScreenshotBase64: _stripped, ...identityForApi } = locatedBusiness as any;
      const res = await apiFetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: locatedBusiness.officialUrl,
          enrichedProfile: identityForApi,
          menuUrl,
          advancedMode: false,
        }),
      });

      if (!res.ok) {
        throw new Error('menu_not_found');
      }

      const data = await res.json();
      if (data.menuNotFound) {
        setMessages(prev => [...prev, msg('model', "I couldn't extract menu items from that URL. Make sure it's a direct link to a page listing your items with prices.")]);
        setAwaitingMenuUrl(true);
        return;
      }

      setReport(data);
      if (data.reportUrl) {
        setMarginReportUrl(data.reportUrl);
        const totalLeakage = data.menu_items?.reduce((s: number, i: { price_leakage: number }) => s + i.price_leakage, 0) || 0;
        sendReportEmailAsync('margin', data.reportUrl, locatedBusiness.name, `$${totalLeakage.toFixed(2)} total profit leakage detected across ${data.menu_items?.length || 0} menu items. Overall score: ${data.overall_score}/100.`);
      }
      setMessages(prev => [...prev, msg('model', "Price analysis complete! Your optimization dashboard is ready.\n\n[Schedule a call](https://hephae.co/schedule) to discuss your pricing strategy with our team.")]);
    } catch (e: any) {
      setMessages(prev => [...prev, msg('model', `Price analysis couldn't complete: ${e.message}`)]);
    } finally {
      setIsTyping(false);
      setActiveCapability(null);
      setCapabilityStartTime(null);
    }
  };

  const sendMessage = async (text: string) => {
    // Intercept: if in profile building mode, handle locally (step-by-step)
    if (isProfileBuilding && profileStep) {
      setMessages(prev => [...prev, msg('user', text)]);
      handleProfileInput(text);
      return;
    }

    // Intercept: ultralocal coverage interest — "yes, add my area" (text path kept for fallback)
    if (/yes.*add.*area|add.*area|yes.*ultralocal|request.*coverage|cover.*my.*area/i.test(text.trim()) && locatedBusiness) {
      setMessages(prev => [...prev, msg('user', text)]);
      await submitUltralocalInterest();
      return;
    }

    // Intercept: user provided a URL for a pending capability (SEO needs website, etc.)
    if (pendingCapForUrl && locatedBusiness && (/^https?:\/\//i.test(text.trim()) || /\w+\.\w+/.test(text.trim()))) {
      const url = /^https?:\/\//i.test(text.trim()) ? text.trim() : `https://${text.trim()}`;
      const capToRun = pendingCapForUrl;
      setPendingCapForUrl(null);
      setMessages(prev => [...prev, msg('user', text)]);
      // Save URL to the business profile
      setLocatedBusiness(prev => prev ? { ...prev, officialUrl: url } as any : prev);
      setMessages(prev => [...prev, msg('model', `Got it — saved **${url}** as your website. Starting the analysis...`)]);
      // Small delay for state to update, then run
      setTimeout(() => executeCapability(capToRun), 200);
      return;
    }

    // Intercept: if we're waiting for a menu URL from the user, retry margin analysis
    if (awaitingMenuUrl && locatedBusiness && /^https?:\/\//i.test(text.trim())) {
      setAwaitingMenuUrl(false);
      setMessages(prev => [...prev, msg('user', text)]);
      executeCapabilityWithMenuUrl(text.trim());
      return;
    }

    // Route action chips directly to executeCapability
    const mappedCapability = ACTION_CHIP_MAP[text];
    if (mappedCapability && locatedBusiness) {
      setMessages(prev => [...prev, msg('user', text)]);
      handleSelectCapability(mappedCapability);
      return;
    }

    // 1. Append user message
    const newMessages: ChatMessage[] = [...messages, msg('user', text)];
    setMessages(newMessages);
    setIsTyping(true);

    // Lead Capture Interception: Always silently track the first query
    if (!hasProvidedEmail && !searchDocId) {
      try {
        const trackRes = await apiFetch('/api/track', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: text })
        });
        if (trackRes.ok) {
          const trackData = await trackRes.json();
          setSearchDocId(trackData.id);
        }
      } catch (e) { console.error("Tracking failed", e); }
    } else if (hasProvidedEmail) {
      // Just log subsequent queries silently in the background
      apiFetch('/api/track', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      }).catch(() => { }); // fire and forget
    }

    try {
      const res = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: chatSessionId ? [newMessages[newMessages.length - 1]] : newMessages,
          sessionId: chatSessionId,
          businessLocated: !!locatedBusiness,
          context: {
            businessName: locatedBusiness?.name,
            address: locatedBusiness?.address,
            overview: businessOverview ? {
              businessSnapshot: businessOverview.businessSnapshot,
              marketPosition: businessOverview.marketPosition,
              localEconomy: businessOverview.localEconomy,
              keyOpportunities: businessOverview.keyOpportunities?.slice(0, 3),
              dashboard: businessOverview.dashboard ? {
                topInsights: businessOverview.dashboard.topInsights?.slice(0, 3),
                communityBuzz: businessOverview.dashboard.communityBuzz,
                coverage: businessOverview.dashboard.coverage,
                stats: businessOverview.dashboard.stats,
                techHighlight: businessOverview.dashboard.techHighlight,
                aiTools: businessOverview.dashboard.aiTools?.slice(0, 5),
                techPlatforms: businessOverview.dashboard.techPlatforms,
              } : undefined,
            } : undefined,
            seoReport: seoReport ? { overallScore: seoReport.overallScore, sections: seoReport.sections?.map((s: any) => ({ title: s.title || s.id, score: s.score, findings: s.recommendations?.slice(0, 3)?.map((r: any) => `[${r.severity}] ${r.title}: ${r.description}`) })), summary: seoReport.summary } : undefined,
            marginReport: report ? { overall_score: report.overall_score, menu_items: report.menu_items?.slice(0, 10), strategic_advice: report.strategic_advice } : undefined,
            trafficForecast: forecast ? { summary: forecast.summary, forecast: forecast.forecast?.slice(0, 5) } : undefined,
            competitiveReport: competitiveReport ? { market_summary: competitiveReport.market_summary, competitors: competitiveReport.competitors, recommendations: competitiveReport.recommendations } : undefined,
          }
        })
      });

      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();

      // Track session ID for this page session (not persisted across reloads)
      if (data.sessionId && data.sessionId !== chatSessionId) {
        setChatSessionId(data.sessionId);
      }

      setMessages(prev => [...prev, msg('model', data.text)]);

      // Trigger Orchestrator State Change
      if (data.triggerCapabilityHandoff && data.locatedBusiness) {
        setLocatedBusiness(data.locatedBusiness);
        setReport(null);
        setForecast(null);
        setSeoReport(null);
        setCompetitiveReport(null);
        setCapabilities([]);
        setProfileReportUrl(null);
        setMarginReportUrl(null);
        setTrafficReportUrl(null);
        setSeoReportUrl(null);
        setCompetitiveReportUrl(null);
        setMarketingReportUrl(null);
        setChatSessionId(null); // New business = new chat session

        // Spawn Background Overview (replaces heavy discovery)
        triggerBusinessOverview(data.locatedBusiness);
      }

    } catch (e: any) {
      console.error(e);
      setMessages(prev => [...prev, msg('model', "I encountered an error connecting to my core logic layer.")]);
    } finally {
      setIsTyping(false);
    }
  };

  // --- Profile Building Mode ---

  // Profile building: auto-discover → ask user for gaps → done
  const [profileStep, setProfileStep] = useState<'menu' | 'social' | 'done' | null>(null);

  const startProfileBuilding = async () => {
    const enriched = locatedBusiness as any;
    setIsProfileBuilding(true);

    setMessages(prev => [...prev, msg('model',
      `Building profile for **${locatedBusiness?.name}**... Searching the web for your business details.`
    )]);

    // Track what we discover to show a summary
    const discovered: string[] = [];
    const discoveredData: Record<string, any> = {};

    // --- Already known ---
    if (enriched?.officialUrl) discovered.push(`Website: [${enriched.officialUrl}](${enriched.officialUrl})`);

    // --- Auto-discover menu ---
    let foundMenu = !!enriched?.menuUrl;
    if (foundMenu) {
      discovered.push(`Menu: [${enriched.menuUrl}](${enriched.menuUrl})`);
    } else {
      try {
        const res = await apiFetch('/api/profile/discover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ section: 'menu', identity: locatedBusiness }),
        });
        if (res.ok) {
          const data = await res.json();
          // Collect all discovered URLs (could be multiple delivery platforms)
          const urls: Record<string, string> = {};
          for (const [key, val] of Object.entries(data.data || {})) {
            if (typeof val === 'string' && val.startsWith('http')) urls[key] = val;
          }
          const firstUrl = Object.values(urls)[0];
          if (firstUrl) {
            foundMenu = true;
            setLocatedBusiness(prev => prev ? { ...prev, menuUrl: firstUrl, deliveryLinks: urls } as any : prev);
            discoveredData.menu = urls;
            for (const [platform, url] of Object.entries(urls)) {
              const label = platform === 'menuUrl' ? 'Menu' : platform.charAt(0).toUpperCase() + platform.slice(1);
              discovered.push(`${label}: [${url}](${url})`);
            }
          }
        }
      } catch { /* will ask user */ }
    }

    // --- Auto-discover social ---
    let foundSocial = !!(enriched?.socialLinks && Object.values(enriched.socialLinks || {}).some((v: any) => v));
    if (foundSocial) {
      for (const [platform, url] of Object.entries(enriched.socialLinks || {})) {
        if (url) discovered.push(`${platform.charAt(0).toUpperCase() + platform.slice(1)}: [${url}](${url as string})`);
      }
    } else {
      try {
        const res = await apiFetch('/api/profile/discover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ section: 'social', identity: locatedBusiness }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.data && Object.keys(data.data).length > 0) {
            foundSocial = true;
            setLocatedBusiness(prev => prev ? { ...prev, socialLinks: data.data } as any : prev);
            discoveredData.social = data.data;
            for (const [platform, url] of Object.entries(data.data)) {
              if (typeof url === 'string' && url) {
                discovered.push(`${platform.charAt(0).toUpperCase() + platform.slice(1)}: [${url}](${url})`);
              }
            }
          }
        }
      } catch { /* will ask user */ }
    }

    // --- Show discovery summary ---
    if (discovered.length > 0) {
      setMessages(prev => [...prev, msg('model',
        `**Here's what I found:**\n${discovered.map(d => `• ${d}`).join('\n')}`
      )]);
    }

    // --- Now ask for gaps, one at a time ---
    if (!foundMenu) {
      setProfileStep('menu');
      setMessages(prev => [...prev, msg('model',
        `I couldn't find a menu page. Select a platform below or paste your menu link directly.`
      )]);
      return;
    }

    if (!foundSocial) {
      setProfileStep('social');
      setMessages(prev => [...prev, msg('model',
        `I couldn't find social profiles. Select a platform below or paste a link.`
      )]);
      return;
    }

    // Everything found — offer to add more
    setProfileStep('social'); // reuse social step for "add more"
    setMessages(prev => [...prev, msg('model',
      `Want to add any additional links? (More delivery apps, social profiles, etc.) Select below or type "done" to finish.`
    )]);
  };

  const handleProfileInput = (text: string) => {
    const trimmed = text.trim();
    const isDone = /^(done|finish profile|that's it|no more)$/i.test(trimmed);
    const isSkip = /^skip$/i.test(trimmed);
    const isUrl = /^https?:\/\//i.test(trimmed);
    const isHandle = /^@\w/i.test(trimmed);

    // "Finish profile" chip or "done" from any step
    if (isDone) { finishProfileBuilding(); return; }

    if (profileStep === 'menu') {
      if (trimmed === 'menu_link') {
        setMessages(prev => [...prev, msg('model', `Paste your menu page URL.`)]);
        return;
      }
      const appMatch = trimmed.match(/^(delivery|booking):(\w+)$/);
      if (appMatch) {
        const platform = appMatch[2].charAt(0).toUpperCase() + appMatch[2].slice(1);
        setMessages(prev => [...prev, msg('model', `What's your ${platform} page link or store name?`)]);
        setLocatedBusiness(prev => prev ? { ...prev, _pendingApp: appMatch[2] } as any : prev);
        return;
      }
      if (isSkip) { advanceToSocial(); return; }
      if (isUrl || /\w+\.\w+/.test(trimmed)) {
        const url = isUrl ? trimmed : `https://${trimmed}`;
        const pending = (locatedBusiness as any)?._pendingApp;
        if (pending) {
          setLocatedBusiness(prev => {
            const dl = (prev as any)?.deliveryLinks || {};
            return prev ? { ...prev, deliveryLinks: { ...dl, [pending]: url }, _pendingApp: undefined } as any : prev;
          });
          setMessages(prev => [...prev, msg('model', `Saved ${pending}! Add more, paste your menu link, or "Skip".`)]);
        } else {
          setLocatedBusiness(prev => prev ? { ...prev, menuUrl: url } as any : prev);
          setMessages(prev => [...prev, msg('model', `Saved menu. **Margin Analysis** unlocked! Add ${appLabel.toLowerCase()} or "Skip".`)]);
        }
        return;
      }
      const pending = (locatedBusiness as any)?._pendingApp;
      if (pending && trimmed.length > 1) {
        setLocatedBusiness(prev => {
          const dl = (prev as any)?.deliveryLinks || {};
          return prev ? { ...prev, deliveryLinks: { ...dl, [pending]: trimmed }, _pendingApp: undefined } as any : prev;
        });
        setMessages(prev => [...prev, msg('model', `Saved ${pending}. Add more or "Skip".`)]);
        return;
      }
      setMessages(prev => [...prev, msg('model', `Paste a URL or select a platform above.`)]);

    } else if (profileStep === 'social') {
      const socialMatch = trimmed.match(/^social:(\w+)$/);
      if (socialMatch) {
        const p = socialMatch[1];
        const label = p === 'google' ? 'Google Business' : p.charAt(0).toUpperCase() + p.slice(1);
        setMessages(prev => [...prev, msg('model', `What's your ${label} URL or handle?`)]);
        setLocatedBusiness(prev => prev ? { ...prev, _pendingSocial: p } as any : prev);
        return;
      }
      if (isSkip) { finishProfileBuilding(); return; }
      if (isUrl || isHandle) {
        const pending = (locatedBusiness as any)?._pendingSocial;
        const platform = pending
          || (/instagram/i.test(trimmed) ? 'instagram' : /facebook/i.test(trimmed) ? 'facebook'
            : /yelp/i.test(trimmed) ? 'yelp' : /google/i.test(trimmed) ? 'googleBusiness'
            : /tiktok/i.test(trimmed) ? 'tiktok' : 'other');
        setLocatedBusiness(prev => {
          const sl = (prev as any)?.socialLinks || {};
          return prev ? { ...prev, socialLinks: { ...sl, [platform]: trimmed }, _pendingSocial: undefined } as any : prev;
        });
        setMessages(prev => [...prev, msg('model', `Saved ${platform}! Add another or "Done".`)]);
        return;
      }
      const pending = (locatedBusiness as any)?._pendingSocial;
      if (pending && trimmed.length > 1) {
        setLocatedBusiness(prev => {
          const sl = (prev as any)?.socialLinks || {};
          return prev ? { ...prev, socialLinks: { ...sl, [pending]: trimmed }, _pendingSocial: undefined } as any : prev;
        });
        setMessages(prev => [...prev, msg('model', `Saved ${pending}. Add another or "Done".`)]);
        return;
      }
      setMessages(prev => [...prev, msg('model', `Select a platform above or paste a link.`)]);
    }
  };

  const advanceToSocial = () => {
    setProfileStep('social');
    setLocatedBusiness(prev => {
      const enriched = prev as any;
      const hasSocial = enriched?.socialLinks && Object.values(enriched.socialLinks || {}).some((v: any) => v);
      setTimeout(() => {
        setMessages(p => [...p, msg('model',
          hasSocial ? `Any more social profiles? Select below or "Done".` : `Any social media? Select a platform or "Skip".`
        )]);
      }, 300);
      return prev;
    });
  };

  const finishProfileBuilding = () => {
    setIsProfileBuilding(false);
    setProfileStep(null);
    setProfileHasBeenBuilt(true);

    // Build a full summary of everything in the profile
    setLocatedBusiness(prev => {
      const enriched = prev as any;
      const profileLines: string[] = [];

      if (enriched?.officialUrl) profileLines.push(`**Website:** ${enriched.officialUrl}`);
      if (enriched?.menuUrl) profileLines.push(`**Menu:** ${enriched.menuUrl}`);
      if (enriched?.deliveryLinks) {
        for (const [platform, url] of Object.entries(enriched.deliveryLinks)) {
          if (typeof url === 'string' && url && platform !== 'menuUrl') {
            profileLines.push(`**${platform.charAt(0).toUpperCase() + platform.slice(1)}:** ${url}`);
          }
        }
      }
      if (enriched?.socialLinks) {
        for (const [platform, url] of Object.entries(enriched.socialLinks)) {
          if (url) profileLines.push(`**${platform.charAt(0).toUpperCase() + platform.slice(1)}:** ${url}`);
        }
      }

      const unlocked: string[] = [];
      if (enriched?.menuUrl) unlocked.push('Margin Analysis');
      if (enriched?.officialUrl) unlocked.push('SEO Audit');
      unlocked.push('Foot Traffic', 'Competitive Intel');

      const summary = profileLines.length > 0
        ? `**Your profile:**\n${profileLines.map(l => `• ${l}`).join('\n')}\n\n`
        : '';

      setMessages(p => [...p, msg('model',
        `${summary}Profile complete! Analyses unlocked: **${unlocked.join(', ')}**.\n\nRun any analysis from the dashboard. You can always add more links later by clicking "Build my profile" again.`
      )]);

      // Persist profile data to Firestore
      if (businessSlug && prev) {
        saveCapabilitySnapshot(businessSlug, prev, {});
      }

      return prev;
    });
  };

  const sendProfileMessage = async (text: string) => {
    if (!locatedBusiness) return;
    setIsTyping(true);

    try {
      const profileMessages = [{ role: 'user', text }];
      const res = await apiFetch('/api/profile/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: profileMessages,
          businessIdentity: locatedBusiness,
          sessionId: profileSessionId,
        }),
      });

      if (!res.ok) {
        const status = res.status;
        let errBody = '';
        try { errBody = await res.text(); } catch { /* ignore */ }
        console.error(`Profile builder returned ${status}: ${errBody}`);
        // Fall through to chat-based fallback below
        throw new Error(`Profile builder returned ${status}`);
      }

      const data = await res.json();

      if (data.sessionId && data.sessionId !== profileSessionId) {
        setProfileSessionId(data.sessionId);
      }

      setMessages(prev => [...prev, msg('model', data.text)]);

      // Profile building complete — save and run capabilities
      if (data.profileComplete) {
        setIsProfileBuilding(false);
        const selectedCaps = data.selectedCapabilities || [];

        if (data.profile) {
          setLocatedBusiness(prev => prev ? { ...prev, ...data.profile } : prev);
        }

        for (const capId of selectedCaps) {
          const normalizedId = capId === 'margin' ? 'surgery' : capId === 'social' ? 'marketing' : capId;
          executeCapability(normalizedId);
        }
      }
    } catch (e: any) {
      console.error("Profile building failed, switching to chat-based collection:", e.message);
      // Switch to collecting profile data through the regular chat interface
      setIsProfileBuilding(false);
      const enriched = locatedBusiness as any;
      const gaps: string[] = [];
      if (!enriched?.menuUrl) gaps.push("**Menu URL** — a link to your online menu with prices (your website, DoorDash, Grubhub, etc.)");
      if (!enriched?.officialUrl) gaps.push("**Website URL** — your business website");
      if (!enriched?.socialLinks || !Object.values(enriched.socialLinks || {}).some((v: any) => v)) gaps.push("**Social media** — Instagram handle, Facebook page, or Google Business Profile link");

      if (gaps.length > 0) {
        setMessages(prev => [...prev, msg('model',
          `I'll collect your profile info right here in the chat. To unlock the full suite of analyses, I need:\n\n${gaps.map((g, i) => `${i + 1}. ${g}`).join('\n')}\n\nJust paste a link or type your answer — we'll go one at a time. What's your menu URL?`
        )]);
        // Stay in a mode where we intercept URLs and save them
        setAwaitingMenuUrl(true);
      } else {
        setMessages(prev => [...prev, msg('model', "Your profile looks good! Try running one of the analyses from the dashboard.")]);
      }
    } finally {
      setIsTyping(false);
    }
  };

  const makeBusinessSlug = (identity: BaseIdentity): string => {
    const slugify = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    const namePart = slugify(identity.name).slice(0, 40);
    const addrParts = (identity.address ?? '').split(',');
    const city = addrParts.length >= 2 ? slugify(addrParts[addrParts.length - 2].trim()).slice(0, 20) : '';
    const zip = (identity as any).zipCode || '';
    return [namePart, city, zip].filter(Boolean).join('-');
  };

  // Save a snapshot of capability results to the business profile (best-effort)
  const saveCapabilitySnapshot = async (
    slug: string | null,
    identity: BaseIdentity | null,
    snapshotUpdate: Record<string, unknown>
  ) => {
    if (!slug || !identity) return;
    try {
      // Include enriched profile fields (menuUrl, socialLinks, etc.) in the identity
      // so they're persisted alongside the capability data
      const enriched = identity as any;
      const enrichedIdentity = {
        ...identity,
        ...(enriched.menuUrl ? { menuUrl: enriched.menuUrl } : {}),
        ...(enriched.socialLinks ? { socialLinks: enriched.socialLinks } : {}),
        ...(enriched.deliveryLinks ? { deliveryLinks: enriched.deliveryLinks } : {}),
      };
      await apiFetch('/api/b/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, identity: enrichedIdentity, snapshotUpdate }),
      });
    } catch { /* non-critical */ }
  };

  const submitUltralocalInterest = async () => {
    // Require sign-in first
    if (!user) {
      setMessages(prev => [...prev, msg('model',
        `🔒 Please **sign in** first so we can notify you when hyperlocal intelligence is available in your area.`
      )]);
      signInWithGoogle();
      return;
    }

    const zipCode = (locatedBusiness as any)?.zipCode;
    setAddMyAreaCity(null);
    if (zipCode) {
      try {
        const res = await apiFetch('/api/pulse/zipcode-interest', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ zipCode, businessType: (locatedBusiness as any)?.businessType }),
        });
        const data = await res.json();
        const location = data.city ? `${data.city} (${zipCode})` : zipCode;
        const others = data.interestCount > 1 ? ` You're #${data.interestCount} to request this area.` : '';
        setMessages(prev => [...prev, msg('model',
          `Got it — we've noted your interest in **${location}**.${others} We'll notify you when hyperlocal intelligence is available for your neighborhood.`
        )]);
      } catch {
        setMessages(prev => [...prev, msg('model',
          `Got it — we've noted your interest. We'll get back to you when hyperlocal intelligence is available in your location.`
        )]);
      }
    }
  };

  const publishProfile = async () => {
    if (!businessSlug || !isAdmin) return;
    try {
      // Get latest version ID
      const versionsRes = await apiFetch(`/api/b/${businessSlug}/versions`);
      if (!versionsRes.ok) { alert('Failed to load versions'); return; }
      const versionsData = await versionsRes.json();
      const versions = versionsData.versions || [];
      if (!versions.length) { alert('No versions to publish'); return; }

      const latestId = versions[0].id;
      const alreadyPublished = versionsData.publishedVersionId;

      if (alreadyPublished === latestId) {
        if (confirm(`Already published (${latestId}). Unpublish?`)) {
          await apiFetch(`/api/b/${businessSlug}/unpublish`, { method: 'POST' });
          setMessages(prev => [...prev, msg('model', `Unpublished **${locatedBusiness?.name}**. The public page is now hidden.`)]);
        }
        return;
      }

      const label = `${latestId} (${versions[0].createdAt?.slice(0, 10) || 'latest'})`;
      if (!confirm(`Publish version ${label} as public case study?`)) return;

      const res = await apiFetch(`/api/b/${businessSlug}/publish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ versionId: latestId }),
      });
      if (res.ok) {
        setMessages(prev => [...prev, msg('model',
          `Published **${locatedBusiness?.name}** as a public case study.\n\nPublic URL: [/b/${businessSlug}](/b/${businessSlug})`
        )]);
      } else {
        alert('Publish failed');
      }
    } catch (e) {
      console.error('Publish error:', e);
      alert('Publish failed');
    }
  };

  const triggerBusinessOverview = async (identity: BaseIdentity, coverage?: { ultralocal: boolean; zipCode?: string; coverageCity?: string | null }) => {
    setIsDiscovering(true);
    setActiveCapability("discovery");
    setCapabilityStartTime(Date.now());

    try {
      const res = await apiFetch('/api/overview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity, light: !user })
      });

      if (res.ok) {
        const overview = await res.json();
        setBusinessOverview(overview);

        // Generate slug and save business profile for shareable URL
        const slug = makeBusinessSlug(identity);
        setBusinessSlug(slug);
        window.history.replaceState(null, '', '/b/' + slug);
        // Save in background — non-critical
        apiFetch('/api/b/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug, identity, snapshot: { overview } }),
        }).catch(() => { /* non-critical */ });

        // Build conversational insight message with real numbers
        const parts: string[] = [];
        const snap = overview.businessSnapshot;
        const market = overview.marketPosition;
        const econ = overview.localEconomy;
        const buzz = overview.localBuzz;
        const dash = overview.dashboard;

        if (snap) {
          let intro = `Here's what I found about **${snap.name}**`;
          if (snap.rating) intro += ` — rated **${snap.rating}★**${snap.reviewCount ? ` (${snap.reviewCount} reviews)` : ''}`;
          intro += '.';
          parts.push(intro);
        }

        // Market + economy in one section
        const marketParts = [];
        if (market) {
          marketParts.push(`**${market.competitorCount} competitors** nearby (${market.saturationLevel} saturation)`);
          if (market.ranking) marketParts.push(market.ranking);
        }
        if (econ) {
          if (econ.medianIncome) marketParts.push(`**${econ.medianIncome}** median household income`);
          if (econ.population) marketParts.push(`**${econ.population}** residents`);
          if (econ.keyFact) marketParts.push(econ.keyFact);
        }
        if (marketParts.length) parts.push(marketParts.join('. ') + '.');

        // Nearby competitors from dashboard
        if (dash?.competitors?.length) {
          const compNames = dash.competitors.slice(0, 5).map((c: any) => `**${c.name}** (${c.cuisine || c.category}, ${c.distanceM}m)`);
          parts.push(`**Your neighbors:** ${compNames.join(', ')}`);
        }

        // This week's local intel from pulse
        if (buzz?.headline || dash?.pulseHeadline) {
          parts.push(`**This week:** ${buzz?.headline || dash?.pulseHeadline}`);
        }
        if (dash?.events?.length) {
          const eventList = dash.events.slice(0, 3).map((ev: any) => `• ${ev.what}${ev.when ? ` (${ev.when})` : ''}`).join('\n');
          parts.push(`**Local events:**\n${eventList}`);
        }
        if (dash?.communityBuzz) {
          parts.push(`**Community buzz:** ${dash.communityBuzz}`);
        }

        // Top pulse insights
        if (dash?.topInsights?.length) {
          const insights = dash.topInsights.slice(0, 2).map((i: any) => `• **${humanize(i.title)}** — ${i.recommendation}`).join('\n');
          parts.push(`**Intelligence from this week's analysis:**\n${insights}`);
        }

        // Opportunities from synthesizer
        if (overview.keyOpportunities?.length) {
          const opps = overview.keyOpportunities.slice(0, 2).map((o: any) => `• **${humanize(o.title)}** — ${o.detail}`).join('\n');
          parts.push(`**Opportunities:**\n${opps}`);
        }

        // Tech intelligence — AI tools & platform updates
        if (dash?.aiTools?.length) {
          const toolLines = dash.aiTools.map((t: any) => {
            const label = t.url ? `[**${t.tool}**](${t.url})` : `**${t.tool}**`;
            return `• ${label} — ${t.capability}`;
          }).join('\n');
          parts.push(`**Tech tools your competitors are adopting:**\n${toolLines}`);
        } else if (dash?.techHighlight) {
          parts.push(`**Tech highlight:** ${dash.techHighlight}`);
        }

        // Data sources badge
        if (dash?.confirmedSources) {
          parts.push(`*Based on ${dash.confirmedSources} verified data sources for this area.*`);
        }

        parts.push('What would you like to dig into? Ask me anything about your market, competitors, or opportunities.');

        setMessages(prev => [...prev, msg('model', parts.join('\n\n'))]);

        // Show ultralocal interest prompt if coverage is national-only
        const dashCoverage = overview?.dashboard?.coverage;
        if (coverage && !coverage.ultralocal && dashCoverage !== 'ultralocal') {
          const cityName = coverage.coverageCity || 'your area';
          const cityLabel = coverage.zipCode && coverage.coverageCity
            ? `${coverage.coverageCity} (${coverage.zipCode})`
            : coverage.coverageCity || coverage.zipCode || 'your area';
          setAddMyAreaCity(cityLabel);
        }
      } else {
        console.error("Overview returned", res.status);
        setMessages(prev => [...prev, msg('model', `I found **${identity.name}** but couldn't generate a full overview right now. Try again in a moment.`)]);
      }
    } catch (e) {
      console.error("Overview failed", e);
      setMessages(prev => [...prev, msg('model', `Something went wrong generating the overview. Please try again.`)]);
    } finally {
      setIsDiscovering(false);
      setActiveCapability(null);
      setCapabilityStartTime(null);
    }
  };

  // Fast-track location from Places Autocomplete — checks coverage tier, then runs overview
  const handlePlaceSelect = async (identity: BaseIdentity) => {
    // Add user message immediately
    setMessages(prev => [...prev, msg('user', identity.name)]);

    // --- Coverage check (non-blocking — all US zips proceed) ---
    const zipCode = (identity as any).zipCode;
    let ultralocal = false;
    let coverageCity: string | null = null;

    if (zipCode) {
      try {
        const valRes = await apiFetch(`/api/places/validate-zipcode?zipCode=${zipCode}`);
        if (valRes.ok) {
          const valData = await valRes.json();
          ultralocal = valData.ultralocal === true;
          coverageCity = valData.city || null;
        }
      } catch (e) {
        console.error("Zipcode coverage check failed, proceeding anyway", e);
      }
    }

    // Track for lead capture
    if (!hasProvidedEmail && !searchDocId) {
      try {
        const trackRes = await apiFetch('/api/track', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: identity.name })
        });
        if (trackRes.ok) {
          const trackData = await trackRes.json();
          setSearchDocId(trackData.id);
        }
      } catch (e) { console.error("Tracking failed", e); }
    }

    // Show coverage-aware discovery message
    const locationLabel = coverageCity || (identity.address?.split(',').slice(-3, -1).join(',').trim()) || identity.address;
    setMessages(prev => [
      ...prev,
      msg('model', ultralocal
        ? `Found **${identity.name}** at ${identity.address}! 📡 ${locationLabel} has **ultralocal weekly coverage** — pulling live neighborhood intelligence...`
        : `Found **${identity.name}** at ${identity.address}! Analyzing your market with national industry data...`
      ),
    ]);

    // Reset state
    setLocatedBusiness(identity);
    setReport(null);
    setForecast(null);
    setSeoReport(null);
    setCompetitiveReport(null);
    setSocialAuditReport(null);
    setCapabilities([]);
    setProfileReportUrl(null);
    setMarginReportUrl(null);
    setTrafficReportUrl(null);
    setSeoReportUrl(null);
    setCompetitiveReportUrl(null);
    setMarketingReportUrl(null);
    setProfileHasBeenBuilt(false);

    // --- Check if we already have a saved profile for this business ---
    const slug = makeBusinessSlug(identity);
    setBusinessSlug(slug);
    try {
      const savedRes = await apiFetch(`/api/b/${slug}/public`);
      if (savedRes.ok) {
        const saved = await savedRes.json();
        if (saved.snapshot) {
          // Restore saved data instantly
          const snap = saved.snapshot;
          const savedIdentity = saved.identity || identity;
          setLocatedBusiness({ ...identity, ...savedIdentity });
          if (snap.overview) setBusinessOverview(snap.overview);
          if (snap.margin?.data) { setReport(snap.margin.data); setMarginReportUrl(snap.margin.reportUrl || null); }
          if (snap.traffic?.data) { setForecast(snap.traffic.data); setTrafficReportUrl(snap.traffic.reportUrl || null); }
          if (snap.seo?.data) { setSeoReport(snap.seo.data); setSeoReportUrl(snap.seo.reportUrl || null); }
          if (snap.competitive?.data) { setCompetitiveReport(snap.competitive.data); setCompetitiveReportUrl(snap.competitive.reportUrl || null); }
          if (snap.marketing?.data) { setSocialAuditReport(snap.marketing.data); setMarketingReportUrl(snap.marketing.reportUrl || null); }
          if (saved.identity?.menuUrl || saved.identity?.socialLinks) setProfileHasBeenBuilt(true);
          window.history.replaceState(null, '', '/b/' + slug);

          setMessages(prev => [...prev, msg('model',
            `Welcome back! I've restored your saved analysis for **${identity.name}**. All previously discovered insights are loaded.`
          )]);

          // Still refresh the overview in background for latest pulse data
          triggerBusinessOverview(identity, { ultralocal, zipCode, coverageCity });
          return;
        }
      }
    } catch { /* No saved profile — run fresh discovery */ }

    // No saved profile — trigger fresh overview
    triggerBusinessOverview(identity, { ultralocal, zipCode, coverageCity });
  };

  const handleSelectCapability = async (capId: string) => {
    if (!locatedBusiness) return;

    // Auth gate: capabilities require sign-in
    if (!user) {
      setPendingCapability(capId);
      setShowAuthWall(true);
      setMessages(prev => [...prev, msg('model', 'Sign in to unlock detailed analysis. It only takes a moment!')]);
      return;
    }

    executeCapability(capId);
  };

  // Show save-report banner after each capability report completes
  const maybeShowAuthWall = () => {
    if (!user && !hasProvidedEmail) {
      setShowAuthWall(true);
      // Auto-dismiss after 10s if not interacted with
      setTimeout(() => setShowAuthWall(false), 10000);
    }
  };

  const sendReportEmailAsync = (reportType: string, reportUrl: string, businessName: string, summary: string) => {
    if (!userEmail || !reportUrl) return;
    apiFetch('/api/send-report-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: userEmail, reportUrl, reportType, businessName, summary }),
    }).catch((err) => console.error('[Email] Fire-and-forget failed:', err));
  };

  // State for collecting missing data before running a capability
  const [pendingCapForUrl, setPendingCapForUrl] = useState<string | null>(null);

  const executeCapability = async (capId: string) => {
    if (!locatedBusiness) return;

    // ── Concurrency guard: only one analysis at a time ──────────────
    if (activeCapability) {
      const capLabels: Record<string, string> = { surgery: 'Margin Analysis', seo: 'SEO Audit', traffic: 'Traffic Forecast', competitive: 'Competitive Intel', marketing: 'Social Audit' };
      const running = capLabels[activeCapability] || activeCapability;
      setMessages(prev => [...prev, msg('model',
        `**${running}** is still running. I'll start this one when it finishes — or wait a moment and try again.`
      )]);
      return;
    }

    const enriched = locatedBusiness as any;

    // ── Pre-flight checks: prompt user for missing data ──────────────
    if (capId === 'seo' && !enriched.officialUrl) {
      setPendingCapForUrl('seo');
      setMessages(prev => [...prev, msg('model',
        `I need a **website URL** to run the SEO audit. Paste the URL for **${locatedBusiness.name}** and I'll start the analysis.`
      )]);
      return;
    }
    if (capId === 'surgery' && !enriched.officialUrl && !enriched.menuUrl) {
      setPendingCapForUrl('surgery');
      setMessages(prev => [...prev, msg('model',
        `I need a **menu URL** or **website URL** to run the margin analysis. Paste a link (your website, DoorDash, Grubhub — anything with prices).`
      )]);
      return;
    }
    if (capId === 'competitive' && !enriched.officialUrl && !enriched.address) {
      setPendingCapForUrl('competitive');
      setMessages(prev => [...prev, msg('model',
        `I need at least a **website** or **address** to run competitive analysis. Paste your website URL.`
      )]);
      return;
    }

    // Only clear the specific report being re-run (keep others for reference)
    if (capId === 'surgery') setReport(null);
    if (capId === 'seo') setSeoReport(null);
    if (capId === 'traffic') { setForecast(null); setSelectedDay(null); setSelectedSlot(null); }
    if (capId === 'competitive') setCompetitiveReport(null);

    // Track which capability is running
    setActiveCapability(capId);
    setCapabilityStartTime(Date.now());

    // Switch to the capability's section so user sees the loading state
    const sectionMap: Record<string, ActiveSection> = { surgery: 'margin', seo: 'seo', traffic: 'traffic', competitive: 'competitive' };
    if (sectionMap[capId]) setActiveSection(sectionMap[capId]);

    const { menuScreenshotBase64: _stripped, ...identityForApi } = locatedBusiness as any;

    if (capId === 'surgery') {
      setMessages(prev => [...prev, msg('model', "Checking your menu prices against commodity costs and local competitors... ⏱️")]);
      setIsTyping(true);

      try {
        // Pass the enriched profile (without base64) so /api/analyze can skip the Crawler
        const enrichedForApi = locatedBusiness as any;
        const payload = {
          url: enrichedForApi.officialUrl || enrichedForApi.menuUrl || '',
          enrichedProfile: identityForApi,
          menuUrl: enrichedForApi.menuUrl || undefined,
          advancedMode: false
        };
        const res = await apiFetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          // Don't expose raw server errors — frame as a menu discovery issue
          throw new Error('menu_not_found');
        }

        const data = await res.json();

        // P2b: Handle menuNotFound — ask user for a menu URL
        if (data.menuNotFound) {
          setAwaitingMenuUrl(true);
          setMessages(prev => [...prev, msg('model', "I couldn't find a menu online for this business. Paste a link to the menu (website page, PDF, or delivery platform like DoorDash/Grubhub) and I'll analyze it.")]);
          return;
        }

        setReport(data);
        setActiveSection('margin');
        if (data.reportUrl) {
          setMarginReportUrl(data.reportUrl);
          const totalLeakage = data.menu_items?.reduce((s: number, i: { price_leakage: number }) => s + i.price_leakage, 0) || 0;
          sendReportEmailAsync('margin', data.reportUrl, locatedBusiness!.name, `$${totalLeakage.toFixed(2)} total profit leakage detected across ${data.menu_items?.length || 0} menu items. Overall score: ${data.overall_score}/100.`);
        }
        saveCapabilitySnapshot(businessSlug, locatedBusiness, { margin: { data, reportUrl: data.reportUrl || null } });
        setMessages(prev => [...prev, msg('model', "Price analysis complete! Your optimization dashboard is ready.\n\n[Schedule a call](https://hephae.co/schedule) to discuss your pricing strategy with our team.")]);
        maybeShowAuthWall();

      } catch (e: any) {
        console.error('[Margin] Analysis failed:', e.message);
        // Frame missing menu as a finding, not an error
        setLocatedBusiness(prev => prev ? { ...prev, profileFindings: { ...(prev as any).profileFindings, noMenuOnline: true } } as any : prev);
        setMessages(prev => [...prev, msg('model',
          `**Finding:** Your menu isn't easily discoverable online. This is a common gap — **68% of customers check prices online before visiting**.\n\n` +
          `To run the full Margin Analysis, I need a direct link to your menu with prices. Paste one below:\n` +
          `• Your website's menu page\n` +
          `• DoorDash, Grubhub, or UberEats store page\n` +
          `• Any page listing your items with prices`
        )]);
        setAwaitingMenuUrl(true);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    } else if (capId === 'traffic') {
      setMessages(prev => [...prev, msg('model', "Predicting your foot traffic patterns — analyzing local events, weather, and historical trends... ⏱️")]);
      setIsTyping(true);

      try {
        const res = await apiFetch('/api/capabilities/traffic', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: identityForApi }),
        });

        if (!res.ok) {
          let errMsg = "Analysis Failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { /* suppress raw errors */ }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setForecast(data);
        setActiveSection('traffic');
        if (data.reportUrl) {
          setTrafficReportUrl(data.reportUrl);
          sendReportEmailAsync('traffic', data.reportUrl, locatedBusiness!.name, data.summary || 'Your 3-day foot traffic forecast is ready.');
        }

        if (data.forecast?.length) {
          const firstDay = data.forecast[0];
          setSelectedDay(firstDay);
          setSelectedSlot(firstDay.slots.find((s: any) => s.score > 70) || firstDay.slots[0]);
        }
        saveCapabilitySnapshot(businessSlug, locatedBusiness, { traffic: { data, reportUrl: data.reportUrl || null } });

        setMessages(prev => [...prev, msg('model', `Forecast complete!\n\n**Executive Summary**:\n${data.summary}\n\n[Schedule a call](https://hephae.co/schedule) to plan your staffing strategy with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        console.error('[Traffic] Forecast failed:', e.message);
        setMessages(prev => [...prev, msg('model', `The foot traffic forecast couldn't complete right now. This can happen if local event data isn't available yet. Try again in a moment.`)]);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    } else if (capId === 'seo') {
      setMessages(prev => [...prev, msg('model', "Checking how visible you are on Google — analyzing search rankings, website speed, and content quality... ⏱️")]);
      setIsTyping(true);

      try {
        const res = await apiFetch('/api/capabilities/seo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: identityForApi }),
        });

        if (!res.ok) {
          let errMsg = "Analysis Failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { /* suppress raw errors */ }
          throw new Error(errMsg);
        }

        const data = await res.json();
        const sectionCount = data.sections?.length || 0;

        if (sectionCount === 0) {
          // Agent returned no sections — don't show a blank dashboard
          const scoreNote = data.overallScore ? ` (estimated score: ${data.overallScore}/100)` : '';
          setMessages(prev => [...prev, msg('model', `The SEO Auditor completed but returned incomplete data${scoreNote}. ${data.summary || 'The model may have hit a rate limit or timed out.'}\n\nYou can try running the audit again from the action bar.`)]);
          // Re-enable capabilities so user can retry
          setCapabilities(prev => prev.length > 0 ? prev : [
            { id: 'seo', label: 'Retry Google Presence Check', icon: undefined },
          ]);
        } else {
          setSeoReport(data);
          setActiveSection('seo');
          if (data.reportUrl) {
            setSeoReportUrl(data.reportUrl);
            sendReportEmailAsync('seo', data.reportUrl, locatedBusiness!.name, `SEO score: ${data.overallScore ?? 'N/A'}/100. ${sectionCount} categories analyzed. ${data.summary || ''}`);
          }
          saveCapabilitySnapshot(businessSlug, locatedBusiness, { seo: { data, reportUrl: data.reportUrl || null } });
          setMessages(prev => [...prev, msg('model', `SEO Audit complete! Verified ${sectionCount} critical infrastructure categories.\n\n[Schedule a call](https://hephae.co/schedule) to improve your search rankings with our team.`)]);
          maybeShowAuthWall();
        }

      } catch (e: any) {
        console.error('[SEO] Audit failed:', e.message);
        setMessages(prev => [...prev, msg('model', `The SEO audit ran into an issue. This can happen with complex websites. Try again in a moment, or ask me a specific question about your online presence.`)]);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    } else if (capId === 'marketing') {
      setMessages(prev => [...prev, msg('model', "Checking your social media presence across all platforms... ⏱️")]);
      setIsTyping(true);

      try {
        const res = await apiFetch('/api/capabilities/marketing', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: identityForApi }),
        });

        if (!res.ok) {
          let errMsg = "Social media check failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { /* suppress raw errors */ }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setSocialAuditReport(data);
        if (data.reportUrl) {
          setMarketingReportUrl(data.reportUrl);
          sendReportEmailAsync('marketing', data.reportUrl, locatedBusiness!.name, data.summary || 'Your social media audit is ready.');
        }
        saveCapabilitySnapshot(businessSlug, locatedBusiness, { marketing: { data, reportUrl: data.reportUrl || null } });

        const platformCount = data.platforms?.length || 0;
        setMessages(prev => [...prev, msg('model', `**Social media check** for **${locatedBusiness.name}** is complete! Score: **${data.overall_score ?? 'N/A'}/100** across ${platformCount} platform${platformCount !== 1 ? 's' : ''}.${data.summary ? `\n\n${data.summary}` : ''}\n\n[Schedule a call](https://hephae.co/schedule) to build your social strategy with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        console.error('[Social] Audit failed:', e.message);
        setMessages(prev => [...prev, msg('model', `The social media audit couldn't complete right now. Try again in a moment.`)]);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    } else if (capId === 'competitive') {
      // Competitive analysis needs competitors from the overview
      const competitors = businessOverview?.dashboard?.competitors;
      if (!competitors?.length) {
        setMessages(prev => [...prev, msg('model',
          `I need competitor data to run competitive analysis. This comes from the business overview — let me refresh it first.`
        )]);
        setActiveCapability(null);
        setCapabilityStartTime(null);
        // Re-trigger overview which will populate competitors
        triggerBusinessOverview(locatedBusiness);
        return;
      }

      setMessages(prev => [...prev, msg('model', "Analyzing how you stack up against your closest local competitors... ⏱️")]);
      setIsTyping(true);

      try {
        // Include competitors from the overview dashboard in the identity
        const identityWithCompetitors = { ...identityForApi, competitors };
        const res = await apiFetch('/api/capabilities/competitive', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: identityWithCompetitors }),
        });

        if (!res.ok) {
          let errMsg = "Analysis Failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { /* suppress raw errors */ }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setCompetitiveReport(data);
        setActiveSection('competitive');
        if (data.reportUrl) {
          setCompetitiveReportUrl(data.reportUrl);
          sendReportEmailAsync('competitive', data.reportUrl, locatedBusiness!.name, data.market_summary || 'Your competitive strategy report is ready.');
        }
        saveCapabilitySnapshot(businessSlug, locatedBusiness, { competitive: { data, reportUrl: data.reportUrl || null } });
        setMessages(prev => [...prev, msg('model', `Competitive Strategy complete! ${data.market_summary}\n\n[Schedule a call](https://hephae.co/schedule) to discuss your competitive positioning with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        console.error('[Competitive] Analysis failed:', e.message);
        setMessages(prev => [...prev, msg('model', `The competitive analysis couldn't complete. This usually means we need more competitor data. Try running it again after the overview refreshes.`)]);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    }
  };

  const copyReportUrl = (url: string) => {
    navigator.clipboard.writeText(url).then(() => {
      setCopyToast(true);
      setTimeout(() => setCopyToast(false), 2500);
    });
  };

  const activeReportUrl = marginReportUrl || trafficReportUrl || seoReportUrl || competitiveReportUrl || marketingReportUrl;

  const getActiveReportType = (): string => {
    if (marginReportUrl) return 'margin';
    if (trafficReportUrl) return 'traffic';
    if (seoReportUrl) return 'seo';
    if (competitiveReportUrl) return 'competitive';
    if (marketingReportUrl) return 'marketing';
    return 'profile';
  };

  const getActiveSummary = (): string => {
    if (report) {
      const totalLeakage = report.menu_items?.reduce((s, i) => s + i.price_leakage, 0) || 0;
      return `$${totalLeakage.toFixed(2)} total profit leakage detected across ${report.menu_items?.length || 0} menu items. Overall score: ${report.overall_score}/100.`;
    }
    if (forecast) return forecast.summary || `3-day foot traffic forecast for ${forecast.business?.name || 'your business'}`;
    if (seoReport) return `SEO score: ${seoReport.overallScore}/100. ${seoReport.summary || ''}`;
    if (competitiveReport) return competitiveReport.market_summary || 'Competitive analysis complete.';
    if (socialAuditReport) return socialAuditReport.summary || 'Social media audit complete.';
    return `Business analysis for ${locatedBusiness?.name || 'your business'}`;
  };

  const getActiveHeadline = (): string => {
    if (report) {
      const totalLeakage = report.menu_items?.reduce((s: number, i: any) => s + (i.price_leakage || 0), 0) || 0;
      return `$${Math.round(totalLeakage).toLocaleString()}/mo`;
    }
    if (seoReport) return `${seoReport.overallScore || 0}/100`;
    if (forecast) return '3-Day Forecast';
    if (competitiveReport) return `${(competitiveReport as any).competitor_profiles?.length || 0} Competitors`;
    if (socialAuditReport) return `${socialAuditReport.overall_score || 0}/100`;
    return '';
  };

  const getActiveSubtitle = (): string => {
    if (report) return 'Profit Leakage Detected';
    if (seoReport) return 'SEO Performance Score';
    if (forecast) return 'Foot Traffic Prediction';
    if (competitiveReport) return 'Market Analysis';
    if (socialAuditReport) return 'Social Media Health';
    return 'Business Intelligence';
  };

  const getActiveHighlight = (): string => {
    if (report) {
      const sorted = [...(report.menu_items || [])].sort((a: any, b: any) => (b.price_leakage || 0) - (a.price_leakage || 0));
      return sorted[0] ? `Top Fix: ${sorted[0].item_name}` : '';
    }
    return '';
  };

  const downloadSocialCard = async () => {
    if (!report) return;
    const topLeak = report.menu_items.sort((a, b) => b.price_leakage - a.price_leakage)[0];
    const totalLeakage = report.menu_items.reduce((s, i) => s + i.price_leakage, 0);

    const res = await apiFetch('/api/social-card', {
      method: "POST",
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        businessName: report.identity.name,
        totalLeakage,
        topItem: topLeak ? topLeak.item_name : "Menu Optimization"
      })
    });

    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "Hephae-Report.png";
      a.click();
    }
  };

  const renderSurgeonReport = () => {
    if (!report) return null;
    const { identity, menu_items, overall_score } = report;
    const strategic_advice = Array.isArray(report.strategic_advice) ? report.strategic_advice : typeof report.strategic_advice === 'string' ? [report.strategic_advice] : [];
    const totalLeakage = menu_items.reduce((s, i) => s + i.price_leakage, 0);
    const topLeaks = menu_items.filter(i => i.price_leakage > 0).sort((a, b) => b.price_leakage - a.price_leakage);

    const leakageChartData = topLeaks.slice(0, 8).map(item => ({
      name: item.item_name.length > 14 ? item.item_name.slice(0, 14) + '…' : item.item_name,
      leakage: item.price_leakage,
    }));
    const leakageColors = ['#ef4444', '#f97316', '#f59e0b', '#eab308', '#ec4899', '#8b5cf6', '#6366f1', '#3b82f6'];

    return (
      <div className="w-full h-full overflow-y-auto pb-20 animate-fade-in relative" style={{ background: 'linear-gradient(135deg, #eef2ff 0%, #faf5ff 40%, #fff1f2 100%)', color: '#1e293b' }}>
        <BlobBackground className="opacity-20 fixed" />
        <div className="absolute inset-0 pointer-events-none opacity-[0.25]">
          <NeuralBackground />
        </div>

        <div className="relative z-10 p-4 md:p-8">
          {/* Gradient Header */}
          <header className="mb-6 md:mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 shadow-xl animate-fade-in-up">
            <div className="flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 md:gap-4 min-w-0">
                {identity.logoUrl ? (
                  <img src={identity.logoUrl} className="h-10 w-10 md:h-12 md:w-12 rounded-full object-cover border-2 border-white/30 shadow-lg flex-shrink-0" alt="Logo" />
                ) : (
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                    <Building2 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                  </div>
                )}
                <div className="min-w-0">
                  <h1 className="text-lg md:text-xl font-bold text-white truncate">{identity.name}</h1>
                  <p className="text-indigo-100 text-xs md:text-sm">Price Optimization Report</p>
                </div>
              </div>
              <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
                <span className="hidden md:block"><HephaeLogo size="sm" variant="white" /></span>
                <button onClick={() => setReport(null)} className="w-9 h-9 md:w-10 md:h-10 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors" title="Close Report">
                  <X size={18} />
                </button>
              </div>
            </div>
          </header>

          {/* Score + Leakage Hero Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 mb-6 md:mb-8">
            <div className="p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-indigo-100 shadow-sm flex flex-col items-center justify-center animate-fade-in-up stagger-1">
              <RadialScoreChart score={overall_score} size={140} label="Health" color="#6366f1" />
              <p className="text-xs text-gray-500 mt-2 font-semibold uppercase tracking-wider">Surgical Score</p>
            </div>
            <div className="p-6 rounded-2xl bg-gradient-to-br from-red-50 to-orange-50 border border-red-200 shadow-sm flex flex-col justify-center animate-fade-in-up stagger-1">
              <h3 className="text-red-600 font-semibold mb-1 flex items-center gap-2 text-sm">
                <AlertTriangle size={16} /> PROFIT LEAKAGE DETECTED
              </h3>
              <div className="text-4xl font-black text-red-600 tracking-tight">
                ${totalLeakage.toLocaleString()}
              </div>
              <p className="text-sm text-red-400 mt-1">per cycle</p>
              <div className="mt-3 flex items-center gap-2">
                <div className="h-2 flex-1 bg-red-100 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-red-500 to-orange-500 rounded-full animate-pulse" style={{ width: `${Math.min(100, (totalLeakage / 500) * 100)}%` }} />
                </div>
              </div>
            </div>
          </div>

          {/* Leakage Bar Chart */}
          <div className="mb-8 p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-100 shadow-sm animate-fade-in-up stagger-2">
            <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><BarChart3 size={18} className="text-indigo-500" /> Leakage by Item</h3>
            <RechartsBarChart data={leakageChartData} barKey="leakage" nameKey="name" colors={leakageColors} layout="vertical" height={Math.max(180, leakageChartData.length * 35)} />
          </div>

          {/* Surgical Breakdown Table */}
          <div className="rounded-2xl border border-indigo-100 bg-white/80 backdrop-blur-sm shadow-sm overflow-hidden mb-8 animate-fade-in-up stagger-2">
            <div className="p-5 border-b border-indigo-50 bg-gradient-to-r from-indigo-50 to-purple-50">
              <h3 className="font-bold text-lg text-indigo-900 flex items-center gap-2"><Scale size={18} /> Surgical Breakdown</h3>
            </div>
            <div className="overflow-x-auto">
            <table className="w-full text-left text-sm min-w-[540px]">
              <thead className="bg-indigo-50/50 text-xs uppercase tracking-wider text-indigo-400">
                <tr>
                  <th className="p-3 md:p-4">Item</th>
                  <th className="p-3 md:p-4">Benchmark</th>
                  <th className="p-3 md:p-4">Price</th>
                  <th className="p-3 md:p-4 text-emerald-600">Rec.</th>
                  <th className="p-3 md:p-4 text-right text-red-500">Leakage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {topLeaks.map((item, i) => (
                  <tr key={i} className="hover:bg-indigo-50/40 transition-colors animate-fade-in-right" style={{ animationDelay: `${0.18 + i * 0.04}s` }}>
                    <td className="p-3 md:p-4 text-gray-900 font-medium">{item.item_name}</td>
                    <td className="p-3 md:p-4 text-gray-500">${item.competitor_benchmark.toFixed(2)}</td>
                    <td className="p-3 md:p-4 text-gray-500">${item.current_price.toFixed(2)}</td>
                    <td className="p-3 md:p-4 font-bold text-emerald-600">${item.recommended_price.toFixed(2)}</td>
                    <td className="p-3 md:p-4 text-right">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-mono text-xs font-bold">+${item.price_leakage.toFixed(2)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>

          {/* Strategic Advice */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 shadow-sm mb-8 animate-fade-in-up stagger-3">
            <h3 className="text-indigo-700 font-bold mb-4 flex items-center gap-2"><Zap size={18} /> STRATEGIC ADVICE</h3>
            <div className="space-y-3">
              {strategic_advice.map((tip, i) => (
                <div key={i} className="p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-indigo-100 text-sm text-gray-700 leading-relaxed animate-fade-in-up flex items-start gap-3" style={{ animationDelay: `${0.24 + i * 0.06}s` }}>
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold flex items-center justify-center mt-0.5">{i + 1}</span>
                  <span>{tip}</span>
                </div>
              ))}
            </div>
          </div>

          <button onClick={downloadSocialCard} className="w-full py-4 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 hover:from-indigo-500 hover:via-purple-500 hover:to-pink-400 font-bold text-white shadow-lg flex items-center justify-center gap-2 transition-all animate-fade-in-up stagger-4 hover:shadow-xl hover:scale-[1.01]">
            <Download size={20} /> Download Integrity Report
          </button>
        </div>
      </div>
    );
  };

  const renderTrafficForecast = () => {
    if (!forecast) return null;

    // Compute daily traffic summary for stats
    const trafficLevelValue = (level: string) => {
      const l = level?.toUpperCase() || '';
      if (l === 'VERY_HIGH') return 4;
      if (l === 'HIGH') return 3;
      if (l === 'MEDIUM') return 2;
      if (l === 'LOW') return 1;
      return 0;
    };
    const dailySummary = forecast.forecast.map(day => {
      const avg = day.slots.reduce((s, sl) => s + trafficLevelValue(sl.level), 0) / Math.max(day.slots.length, 1);
      return { name: day.dayOfWeek?.slice(0, 3) || day.date?.slice(5) || '?', traffic: +(avg * 25).toFixed(0) };
    });
    const totalEvents = forecast.forecast.reduce((s, d) => s + (d.localEvents?.length || 0), 0);
    const peakDay = dailySummary.reduce((best, d) => d.traffic > best.traffic ? d : best, dailySummary[0]);

    return (
      <div className="w-full h-full overflow-y-auto pb-20 animate-fade-in relative" style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 40%, #ecfeff 100%)', color: '#1e293b' }}>
        <BlobBackground className="opacity-20 fixed" />
        <div className="absolute inset-0 pointer-events-none opacity-[0.20]">
          <NeuralBackground />
        </div>

        <div className="relative z-10 p-4 md:p-8">
          {/* Gradient Header */}
          <header className="mb-6 md:mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-500 to-cyan-500 shadow-xl animate-fade-in-up">
            <div className="flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 md:gap-4 min-w-0">
                {((locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon) ? (
                  <img src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon} className="h-10 w-10 md:h-12 md:w-12 rounded-full object-cover border-2 border-white/30 shadow-lg flex-shrink-0" alt="Logo" />
                ) : (
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                    <Users className="w-5 h-5 md:w-6 md:h-6 text-white" />
                  </div>
                )}
                <div className="min-w-0">
                  <h1 className="text-lg md:text-xl font-bold text-white truncate">{forecast.business.name}</h1>
                  <p className="text-emerald-100 text-xs md:text-sm">Foot Traffic Forecast</p>
                </div>
              </div>
              <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
                <span className="hidden md:block"><HephaeLogo size="sm" variant="white" /></span>
                <button onClick={() => setForecast(null)} className="w-9 h-9 md:w-10 md:h-10 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors" title="Close Forecast">
                  <X size={18} />
                </button>
              </div>
            </div>
          </header>

          {/* Quick Stats Row */}
          <div className="grid grid-cols-3 gap-2 md:gap-4 mb-6 md:mb-8 animate-fade-in-up stagger-1">
            <div className="p-3 md:p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-emerald-100 shadow-sm text-center">
              <div className="text-xl md:text-2xl font-black text-emerald-600">{forecast.forecast.length}</div>
              <div className="text-[10px] md:text-xs text-gray-500 font-semibold uppercase tracking-wider mt-1">Days Forecast</div>
            </div>
            <div className="p-3 md:p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-teal-100 shadow-sm text-center">
              <div className="text-xl md:text-2xl font-black text-teal-600">{peakDay?.name || '—'}</div>
              <div className="text-[10px] md:text-xs text-gray-500 font-semibold uppercase tracking-wider mt-1">Peak Day</div>
            </div>
            <div className="p-3 md:p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-cyan-100 shadow-sm text-center">
              <div className="text-xl md:text-2xl font-black text-cyan-600">{totalEvents}</div>
              <div className="text-[10px] md:text-xs text-gray-500 font-semibold uppercase tracking-wider mt-1">Local Events</div>
            </div>
          </div>

          {/* Daily Traffic Bar Chart */}
          {dailySummary.length > 0 && (
            <div className="mb-8 p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-emerald-100 shadow-sm animate-fade-in-up stagger-2">
              <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><Activity size={18} className="text-emerald-500" /> Daily Traffic Index</h3>
              <RechartsBarChart
                data={dailySummary}
                barKey="traffic"
                nameKey="name"
                colors={['#10b981', '#14b8a6', '#06b6d4', '#0891b2', '#059669', '#0d9488', '#0e7490']}
                layout="horizontal"
                height={160}
              />
            </div>
          )}

          {/* Detail Panel */}
          {selectedSlot && selectedDay && (
            <div className="mb-6 rounded-2xl overflow-hidden shadow-xl border border-emerald-100 animate-fade-in-up stagger-1">
              <DetailPanel
                day={selectedDay}
                slot={selectedSlot}
                onAskAI={(query) => { setForecast(null); sendMessage(query); }}
              />
            </div>
          )}

          {/* Heatmap */}
          <div className="p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-emerald-100 shadow-sm overflow-hidden mb-6 animate-fade-in-up stagger-3">
            <HeatmapGrid
              forecast={forecast.forecast}
              onSlotClick={(day, slot) => { setSelectedDay(day); setSelectedSlot(slot); }}
              selectedSlot={selectedSlot && selectedDay ? { dayStr: selectedDay.date, slotLabel: selectedSlot.label } : null}
            />
          </div>
        </div>
      </div>
    );
  };

  const renderCompetitiveReport = () => {
    if (!competitiveReport) return null;

    const threatData = (competitiveReport.competitor_analysis || []).map((comp: any) => ({
      name: (comp.name || '').length > 14 ? comp.name.slice(0, 14) + '…' : comp.name,
      threat: comp.threat_level || 0,
    }));
    const threatColors = ['#f97316', '#ef4444', '#f59e0b', '#ec4899', '#8b5cf6'];

    return (
      <div className="w-full h-full overflow-y-auto pb-20 animate-fade-in relative" style={{ background: 'linear-gradient(135deg, #fff7ed 0%, #fef3c7 40%, #fce7f3 100%)', color: '#1e293b' }}>
        <BlobBackground className="opacity-20 fixed" />
        <div className="absolute inset-0 pointer-events-none opacity-[0.20]">
          <NeuralBackground />
        </div>

        <div className="relative z-10 p-4 md:p-8">
          {/* Gradient Header */}
          <header className="mb-6 md:mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 shadow-xl animate-fade-in-up">
            <div className="flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 md:gap-4 min-w-0">
                {((locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon) ? (
                  <img src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon} className="h-10 w-10 md:h-12 md:w-12 rounded-full object-cover border-2 border-white/30 shadow-lg flex-shrink-0" alt="Logo" />
                ) : (
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                    <Swords className="w-5 h-5 md:w-6 md:h-6 text-white" />
                  </div>
                )}
                <div className="min-w-0">
                  <h1 className="text-lg md:text-xl font-bold text-white truncate">{locatedBusiness?.name || 'Business'}</h1>
                  <p className="text-orange-100 text-xs md:text-sm">Competitive Market Strategy</p>
                </div>
              </div>
              <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
                <span className="hidden md:block"><HephaeLogo size="sm" variant="white" /></span>
                <button onClick={() => setCompetitiveReport(null)} className="w-9 h-9 md:w-10 md:h-10 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors" title="Close Report">
                  <X size={18} />
                </button>
              </div>
            </div>
          </header>

          {/* Executive Summary */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-orange-50 to-amber-50 border border-orange-200 shadow-sm mb-8 animate-fade-in-up stagger-1">
            <h3 className="text-orange-700 font-bold mb-3 flex items-center gap-2"><Target size={18} /> Executive Summary</h3>
            <p className="text-gray-800 text-sm leading-relaxed">{competitiveReport.market_summary}</p>
          </div>

          {/* Threat Level Chart */}
          {threatData.length > 0 && (
            <div className="mb-8 p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-orange-100 shadow-sm animate-fade-in-up stagger-2">
              <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><Eye size={18} className="text-orange-500" /> Threat Level Comparison</h3>
              <RechartsBarChart data={threatData} barKey="threat" nameKey="name" colors={threatColors} layout="vertical" height={Math.max(120, threatData.length * 45)} />
            </div>
          )}

          {/* Rival Positioning Cards */}
          <div className="space-y-6 mb-8 animate-fade-in-up stagger-2">
            <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2"><Shield size={18} className="text-orange-500" /> Rival Positioning Radar</h3>
            <div className="grid grid-cols-1 gap-4">
              {competitiveReport.competitor_analysis.map((comp: any, i: number) => (
                <div key={i} className="p-5 rounded-2xl bg-white/80 backdrop-blur-sm border border-orange-100 hover:border-orange-300 shadow-sm transition-all hover:shadow-md animate-fade-in-up" style={{ animationDelay: `${0.18 + i * 0.08}s` }}>
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-bold text-gray-900 text-lg">{comp.name}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-2.5 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-1000" style={{
                          width: `${(comp.threat_level / 10) * 100}%`,
                          background: comp.threat_level >= 7 ? 'linear-gradient(90deg, #ef4444, #dc2626)' : comp.threat_level >= 4 ? 'linear-gradient(90deg, #f97316, #f59e0b)' : 'linear-gradient(90deg, #22c55e, #16a34a)'
                        }} />
                      </div>
                      <span className={clsx("text-xs font-bold px-2 py-1 rounded-full",
                        comp.threat_level >= 7 ? "bg-red-100 text-red-700" : comp.threat_level >= 4 ? "bg-orange-100 text-orange-700" : "bg-green-100 text-green-700"
                      )}>{comp.threat_level}/10</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                      <div className="text-[10px] text-emerald-600 uppercase font-bold tracking-wider mb-1 flex items-center gap-1"><TrendingUp size={10} /> Strength</div>
                      <div className="text-sm text-gray-700 leading-relaxed">{comp.key_strength}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-red-50 border border-red-200">
                      <div className="text-[10px] text-red-600 uppercase font-bold tracking-wider mb-1 flex items-center gap-1"><AlertTriangle size={10} /> Weakness</div>
                      <div className="text-sm text-gray-700 leading-relaxed">{comp.key_weakness}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Strategic Advantages */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200 shadow-sm mb-8 animate-fade-in-up stagger-3">
            <h3 className="text-indigo-700 font-bold mb-5 flex items-center gap-2"><Zap size={18} /> Strategic Advantages to Leverage</h3>
            <ul className="space-y-3">
              {competitiveReport.strategic_advantages.map((adv: string, i: number) => (
                <li key={i} className="flex gap-4 text-sm text-gray-700 bg-white/80 backdrop-blur-sm border border-indigo-100 p-4 rounded-xl leading-relaxed items-start animate-fade-in-right" style={{ animationDelay: `${0.24 + i * 0.05}s` }}>
                  <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold text-xs flex items-center justify-center shadow-sm">{i + 1}</span>
                  <span>{adv}</span>
                </li>
              ))}
            </ul>
          </div>

          {competitiveReport.sources?.length > 0 && (
            <div className="p-5 rounded-2xl bg-white/60 backdrop-blur-sm border border-gray-200 animate-fade-in-up stagger-4">
              <h3 className="text-gray-500 font-bold mb-3 text-xs uppercase tracking-wider">Analysis Sources</h3>
              <ul className="space-y-1">
                {competitiveReport.sources.map((s: any, i: number) => (
                  <li key={i}>
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-indigo-600 text-sm hover:underline">↗ {s.title || s.url}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderSocialAuditReport = () => {
    if (!socialAuditReport) return null;
    const platforms = socialAuditReport.platforms || [];
    const recs = socialAuditReport.strategic_recommendations || [];
    const benchmarks = socialAuditReport.competitor_benchmarks || [];
    const contentStrategy = socialAuditReport.content_strategy || {};

    const scoreColor = (s: number) => s >= 70 ? 'text-emerald-600' : s >= 40 ? 'text-yellow-600' : 'text-red-600';
    const scoreBg = (s: number) => s >= 70 ? 'bg-emerald-50 border-emerald-200' : s >= 40 ? 'bg-yellow-50 border-yellow-200' : 'bg-red-50 border-red-200';
    const impactColor = (v: string) => v === 'high' ? 'bg-red-100 text-red-700' : v === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700';

    return (
      <div className="w-full h-full overflow-y-auto pb-20 animate-fade-in relative" style={{ background: 'linear-gradient(135deg, #fdf2f8 0%, #fce7f3 40%, #faf5ff 100%)', color: '#1e293b' }}>
        <BlobBackground className="opacity-20 fixed" />
        <div className="absolute inset-0 pointer-events-none opacity-[0.20]">
          <NeuralBackground />
        </div>

        <div className="relative z-10 p-4 md:p-8">
          {/* Header */}
          <header className="mb-6 md:mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-r from-pink-500 via-rose-500 to-fuchsia-500 shadow-xl animate-fade-in-up">
            <div className="flex justify-between items-center gap-3">
              <div className="flex items-center gap-3 md:gap-4 min-w-0">
                {((locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon) ? (
                  <img src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon} className="h-10 w-10 md:h-12 md:w-12 rounded-full object-cover border-2 border-white/30 shadow-lg flex-shrink-0" alt="Logo" />
                ) : (
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                    <Share2 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                  </div>
                )}
                <div className="min-w-0">
                  <h1 className="text-lg md:text-xl font-bold text-white truncate">{locatedBusiness?.name || 'Business'}</h1>
                  <p className="text-pink-100 text-xs md:text-sm">Social Media Health Check</p>
                </div>
              </div>
              <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
                <span className="hidden md:block"><HephaeLogo size="sm" variant="white" /></span>
                <button onClick={() => setSocialAuditReport(null)} className="w-9 h-9 md:w-10 md:h-10 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors" title="Close Report">
                  <X size={18} />
                </button>
              </div>
            </div>
          </header>

          {/* Overall Score */}
          <div className="text-center p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-pink-100 shadow-sm mb-6 md:mb-8 animate-fade-in-up stagger-1">
            <div className={`text-5xl font-black ${scoreColor(socialAuditReport.overall_score || 0)}`}>{socialAuditReport.overall_score || 0}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider font-bold mt-1">Overall Social Health Score</div>
            {socialAuditReport.summary && <p className="text-sm text-gray-600 leading-relaxed mt-3 max-w-lg mx-auto">{socialAuditReport.summary}</p>}
          </div>

          {/* Platform Cards */}
          {platforms.length > 0 && (
            <div className="space-y-4 mb-6 md:mb-8 animate-fade-in-up stagger-2">
              <h3 className="font-bold text-lg text-gray-900 flex items-center gap-2"><Share2 size={18} className="text-pink-500" /> Platform Analysis</h3>
              {platforms.map((p: any, i: number) => (
                <div key={i} className="p-4 md:p-5 rounded-2xl bg-white/80 backdrop-blur-sm border border-pink-100 shadow-sm animate-fade-in-up" style={{ animationDelay: `${0.18 + i * 0.08}s` }}>
                  <div className="flex justify-between items-center mb-3">
                    <div>
                      <span className="font-bold text-gray-900 text-lg capitalize">{p.name}</span>
                      {p.handle && <span className="text-gray-400 text-sm ml-2">{p.handle}</span>}
                    </div>
                    <div className={`px-3 py-1.5 rounded-xl border font-black text-lg ${scoreBg(p.score || 0)} ${scoreColor(p.score || 0)}`}>
                      {p.score || 0}<span className="text-xs font-normal opacity-60">/100</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 mb-3">
                    <div className="bg-gray-50 rounded-xl p-2.5 text-center">
                      <div className="text-[10px] text-gray-400 uppercase font-bold">Followers</div>
                      <div className="text-sm font-bold text-gray-800">{p.followers || 'Unknown'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-2.5 text-center">
                      <div className="text-[10px] text-gray-400 uppercase font-bold">Posting</div>
                      <div className="text-sm font-semibold text-gray-700">{p.posting_frequency || 'Unknown'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-2.5 text-center">
                      <div className="text-[10px] text-gray-400 uppercase font-bold">Engagement</div>
                      <div className="text-sm font-semibold text-gray-700 capitalize">{p.engagement || 'Unknown'}</div>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-2.5 text-center">
                      <div className="text-[10px] text-gray-400 uppercase font-bold">Last Post</div>
                      <div className="text-sm font-semibold text-gray-700">{p.last_post_recency || 'Unknown'}</div>
                    </div>
                  </div>

                  {p.content_themes?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {p.content_themes.map((t: string, j: number) => (
                        <span key={j} className="text-xs px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-600 font-semibold">{t}</span>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {p.strengths?.length > 0 && (
                      <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                        <div className="text-[10px] text-emerald-600 uppercase font-bold tracking-wider mb-1.5 flex items-center gap-1"><TrendingUp size={10} /> Strengths</div>
                        {p.strengths.map((s: string, j: number) => (
                          <div key={j} className="text-sm text-gray-700 leading-relaxed">+ {s}</div>
                        ))}
                      </div>
                    )}
                    {p.weaknesses?.length > 0 && (
                      <div className="p-3 rounded-xl bg-red-50 border border-red-200">
                        <div className="text-[10px] text-red-600 uppercase font-bold tracking-wider mb-1.5 flex items-center gap-1"><AlertTriangle size={10} /> Weaknesses</div>
                        {p.weaknesses.map((w: string, j: number) => (
                          <div key={j} className="text-sm text-gray-700 leading-relaxed">- {w}</div>
                        ))}
                      </div>
                    )}
                  </div>

                  {p.recommendations?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="text-[10px] text-indigo-600 uppercase font-bold tracking-wider mb-1.5">Recommendations</div>
                      {p.recommendations.map((r: string, j: number) => (
                        <div key={j} className="text-sm text-indigo-700 leading-relaxed">→ {r}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Competitor Benchmarks */}
          {benchmarks.length > 0 && (
            <div className="p-4 md:p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-pink-100 shadow-sm mb-6 md:mb-8 animate-fade-in-up stagger-3">
              <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><Eye size={18} className="text-pink-500" /> Competitor Benchmarks</h3>
              <div className="space-y-3">
                {benchmarks.map((b: any, i: number) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                    <div>
                      <div className="font-bold text-gray-800">{b.name}</div>
                      <div className="text-xs text-gray-500 capitalize">{b.strongest_platform} · {b.posting_frequency}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-800">{b.followers}</div>
                      <div className="text-xs text-gray-400">followers</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strategic Recommendations */}
          {recs.length > 0 && (
            <div className="p-4 md:p-6 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200 shadow-sm mb-6 md:mb-8 animate-fade-in-up stagger-3">
              <h3 className="text-indigo-700 font-bold mb-4 flex items-center gap-2"><Zap size={18} /> Strategic Recommendations</h3>
              <div className="space-y-3">
                {recs.map((r: any, i: number) => (
                  <div key={i} className="flex gap-3 items-start p-4 bg-white/80 border border-indigo-100 rounded-xl animate-fade-in-right" style={{ animationDelay: `${0.24 + i * 0.05}s` }}>
                    <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold text-xs flex items-center justify-center shadow-sm">{r.priority || i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-bold text-gray-800 text-sm">{r.action}</div>
                      {r.rationale && <div className="text-xs text-gray-500 mt-1">{r.rationale}</div>}
                      <div className="flex gap-2 mt-2">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${impactColor(r.impact)}`}>Impact: {r.impact}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${impactColor(r.effort)}`}>Effort: {r.effort}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Content Strategy */}
          {(contentStrategy.content_pillars?.length > 0 || contentStrategy.hashtag_strategy?.length > 0 || contentStrategy.quick_wins?.length > 0) && (
            <div className="p-4 md:p-6 rounded-2xl bg-white/80 backdrop-blur-sm border border-pink-100 shadow-sm mb-6 md:mb-8 animate-fade-in-up stagger-4">
              <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><Sparkles size={18} className="text-pink-500" /> Content Strategy</h3>
              {contentStrategy.content_pillars?.length > 0 && (
                <div className="mb-4">
                  <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-2">Content Pillars</div>
                  <div className="flex flex-wrap gap-2">
                    {contentStrategy.content_pillars.map((p: string, i: number) => (
                      <span key={i} className="px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold border border-emerald-200">{p}</span>
                    ))}
                  </div>
                </div>
              )}
              {contentStrategy.posting_schedule && (
                <div className="mb-4">
                  <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-1">Posting Schedule</div>
                  <p className="text-sm text-gray-700">{contentStrategy.posting_schedule}</p>
                </div>
              )}
              {contentStrategy.hashtag_strategy?.length > 0 && (
                <div className="mb-4">
                  <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-2">Hashtag Strategy</div>
                  <div className="flex flex-wrap gap-1.5">
                    {contentStrategy.hashtag_strategy.map((h: string, i: number) => (
                      <span key={i} className="px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-600 text-xs font-semibold">{h}</span>
                    ))}
                  </div>
                </div>
              )}
              {contentStrategy.quick_wins?.length > 0 && (
                <div>
                  <div className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-2">Quick Wins</div>
                  {contentStrategy.quick_wins.map((w: string, i: number) => (
                    <div key={i} className="text-sm text-gray-700 mb-1 flex items-start gap-1.5">
                      <Zap size={12} className="text-yellow-500 mt-0.5 flex-shrink-0" /> {w}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Sources */}
          {socialAuditReport.sources?.length > 0 && (
            <div className="p-5 rounded-2xl bg-white/60 backdrop-blur-sm border border-gray-200 animate-fade-in-up stagger-4">
              <h3 className="text-gray-500 font-bold mb-3 text-xs uppercase tracking-wider">Research Sources</h3>
              <ul className="space-y-1">
                {socialAuditReport.sources.map((s: any, i: number) => (
                  <li key={i}>
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-indigo-600 text-sm hover:underline">↗ {s.title || s.url}</a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    );
  };

  const isCentered = !locatedBusiness && !report && !forecast && !seoReport && !competitiveReport && !socialAuditReport;

  // Dynamic follow-up chips — split into insights (about current results) and actions (new capabilities)
  // ── Content-only report renderers (for Amethyst layout — no full-page wrapper) ──

  const renderSurgeonReportContent = () => {
    if (!report) return null;
    const { identity, menu_items, overall_score } = report;
    const strategic_advice = Array.isArray(report.strategic_advice) ? report.strategic_advice : typeof report.strategic_advice === 'string' ? [report.strategic_advice] : [];
    const totalLeakage = menu_items.reduce((s, i) => s + i.price_leakage, 0);
    const topLeaks = menu_items.filter(i => i.price_leakage > 0).sort((a, b) => b.price_leakage - a.price_leakage);
    const leakageChartData = topLeaks.slice(0, 8).map(item => ({
      name: item.item_name.length > 14 ? item.item_name.slice(0, 14) + '…' : item.item_name,
      leakage: item.price_leakage,
    }));
    const leakageColors = ['#ef4444', '#f97316', '#f59e0b', '#eab308', '#ec4899', '#8b5cf6', '#6366f1', '#3b82f6'];

    return (
      <>
        <header className="mb-6 p-5 rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-500 shadow-xl">
          <h1 className="text-xl font-bold text-white">{identity.name} — Price Optimization</h1>
          <p className="text-indigo-100 text-sm">Score: {overall_score}/100 · ${totalLeakage.toLocaleString()} profit leakage detected</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="p-6 rounded-2xl bg-white border border-indigo-100 shadow-sm flex flex-col items-center justify-center">
            <RadialScoreChart score={overall_score} size={140} label="Health" color="#6366f1" />
            <p className="text-xs text-gray-500 mt-2 font-semibold uppercase tracking-wider">Surgical Score</p>
          </div>
          <div className="p-6 rounded-2xl bg-gradient-to-br from-red-50 to-orange-50 border border-red-200 shadow-sm flex flex-col justify-center">
            <h3 className="text-red-600 font-semibold mb-1 flex items-center gap-2 text-sm"><AlertTriangle size={16} /> PROFIT LEAKAGE</h3>
            <div className="text-4xl font-black text-red-600">${totalLeakage.toLocaleString()}</div>
            <p className="text-sm text-red-400 mt-1">per cycle</p>
          </div>
        </div>

        <div className="mb-6 p-6 rounded-2xl bg-white border border-gray-100 shadow-sm">
          <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2"><BarChart3 size={18} className="text-indigo-500" /> Leakage by Item</h3>
          <RechartsBarChart data={leakageChartData} barKey="leakage" nameKey="name" colors={leakageColors} layout="vertical" height={Math.max(180, leakageChartData.length * 35)} />
        </div>

        <div className="rounded-2xl border border-indigo-100 bg-white shadow-sm overflow-hidden mb-6">
          <div className="p-5 border-b border-indigo-50 bg-gradient-to-r from-indigo-50 to-purple-50">
            <h3 className="font-bold text-lg text-indigo-900 flex items-center gap-2"><Scale size={18} /> Surgical Breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm min-w-[540px]">
              <thead className="bg-indigo-50/50 text-xs uppercase tracking-wider text-indigo-400">
                <tr><th className="p-3">Item</th><th className="p-3">Benchmark</th><th className="p-3">Price</th><th className="p-3 text-emerald-600">Rec.</th><th className="p-3 text-right text-red-500">Leakage</th></tr>
              </thead>
              <tbody className="divide-y divide-indigo-50">
                {topLeaks.map((item, i) => (
                  <tr key={i} className="hover:bg-indigo-50/40 transition-colors">
                    <td className="p-3 text-gray-900 font-medium">{item.item_name}</td>
                    <td className="p-3 text-gray-500">${item.competitor_benchmark.toFixed(2)}</td>
                    <td className="p-3 text-gray-500">${item.current_price.toFixed(2)}</td>
                    <td className="p-3 font-bold text-emerald-600">${item.recommended_price.toFixed(2)}</td>
                    <td className="p-3 text-right"><span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-mono text-xs font-bold">+${item.price_leakage.toFixed(2)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 shadow-sm">
          <h3 className="text-indigo-700 font-bold mb-4 flex items-center gap-2"><Zap size={18} /> STRATEGIC ADVICE</h3>
          <div className="space-y-3">
            {strategic_advice.map((tip, i) => (
              <div key={i} className="p-4 rounded-xl bg-white border border-indigo-100 text-sm text-gray-700 leading-relaxed flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold flex items-center justify-center mt-0.5">{i + 1}</span>
                <span>{tip}</span>
              </div>
            ))}
          </div>
        </div>
      </>
    );
  };

  const renderTrafficForecastContent = () => {
    if (!forecast) return null;
    const bizName = (forecast as any).businessName || (forecast as any).business?.name || locatedBusiness?.name;
    return (
      <>
        <header className="mb-6 p-5 rounded-2xl bg-gradient-to-r from-emerald-600 via-teal-500 to-cyan-500 shadow-xl">
          <h1 className="text-xl font-bold text-white">{bizName} — Foot Traffic Forecast</h1>
          {forecast.summary && <p className="text-emerald-100 text-sm mt-1">{forecast.summary}</p>}
        </header>

        {trafficCardData && <FootTrafficCard traffic={trafficCardData} />}

        {forecast.forecast?.length > 0 && (
          <div className="mt-6">
            <HeatmapGrid
              forecast={forecast.forecast}
              selectedSlot={selectedSlot && selectedDay ? { dayStr: selectedDay.dayOfWeek, slotLabel: selectedSlot.label ?? '' } : null}
              onSlotClick={(day, slot) => { setSelectedDay(day); setSelectedSlot(slot); }}
            />
          </div>
        )}
        {selectedDay && selectedSlot && (
          <div className="mt-4">
            <DetailPanel day={selectedDay} slot={selectedSlot} onAskAI={(q: string) => sendMessage(q)} />
          </div>
        )}
      </>
    );
  };

  const renderCompetitiveReportContent = () => {
    if (!competitiveReport) return null;
    return (
      <>
        <header className="mb-6 p-5 rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 shadow-xl">
          <h1 className="text-xl font-bold text-white">{locatedBusiness?.name} — Competitive Analysis</h1>
          {competitiveReport.market_summary && <p className="text-orange-100 text-sm mt-1">{competitiveReport.market_summary}</p>}
        </header>

        {competitiveReport.competitors?.length > 0 && (
          <div className="space-y-4 mb-6">
            {competitiveReport.competitors.map((comp: any, i: number) => (
              <div key={i} className="p-5 rounded-2xl bg-white border border-orange-100 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-bold text-gray-900">{comp.name || `Competitor ${i + 1}`}</h3>
                  {comp.threat_level && <span className={`text-xs font-bold px-2 py-1 rounded-full ${comp.threat_level === 'high' ? 'bg-red-100 text-red-700' : comp.threat_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>{comp.threat_level}</span>}
                </div>
                {comp.strengths && <p className="text-sm text-gray-600">{typeof comp.strengths === 'string' ? comp.strengths : JSON.stringify(comp.strengths)}</p>}
              </div>
            ))}
          </div>
        )}

        {competitiveReport.recommendations?.length > 0 && (
          <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-200 shadow-sm">
            <h3 className="text-indigo-700 font-bold mb-4 flex items-center gap-2"><Zap size={18} /> Strategic Recommendations</h3>
            <div className="space-y-3">
              {competitiveReport.recommendations.map((rec: any, i: number) => (
                <div key={i} className="p-4 rounded-xl bg-white border border-indigo-100 text-sm text-gray-700 leading-relaxed flex items-start gap-3">
                  <span className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 text-white font-bold text-xs flex items-center justify-center shadow-sm">{i + 1}</span>
                  <span>{typeof rec === 'string' ? rec : rec.recommendation || rec.title || JSON.stringify(rec)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </>
    );
  };

  const dynamicChips = useMemo((): SuggestionChip[] => {
    // Suppress regular chips during profile building — profile chips take over
    if (isProfileBuilding) return [];
    return computeSuggestionChips({
      isCentered,
      isDiscovering,
      isTyping,
      businessName: locatedBusiness?.name,
      hasReport: !!report,
      hasForecast: !!forecast,
      hasSeoReport: !!seoReport,
      hasCompetitiveReport: !!competitiveReport,
      hasSocialAuditReport: !!socialAuditReport,
      hasCapabilities: !!locatedBusiness,
    });
  }, [isCentered, isDiscovering, isTyping, isProfileBuilding, locatedBusiness, report, seoReport, forecast, competitiveReport, socialAuditReport, capabilities]);

  // ─── Amethyst bento grid data ─────────────────────────────────────────
  const [activeSection, setActiveSection] = useState<ActiveSection>('overview');
  const [dismissedInsight, setDismissedInsight] = useState(false);

  const dashBusiness = useMemo(() => toBusiness(locatedBusiness, businessOverview), [locatedBusiness, businessOverview]);
  const dashboardData = useMemo(() => toDashboardData(businessOverview), [businessOverview]);
  const marginCardData = useMemo(() => toMarginCardData(report), [report]);
  const seoCardData = useMemo(() => toSeoCardData(seoReport), [seoReport]);
  const trafficCardData = useMemo(() => toTrafficCardData(forecast), [forecast]);

  const topInsight = !dismissedInsight ? (dashboardData?.topInsights?.[0] ?? null) : null;

  const isNationalCoverage = dashboardData?.isNational ?? false;

  // Profile completeness — drives the ProfileDiscoveryCard
  const profileStatus = useMemo(() => {
    const enriched = locatedBusiness as any;
    return {
      hasWebsite: !!(enriched?.officialUrl),
      hasMenu: !!(enriched?.menuUrl),
      hasSocial: !!(enriched?.socialLinks && Object.values(enriched.socialLinks).some((v: any) => v)),
      hasHours: !!(enriched?.hours || enriched?.operatingHours),
    };
  }, [locatedBusiness]);

  // Profile is "complete" if user ran the build flow OR has all 4 fields
  const [profileHasBeenBuilt, setProfileHasBeenBuilt] = useState(false);
  const profileDataComplete = profileStatus.hasWebsite && profileStatus.hasMenu && profileStatus.hasSocial && profileStatus.hasHours;
  const profileIncomplete = locatedBusiness && !profileHasBeenBuilt && !profileDataComplete;

  // Profile building chips — context-aware based on current step
  // Detect if business is food/restaurant to adapt labels
  const isRestaurant = useMemo(() => {
    const biz = locatedBusiness as any;
    const indicators = [biz?.businessType, biz?.category, biz?.persona, biz?.name].join(' ').toLowerCase();
    return /restaurant|food|pizza|burger|grill|cafe|bakery|donut|diner|bistro|kitchen|bbq|taco|sushi|bar & grill/i.test(indicators);
  }, [locatedBusiness]);
  const appLabel = isRestaurant ? 'Delivery apps' : 'Booking apps';

  const profileChips = useMemo(() => {
    if (!isProfileBuilding || !profileStep) return [];
    const finish = { label: '✅ Finish profile', value: 'done' };

    if (profileStep === 'menu') {
      return [
        { label: '🔗 My menu page', value: 'menu_link' },
        ...(isRestaurant ? [
          { label: '🍕 DoorDash', value: 'delivery:doordash' },
          { label: '🍔 Grubhub', value: 'delivery:grubhub' },
          { label: '🥡 UberEats', value: 'delivery:ubereats' },
          { label: '🍽️ Slice', value: 'delivery:slice' },
        ] : [
          { label: '📅 Booksy', value: 'booking:booksy' },
          { label: '💇 Vagaro', value: 'booking:vagaro' },
          { label: '📋 Square Appointments', value: 'booking:square' },
        ]),
        { label: '⏭️ Skip', value: 'skip' },
        finish,
      ];
    }
    if (profileStep === 'social') {
      return [
        { label: '📸 Instagram', value: 'social:instagram' },
        { label: '📘 Facebook', value: 'social:facebook' },
        { label: '⭐ Yelp', value: 'social:yelp' },
        { label: '📍 Google Business', value: 'social:google' },
        { label: '🎵 TikTok', value: 'social:tiktok' },
        { label: '⏭️ Skip', value: 'skip' },
        finish,
      ];
    }
    return [finish];
  }, [isProfileBuilding, profileStep, isRestaurant]);

  // ─── CENTERED (home screen) — original search experience, untouched ────
  if (isCentered) {
    return (
      <main className="flex flex-col md:flex-row h-screen w-screen overflow-hidden relative bg-[#f8f9ff]">
        <BlobBackground className="z-0 opacity-40" />
        <div className="absolute inset-0 z-10 opacity-40">
          <NeuralBackground />
        </div>

        <div className="fixed top-4 left-4 z-[100] animate-fade-in pointer-events-none">
          <HephaeLogo size="sm" variant="color" />
        </div>

        <div className="fixed top-4 right-4 z-[100] opacity-100 pointer-events-auto">
          {user ? (
            <div className="relative">
              <button
                onClick={() => setShowUserMenu((v) => !v)}
                className="flex items-center gap-1.5 bg-white/90 backdrop-blur-md px-2.5 py-1.5 rounded-full shadow-md border border-gray-200/80 hover:shadow-lg transition-all"
              >
                {user.photoURL ? (
                  <img src={user.photoURL} alt="" className="w-6 h-6 rounded-full" referrerPolicy="no-referrer" />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center">
                    <span className="text-[10px] font-bold text-indigo-600">{user.displayName?.[0] || user.email?.[0] || '?'}</span>
                  </div>
                )}
                <span className="text-xs font-medium text-gray-700 hidden md:block max-w-[100px] truncate">
                  {user.displayName || user.email?.split('@')[0]}
                </span>
              </button>
              {showUserMenu && (
                <>
                  <div className="fixed inset-0 z-[99]" onClick={() => setShowUserMenu(false)} />
                  <div className="absolute right-0 mt-1.5 w-44 bg-white rounded-xl shadow-xl border border-gray-200 py-1 z-[100]">
                    <div className="px-3 py-1.5 border-b border-gray-100">
                      <p className="text-xs font-medium text-gray-900 truncate">{user.displayName}</p>
                      <p className="text-[10px] text-gray-500 truncate">{user.email}</p>
                    </div>
                    <button
                      onClick={async () => { setShowUserMenu(false); await signOut(); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <LogOut className="w-3.5 h-3.5" /> Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 hidden sm:inline">Free weekly business monitoring</span>
              <button onClick={signInWithGoogle} className="px-3 py-1.5 rounded-full border border-gray-200/80 bg-white/90 backdrop-blur-md shadow-md hover:shadow-lg hover:bg-white transition-all text-xs font-medium text-gray-600">Sign in</button>
              <button onClick={signInWithGoogle} className="px-3 py-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 shadow-md hover:shadow-lg hover:from-indigo-400 hover:to-violet-500 transition-all text-xs font-medium text-white">Register</button>
            </div>
          )}
        </div>

        {/* Full-width chat when centered */}
        <div className="relative z-20 w-full max-w-none pointer-events-none h-full">
          <ChatInterface
            messages={messages}
            onSendMessage={sendMessage}
            onPlaceSelect={handlePlaceSelect}
            isTyping={isTyping}
            isDiscovering={isDiscovering}
            onReset={() => {
              setMessages([{ id: '1', role: 'model', text: 'Hi! I am Hephae.\nSearch for your business to get started.', createdAt: Date.now() }]);
              setLocatedBusiness(null); setReport(null); setForecast(null); setSeoReport(null); setCompetitiveReport(null); setSocialAuditReport(null); setProfileHasBeenBuilt(false);
              setCapabilities([]); setIsDiscovering(false); setProfileReportUrl(null); setMarginReportUrl(null); setTrafficReportUrl(null);
              setSeoReportUrl(null); setCompetitiveReportUrl(null); setMarketingReportUrl(null); setIsChatCollapsed(false); setAddMyAreaCity(null); setBusinessSlug(null);
              window.history.replaceState(null, '', '/');
            }}
            capabilities={capabilities}
            onSelectCapability={handleSelectCapability}
            capabilitiesLocked={!user && capabilities.length > 0}
            isCentered={true}
            followUpChips={dynamicChips}
            isCollapsed={false}
            onToggleCollapse={() => {}}
            addMyAreaCity={addMyAreaCity}
            onAddMyArea={submitUltralocalInterest}
            authUser={user}
            onSignIn={signInWithGoogle}
            onSignOut={signOut}
          />
        </div>

        <AuthWall
          isOpen={showAuthWall}
          onGoogleSignIn={async () => { await signInWithGoogle(); setShowAuthWall(false); setHasProvidedEmail(true); }}
          onEmailSubmit={async (email) => { await handleEmailSubmit(email); setShowAuthWall(false); }}
          onDismiss={() => setShowAuthWall(false)}
        />

      </main>
    );
  }

  // ─── AMETHYST 3-COLUMN LAYOUT — after a business is located ──────────
  return (
    <div className="min-h-screen bg-[#f8f9ff] text-slate-900 relative">
      {/* Signature neural background — subtle on the dashboard, non-interactive */}
      <div className="fixed inset-0 z-0 opacity-[0.12] pointer-events-none [&_canvas]:!pointer-events-none">
        <NeuralBackground />
      </div>

      <TopNav
        business={dashBusiness}
        user={user}
        onSignIn={signInWithGoogle}
        onSignOut={signOut}
        onRunAnalysis={() => {
          if (!locatedBusiness) return;
          if (!user) { setShowAuthWall(true); return; }
          const next = !report ? 'surgery' : !seoReport ? 'seo' : !forecast ? 'traffic' : !competitiveReport ? 'competitive' : null;
          if (next) handleSelectCapability(next);
        }}
        nextAnalysisLabel={
          !report ? 'Margin Analysis' : !seoReport ? 'SEO Audit' : !forecast ? 'Traffic Forecast' : !competitiveReport ? 'Competitive Intel' : null
        }
      />
      <LeftSidebar
        active={activeSection}
        onSelect={setActiveSection}
        onSearch={(q) => sendMessage(q)}
        showNominateZip={isNationalCoverage}
        onNominateZip={() => submitUltralocalInterest()}
        isLoggedIn={!!user}
        availableReports={{
          margin: !!report,
          seo: !!seoReport,
          traffic: !!forecast,
          competitive: !!competitiveReport,
        }}
        capabilityReady={{
          seo: !!(locatedBusiness as any)?.officialUrl,
          margin: !!((locatedBusiness as any)?.officialUrl || (locatedBusiness as any)?.menuUrl),
          traffic: !!locatedBusiness, // just needs the business location
          competitive: !!(locatedBusiness?.address || businessOverview?.dashboard?.competitors?.length),
        }}
      />

      {/* RIGHT CHATBOT RAIL */}
      <aside className="fixed right-0 top-16 h-[calc(100vh-64px)] w-[420px] z-40 border-l border-purple-100/60 flex flex-col">
        <ChatInterface
          messages={messages}
          onSendMessage={sendMessage}
          onPlaceSelect={handlePlaceSelect}
          isTyping={isTyping}
          isDiscovering={isDiscovering}
          onReset={() => {
            setMessages([{ id: '1', role: 'model', text: 'Hi! I am Hephae.\nSearch for your business to get started.', createdAt: Date.now() }]);
            setLocatedBusiness(null); setReport(null); setForecast(null); setSeoReport(null); setCompetitiveReport(null); setSocialAuditReport(null); setProfileHasBeenBuilt(false);
            setCapabilities([]); setIsDiscovering(false); setProfileReportUrl(null); setMarginReportUrl(null); setTrafficReportUrl(null);
            setSeoReportUrl(null); setCompetitiveReportUrl(null); setMarketingReportUrl(null); setIsChatCollapsed(false); setAddMyAreaCity(null); setBusinessSlug(null);
            window.history.replaceState(null, '', '/');
          }}
          capabilities={capabilities}
          onSelectCapability={handleSelectCapability}
          capabilitiesLocked={!user && capabilities.length > 0}
          isCentered={false}
          followUpChips={dynamicChips}
          isCollapsed={false}
          onToggleCollapse={() => {}}
          addMyAreaCity={addMyAreaCity}
          onAddMyArea={submitUltralocalInterest}
          authUser={user}
          onSignIn={signInWithGoogle}
          onSignOut={signOut}
          lightMode
          profileBuildingMode={isProfileBuilding}
          profileChips={profileChips}
        />
      </aside>

      {/* MAIN CONTENT AREA — bento grid (overview) or full report view */}
      <main className="ml-56 mr-[420px] pt-24 pb-28 px-8 min-h-screen relative z-10">

        {/* ── Report views OR empty capability pages ───────────────────── */}
        {activeSection !== 'overview' ? (
          <div className="animate-fade-in">
            <div className="flex items-center gap-3 mb-6">
              <button onClick={() => setActiveSection('overview')} className="text-xs text-purple-600 hover:text-purple-800 font-semibold flex items-center gap-1">
                ← Back to Overview
              </button>
              <span className="text-xs text-slate-300">|</span>
              <span className="text-xs font-bold text-slate-700 uppercase tracking-widest">
                {activeSection === 'seo' ? 'SEO Health' : activeSection === 'margin' ? 'Margin Analysis' : activeSection === 'traffic' ? 'Foot Traffic' : activeSection === 'competitive' ? 'Competitive Intel' : activeSection === 'local-intel' ? 'Local Intelligence' : activeSection}
              </span>
            </div>

            {/* Local Intel page */}
            {activeSection === 'local-intel' ? (
              <LocalIntelPage
                dashboard={dashboardData}
                businessName={locatedBusiness?.name}
                zipCode={(locatedBusiness as any)?.zipCode}
                businessSlug={businessSlug ?? undefined}
                vertical={(locatedBusiness as any)?.businessType}
              />
            ) : activeSection === 'seo' && seoReport ? (
              <ResultsDashboard report={seoReport} groundingChunks={(seoReport as any).groundingChunks || []} />
            ) : activeSection === 'margin' && report ? (
              renderSurgeonReportContent()
            ) : activeSection === 'traffic' && forecast ? (
              renderTrafficForecastContent()
            ) : activeSection === 'competitive' && competitiveReport ? (
              renderCompetitiveReportContent()
            ) : activeCapability ? (
              /* Currently running */
              <RunningAnalysisCard capabilityId={activeCapability} startTime={capabilityStartTime} />
            ) : (
              /* Empty state — invite user to run the analysis */
              <div className="flex flex-col items-center justify-center py-20 gap-6">
                <div className="w-20 h-20 rounded-2xl bg-purple-50 flex items-center justify-center">
                  {activeSection === 'seo' ? <Globe className="w-8 h-8 text-purple-400" /> :
                   activeSection === 'margin' ? <DollarSign className="w-8 h-8 text-purple-400" /> :
                   activeSection === 'traffic' ? <TrendingUp className="w-8 h-8 text-purple-400" /> :
                   <Flame className="w-8 h-8 text-purple-400" />}
                </div>
                <div className="text-center max-w-md">
                  <h2 className="text-2xl font-black text-slate-900">
                    {activeSection === 'seo' ? 'SEO Health Check' :
                     activeSection === 'margin' ? 'Margin Analysis' :
                     activeSection === 'traffic' ? 'Foot Traffic Forecast' :
                     'Competitive Intelligence'}
                  </h2>
                  <p className="text-sm text-slate-500 mt-2 leading-relaxed">
                    {activeSection === 'seo' ? 'Audit your Google presence — search rankings, website speed, schema markup, and mobile optimization.' :
                     activeSection === 'margin' ? 'Analyze your menu prices against commodity costs and local competitors to find profit leakage.' :
                     activeSection === 'traffic' ? 'Predict foot traffic patterns using local events, weather forecasts, and historical data.' :
                     'See how you stack up against nearby competitors — pricing, ratings, strengths, and vulnerabilities.'}
                  </p>
                </div>
                <button
                  onClick={() => {
                    const capMap: Record<string, string> = { seo: 'seo', margin: 'surgery', traffic: 'traffic', competitive: 'competitive' };
                    handleSelectCapability(capMap[activeSection] || activeSection);
                  }}
                  disabled={!!activeCapability}
                  className="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 disabled:opacity-50 disabled:cursor-not-allowed text-white px-8 py-3 rounded-xl text-sm font-bold shadow-lg shadow-purple-900/20 transition-all hover:scale-[1.02] active:scale-95"
                >
                  <Sparkles className="w-4 h-4" />
                  {activeCapability ? 'Analysis running...' : `Run ${activeSection === 'seo' ? 'SEO Audit' : activeSection === 'margin' ? 'Margin Analysis' : activeSection === 'traffic' ? 'Traffic Forecast' : 'Competitive Analysis'}`}
                </button>
                <p className="text-[10px] text-slate-400">{activeCapability ? 'Wait for the current analysis to finish' : 'Takes 30–60 seconds · Results appear here'}</p>
              </div>
            )}
          </div>
        ) : (
        /* ── Overview (bento grid) ─────────────────────────────── */
        <>
        <header className="mb-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-purple-700">Business Intelligence</p>
          <h1 className="text-4xl font-black tracking-tighter text-slate-900 mt-1">{dashBusiness?.name ?? 'Dashboard'}</h1>
          {dashBusiness?.persona && <p className="text-slate-500 text-sm mt-1">{dashBusiness.persona}</p>}

          {isNationalCoverage && (
            <div className="mt-4 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm">
              <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
              </div>
              <div className="flex-1">
                <span className="font-bold text-amber-800">Zip not monitored</span>
                <span className="text-amber-600 ml-2">— showing national benchmarks. Run on-demand analyses, or </span>
                <button onClick={() => submitUltralocalInterest()} className="font-bold text-amber-800 underline underline-offset-2 hover:text-amber-900">nominate this zip</button>
                <span className="text-amber-600"> for weekly coverage.</span>
              </div>
            </div>
          )}

          {!user && (
            <div className="mt-4 flex items-center gap-3 bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 text-sm">
              <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center flex-shrink-0">
                <LogIn className="w-4 h-4 text-purple-600" />
              </div>
              <div className="flex-1">
                <span className="font-bold text-purple-800">Sign in to unlock analyses</span>
                <span className="text-purple-600 ml-2">— Margin, SEO, Foot Traffic, and Competitive reports require a free account.</span>
              </div>
              <button onClick={signInWithGoogle} className="flex items-center gap-1.5 bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-bold hover:bg-purple-800 transition-colors flex-shrink-0">
                <LogIn className="w-3.5 h-3.5" /> Sign in
              </button>
            </div>
          )}
        </header>

        <div className="grid grid-cols-12 gap-6 items-start">
          <div className="col-span-12 md:col-span-5" style={{ minHeight: 280 }}><MapCard business={dashBusiness} /></div>
          <div className="col-span-12 md:col-span-7" style={{ minHeight: 280 }}>
            <WeeklyPulseCard dashboard={dashboardData} onNominateZip={isNationalCoverage ? () => submitUltralocalInterest() : undefined} />
          </div>

          <div className="col-span-12"><MarketPositionCard dashboard={dashboardData} onNominateZip={isNationalCoverage ? () => submitUltralocalInterest() : undefined} /></div>

          {/* Profile card — invitation, building progress, or saved profile summary */}
          <div className="col-span-12 md:col-span-6">
            <ProfileDiscoveryCard
              status={profileStatus}
              profileData={{
                officialUrl: (locatedBusiness as any)?.officialUrl,
                menuUrl: (locatedBusiness as any)?.menuUrl,
                socialLinks: (locatedBusiness as any)?.socialLinks,
                deliveryLinks: (locatedBusiness as any)?.deliveryLinks,
              }}
              isBuilding={isProfileBuilding}
              isBuilt={profileHasBeenBuilt || profileDataComplete}
              onStartBuild={startProfileBuilding}
              onSignIn={signInWithGoogle}
              onEditProfile={() => {
                setProfileHasBeenBuilt(false); // re-show the build invitation
                startProfileBuilding();
              }}
              isSignedIn={!!user}
            />
          </div>

          <div className="col-span-12 md:col-span-6"><AiToolsCard tools={dashboardData?.aiTools} personalizedTools={dashboardData?.personalizedTools} businessSlug={businessSlug ?? undefined} zipCode={(locatedBusiness as any)?.zipCode} vertical={(locatedBusiness as any)?.businessType} /></div>

          <div className="col-span-12 md:col-span-4"><WeekCalendarCard events={dashboardData?.events} /></div>
          <div className="col-span-12 md:col-span-8">
            <BuzzCard buzz={dashboardData?.communityBuzz} insights={dashboardData?.topInsights} />
          </div>

          {/* Nearby rivals — compact inline strip */}
          {dashboardData?.competitors?.length ? (
            <div className="col-span-12">
              <CompetitorsStrip competitors={dashboardData.competitors} />
            </div>
          ) : null}

          {/* Research snippets — industry insights */}
          {dashboardData?.researchSnippets?.keyFindings?.length ? (
            <div className="col-span-12">
              <Card className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <BarChart3 className="w-4 h-4 text-indigo-400" />
                  <Label>Industry Research</Label>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {dashboardData.researchSnippets.keyFindings.slice(0, 3).map((finding, i) => (
                    <div key={i} className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-3">
                      <p className="text-xs text-slate-700 leading-relaxed">{typeof finding === 'string' ? finding.slice(0, 150) : ''}{typeof finding === 'string' && finding.length > 150 ? '...' : ''}</p>
                    </div>
                  ))}
                </div>
                {dashboardData.researchSnippets.recommendedReading?.length ? (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {dashboardData.researchSnippets.recommendedReading.slice(0, 3).map((r, i) => (
                      <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                        className="text-[10px] font-medium px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-600 hover:bg-indigo-100 transition-colors">
                        {r.title.slice(0, 35)}{r.title.length > 35 ? '...' : ''}
                      </a>
                    ))}
                  </div>
                ) : null}
              </Card>
            </div>
          ) : null}

          {!user && (
            <div className="col-span-12 flex items-center gap-4 py-2">
              <div className="flex-1 h-px bg-slate-200" />
              <div className="flex items-center gap-2 bg-purple-50 border border-purple-100 rounded-full px-4 py-1.5 flex-shrink-0">
                <Lock className="w-3 h-3 text-purple-500" />
                <span className="text-xs font-semibold text-purple-600">Sign in to unlock these analyses</span>
              </div>
              <div className="flex-1 h-px bg-slate-200" />
            </div>
          )}

          <div className="col-span-12 md:col-span-6 flex flex-col">
            {activeCapability === 'surgery' ? (
              <RunningAnalysisCard capabilityId="surgery" startTime={capabilityStartTime} />
            ) : !user ? (
              <LockedAnalysisCard title="Margin Analysis" subtitle="Sign in to see your full food cost breakdown and profit leakage" onSignIn={signInWithGoogle}>
                <MarginCard margin={marginCardData} />
              </LockedAnalysisCard>
            ) : (
              <MarginCard margin={marginCardData} onRun={() => handleSelectCapability('surgery')} onExpand={report ? () => setActiveSection('margin') : undefined} />
            )}
          </div>
          <div className="col-span-12 md:col-span-6 flex flex-col">
            {activeCapability === 'seo' ? (
              <RunningAnalysisCard capabilityId="seo" startTime={capabilityStartTime} />
            ) : !user ? (
              <LockedAnalysisCard title="SEO Health" subtitle="Sign in to audit your Google presence score" onSignIn={signInWithGoogle}>
                <SeoCard seo={seoCardData} />
              </LockedAnalysisCard>
            ) : (
              <SeoCard seo={seoCardData} onRun={() => handleSelectCapability('seo')} onExpand={seoReport ? () => setActiveSection('seo') : undefined} />
            )}
          </div>

          {/* Traffic + Competitive — show when data available OR when running */}
          {(trafficCardData || activeCapability === 'traffic') && (
            <div className="col-span-12 md:col-span-8 flex flex-col">
              {activeCapability === 'traffic' ? (
                <RunningAnalysisCard capabilityId="traffic" startTime={capabilityStartTime} />
              ) : trafficCardData ? (
                <FootTrafficCard traffic={trafficCardData} onExpand={() => setActiveSection('traffic')} />
              ) : null}
            </div>
          )}
          {(trafficCardData || activeCapability === 'competitive') && (
            <div className="col-span-12 md:col-span-4 flex flex-col">
              {activeCapability === 'competitive' ? (
                <RunningAnalysisCard capabilityId="competitive" startTime={capabilityStartTime} />
              ) : competitiveReport ? (
                <Card className="p-6 border-l-4 border-orange-500 h-full flex flex-col">
                  <Label>Competitive Intel</Label>
                  <h3 className="text-lg font-bold tracking-tight text-slate-900 mt-1">Market Position</h3>
                  <p className="text-xs text-slate-500 mt-2 leading-relaxed">{competitiveReport.market_summary}</p>
                  <p className="text-[10px] font-bold text-orange-600 mt-3">{competitiveReport.competitors?.length ?? 0} competitors analyzed</p>
                </Card>
              ) : (
                <LockedAnalysisCard title="Competitive Intel" subtitle="Run the competitive report to see how you rank vs nearby rivals" onSignIn={signInWithGoogle}>
                  <BuzzCard buzz={dashboardData?.communityBuzz} insights={dashboardData?.topInsights} />
                </LockedAnalysisCard>
              )}
            </div>
          )}
        </div>
        </>
        )}
      </main>

      <IntelligenceBanner
        insight={topInsight}
        onApply={() => { if (topInsight) sendMessage(topInsight.recommendation); }}
        onDismiss={() => setDismissedInsight(true)}
      />

      {/* Floating action buttons — Schedule Call, Share Report, Weekly Pulse */}
      {locatedBusiness && (
        <div className="fixed bottom-6 left-56 z-30 flex items-center gap-2 px-4">
          <a
            href="https://hephae.co/schedule"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-lg transition-all"
          >
            <Calendar className="w-3.5 h-3.5" /> Schedule Call
          </a>
          {activeReportUrl && (
            <button
              onClick={() => setShowSharePanel(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-lg transition-all"
            >
              <Share2 className="w-3.5 h-3.5" /> Share Report
            </button>
          )}
          {businessSlug && (
            <button
              onClick={() => {
                navigator.clipboard.writeText(window.location.origin + '/b/' + businessSlug);
                setCopyToast(true);
                setTimeout(() => setCopyToast(false), 2000);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold text-white bg-slate-700 hover:bg-slate-600 shadow-lg transition-all"
            >
              <Share2 className="w-3.5 h-3.5" /> Copy Link
            </button>
          )}
          {user && !activeHeartbeatId && (
            <button
              onClick={() => setShowHeartbeatSetup(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-lg transition-all"
            >
              <Activity className="w-3.5 h-3.5" /> Weekly Pulse
            </button>
          )}
          {activeHeartbeatId && (
            <HeartbeatBadge onClick={() => setShowHeartbeatSetup(true)} />
          )}
        </div>
      )}

      {copyToast && (
        <div className="fixed bottom-28 left-1/2 -translate-x-1/2 z-[60] bg-gray-900 text-white text-xs font-semibold px-4 py-2 rounded-full shadow-xl border border-white/10 animate-fade-in-up pointer-events-none">
          Link copied!
        </div>
      )}

      <AuthWall
        isOpen={showAuthWall}
        onGoogleSignIn={async () => {
          await signInWithGoogle();
          setShowAuthWall(false);
          setHasProvidedEmail(true);
          // Profile building now happens via ProfileDiscoveryCard — user clicks "Build my profile"
        }}
        onEmailSubmit={async (email) => {
          await handleEmailSubmit(email);
          setShowAuthWall(false);
        }}
        onDismiss={() => setShowAuthWall(false)}
      />

      {user && locatedBusiness && (
        <HeartbeatSetup
          isOpen={showHeartbeatSetup}
          onClose={() => setShowHeartbeatSetup(false)}
          businessName={locatedBusiness.name}
          businessSlug={(locatedBusiness as any).slug || locatedBusiness.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}
          userEmail={user.email || ''}
          onCreated={(id) => {
            setActiveHeartbeatId(id);
            setMessages(prev => [...prev, msg('model', `Heartbeat activated for **${locatedBusiness!.name}**! You'll receive a weekly email digest every ${['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][1]} with changes to your monitored capabilities.`)]);
          }}
        />
      )}

      {/* Social Share Panel */}
      {showSharePanel && activeReportUrl && (
        <SocialSharePanel
          reportUrl={activeReportUrl}
          reportType={getActiveReportType()}
          businessName={locatedBusiness?.name || ''}
          summary={getActiveSummary()}
          headline={getActiveHeadline()}
          subtitle={getActiveSubtitle()}
          highlight={getActiveHighlight()}
          socialHandles={{
            instagram: (locatedBusiness as any)?.socialLinks?.instagram,
            facebook: (locatedBusiness as any)?.socialLinks?.facebook,
            twitter: (locatedBusiness as any)?.socialLinks?.twitter,
          }}
          reportUrls={{
            ...(marginReportUrl ? { margin: marginReportUrl } : {}),
            ...(seoReportUrl ? { seo: seoReportUrl } : {}),
            ...(trafficReportUrl ? { traffic: trafficReportUrl } : {}),
            ...(competitiveReportUrl ? { competitive: competitiveReportUrl } : {}),
            ...(marketingReportUrl ? { marketing: marketingReportUrl } : {}),
          }}
          onClose={() => setShowSharePanel(false)}
        />
      )}

      {/* Full-screen loading overlay ONLY for initial discovery — capability runs use inline indicators */}
      {isDiscovering && (
        <div className="fixed inset-0 z-[55] bg-white/95 backdrop-blur-sm animate-fade-in">
          <LoadingOverlay
            capabilityId={activeCapability}
            startTime={capabilityStartTime}
            businessName={locatedBusiness?.name}
            businessLogo={(locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon}
          />
        </div>
      )}

    </div>
  );
}
