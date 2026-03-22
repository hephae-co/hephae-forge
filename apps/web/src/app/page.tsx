'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { Search as SearchIcon, MapPin, Building2, Store, Loader2, ArrowRight, Activity, Percent, DollarSign, TrendingUp, AlertTriangle, Scale, Target, Swords, X, Download, BarChart3, Users, Search, Share2, Zap, Shield, Eye, MessageCircle, Map, Sparkles, Calendar, LogIn, LogOut } from 'lucide-react';
import { SurgicalReport } from '@/types/api';
import { SuggestionChip } from '@/components/Chatbot/types';
import { computeSuggestionChips, ACTION_CHIP_MAP } from '@/lib/suggestionChips';
import clsx from 'clsx';
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

export default function Home() {
  const { user, signInWithGoogle, signOut } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { apiFetch } = useApiClient();
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
        let errMsg = "Analysis Failed";
        try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
        throw new Error(errMsg);
      }

      const data = await res.json();
      if (data.menuNotFound) {
        setMessages(prev => [...prev, msg('model', "I still couldn't extract menu items from that URL. Make sure it's a direct link to the menu page with prices listed.")]);
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
    // Intercept: if in profile building mode, route to profile builder
    if (isProfileBuilding) {
      setMessages(prev => [...prev, msg('user', text)]);
      sendProfileMessage(text);
      return;
    }

    // Intercept: if we're waiting for a menu URL from the user, retry surgery
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
            seoReport: seoReport ? { overallScore: seoReport.overallScore, sections: seoReport.sections?.map((s: any) => ({ name: s.name, score: s.score, recommendations: s.recommendations })), summary: seoReport.summary } : undefined,
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

  const startProfileBuilding = () => {
    setIsProfileBuilding(true);
    setProfileSessionId(null);
    setMessages(prev => [...prev, msg('model', "Great, you're signed in! Let me set up your business profile so I can run the right analyses for you.")]);
    // Send initial message to profile builder
    sendProfileMessage("Let's get started setting up my profile.");
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

      if (!res.ok) throw new Error("Profile builder request failed");
      const data = await res.json();

      if (data.sessionId && data.sessionId !== profileSessionId) {
        setProfileSessionId(data.sessionId);
      }

      setMessages(prev => [...prev, msg('model', data.text)]);

      // Profile building complete — save and run capabilities
      if (data.profileComplete) {
        setIsProfileBuilding(false);
        const selectedCaps = data.selectedCapabilities || [];

        // Update locatedBusiness with profile data
        if (data.profile) {
          setLocatedBusiness(prev => prev ? { ...prev, ...data.profile } : prev);
        }

        // Auto-run selected capabilities
        for (const capId of selectedCaps) {
          // Normalize capability IDs
          const normalizedId = capId === 'margin' ? 'surgery' : capId === 'social' ? 'marketing' : capId;
          executeCapability(normalizedId);
        }
      }
    } catch (e: any) {
      console.error("Profile building failed", e);
      setMessages(prev => [...prev, msg('model', "Something went wrong. Let me try again.")]);
    } finally {
      setIsTyping(false);
    }
  };

  const triggerBusinessOverview = async (identity: BaseIdentity) => {
    setIsDiscovering(true);
    setActiveCapability("discovery");
    setCapabilityStartTime(Date.now());

    try {
      const res = await apiFetch('/api/overview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity })
      });

      if (res.ok) {
        const overview = await res.json();
        setBusinessOverview(overview);

        // Build conversational insight message with real numbers
        const parts: string[] = [];
        const snap = overview.businessSnapshot;
        const market = overview.marketPosition;
        const econ = overview.localEconomy;
        const buzz = overview.localBuzz;

        if (snap) {
          let intro = `Here's what I found about **${snap.name}**`;
          if (snap.rating) intro += ` — rated **${snap.rating}★**${snap.reviewCount ? ` (${snap.reviewCount} reviews)` : ''}`;
          intro += '.';
          parts.push(intro);
        }

        if (market) {
          parts.push(`There are **${market.competitorCount} competitors** nearby (${market.saturationLevel} saturation). ${market.ranking || ''}`);
        }

        if (econ) {
          const econParts = [];
          if (econ.medianIncome) econParts.push(`**${econ.medianIncome}** median income`);
          if (econ.population) econParts.push(`**${econ.population}** residents`);
          if (econParts.length) parts.push(`Your market: ${econParts.join(', ')}. ${econ.keyFact || ''}`);
        }

        if (buzz?.headline) {
          parts.push(`📡 **This week**: ${buzz.headline}`);
        }

        if (overview.keyOpportunities?.length) {
          const opps = overview.keyOpportunities.slice(0, 2).map((o: any) => `• **${o.title}** — ${o.detail}`).join('\n');
          parts.push(`**Opportunities I spotted:**\n${opps}`);
        }

        parts.push('What would you like to dig into? I can analyze your pricing, check your Google presence, or compare you against competitors.');

        setMessages(prev => [...prev, msg('model', parts.join('\n\n'))]);
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

  // Fast-track location from Places Autocomplete — validates zipcode, then runs overview
  const handlePlaceSelect = async (identity: BaseIdentity) => {
    // Add user message immediately
    setMessages(prev => [...prev, msg('user', identity.name)]);

    // --- Zipcode validation gate ---
    const zipCode = (identity as any).zipCode;
    if (zipCode) {
      try {
        const valRes = await apiFetch(`/api/places/validate-zipcode?zipCode=${zipCode}`);
        if (valRes.ok) {
          const valData = await valRes.json();
          if (!valData.supported) {
            // Unsupported zipcode — register interest
            setMessages(prev => [
              ...prev,
              msg('model', `We don't cover zipcode **${zipCode}** yet. Leave your email and we'll notify you when we expand there!`),
            ]);
            // Track unsupported zipcode interest
            try {
              await apiFetch('/api/track', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: identity.name, unsupportedZipcode: true, zipCode }),
              });
            } catch (e) { console.error("Interest tracking failed", e); }
            // Show email capture wall for notification
            setShowAuthWall(true);
            return; // Do not proceed with overview
          }
        }
      } catch (e) {
        console.error("Zipcode validation failed, proceeding anyway", e);
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

    // Zipcode supported — proceed with overview
    setMessages(prev => [
      ...prev,
      msg('model', `Found **${identity.name}** at ${identity.address}! Analyzing your market...`),
    ]);

    // Reset and set located business
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

    // Trigger lightweight overview (replaces heavy discovery)
    triggerBusinessOverview(identity);
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

  const executeCapability = async (capId: string) => {
    if (!locatedBusiness) return;

    // Clear all previous reports so the loading overlay shows cleanly
    // and the new report renders correctly (no ternary priority conflict).
    setReport(null);
    setForecast(null);
    setSeoReport(null);
    setCompetitiveReport(null);
    setSelectedDay(null);
    setSelectedSlot(null);

    // Track which capability is running for the loading experience
    setActiveCapability(capId);
    setCapabilityStartTime(Date.now());

    // Strip large binary fields before sending to capability APIs.
    // menuScreenshotBase64 can be 2-5 MB as base64, which exceeds Next.js's
    // default request body size limit and causes a 422 response.
    const { menuScreenshotBase64: _stripped, ...identityForApi } = locatedBusiness as any;

    if (capId === 'surgery') {
      setMessages(prev => [...prev, msg('model', "Checking your menu prices against commodity costs and local competitors... ⏱️")]);
      setIsTyping(true);

      try {
        // Pass the enriched profile (without base64) so /api/analyze can skip the Crawler
        const payload = {
          url: locatedBusiness.officialUrl,
          enrichedProfile: identityForApi,
          advancedMode: false
        };
        const res = await apiFetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          let errMsg = "Analysis Failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
          throw new Error(errMsg);
        }

        const data = await res.json();

        // P2b: Handle menuNotFound — ask user for a menu URL
        if (data.menuNotFound) {
          setAwaitingMenuUrl(true);
          setMessages(prev => [...prev, msg('model', "I couldn't find a menu online for this business. Paste a link to the menu (website page, PDF, or delivery platform like DoorDash/Grubhub) and I'll analyze it.")]);
          return;
        }

        setReport(data);
        if (data.reportUrl) {
          setMarginReportUrl(data.reportUrl);
          const totalLeakage = data.menu_items?.reduce((s: number, i: { price_leakage: number }) => s + i.price_leakage, 0) || 0;
          sendReportEmailAsync('margin', data.reportUrl, locatedBusiness!.name, `$${totalLeakage.toFixed(2)} total profit leakage detected across ${data.menu_items?.length || 0} menu items. Overall score: ${data.overall_score}/100.`);
        }
        setMessages(prev => [...prev, msg('model', "Price analysis complete! Your optimization dashboard is ready.\n\n[Schedule a call](https://hephae.co/schedule) to discuss your pricing strategy with our team.")]);
        maybeShowAuthWall();

      } catch (e: any) {
        setMessages(prev => [...prev, msg('model', `Price analysis couldn't complete: ${e.message}\n\nThis can happen if the business website doesn't have a public menu page. Try one of the other analyses instead!`)]);
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
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setForecast(data);
        if (data.reportUrl) {
          setTrafficReportUrl(data.reportUrl);
          sendReportEmailAsync('traffic', data.reportUrl, locatedBusiness!.name, data.summary || 'Your 3-day foot traffic forecast is ready.');
        }

        if (data.forecast?.length) {
          const firstDay = data.forecast[0];
          setSelectedDay(firstDay);
          setSelectedSlot(firstDay.slots.find((s: any) => s.score > 70) || firstDay.slots[0]);
        }

        setMessages(prev => [...prev, msg('model', `Forecast complete!\n\n**Executive Summary**:\n${data.summary}\n\n[Schedule a call](https://hephae.co/schedule) to plan your staffing strategy with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        setMessages(prev => [...prev, msg('model', `Failed to execute Foot Traffic Forecast: ${e.message}`)]);
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
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
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
          if (data.reportUrl) {
            setSeoReportUrl(data.reportUrl);
            sendReportEmailAsync('seo', data.reportUrl, locatedBusiness!.name, `SEO score: ${data.overallScore ?? 'N/A'}/100. ${sectionCount} categories analyzed. ${data.summary || ''}`);
          }
          setMessages(prev => [...prev, msg('model', `SEO Audit complete! Verified ${sectionCount} critical infrastructure categories.\n\n[Schedule a call](https://hephae.co/schedule) to improve your search rankings with our team.`)]);
          maybeShowAuthWall();
        }

      } catch (e: any) {
        setMessages(prev => [...prev, msg('model', `Google presence check failed: ${e.message}`)]);
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
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setSocialAuditReport(data);
        if (data.reportUrl) {
          setMarketingReportUrl(data.reportUrl);
          sendReportEmailAsync('marketing', data.reportUrl, locatedBusiness!.name, data.summary || 'Your social media audit is ready.');
        }

        const platformCount = data.platforms?.length || 0;
        setMessages(prev => [...prev, msg('model', `**Social media check** for **${locatedBusiness.name}** is complete! Score: **${data.overall_score ?? 'N/A'}/100** across ${platformCount} platform${platformCount !== 1 ? 's' : ''}.${data.summary ? `\n\n${data.summary}` : ''}\n\n[Schedule a call](https://hephae.co/schedule) to build your social strategy with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        setMessages(prev => [...prev, msg('model', `Social media check failed: ${e.message}`)]);
      } finally {
        setIsTyping(false);
        setActiveCapability(null);
        setCapabilityStartTime(null);
      }
    } else if (capId === 'competitive') {
      setMessages(prev => [...prev, msg('model', "Analyzing how you stack up against your closest local competitors... ⏱️")]);
      setIsTyping(true);

      try {
        const res = await apiFetch('/api/capabilities/competitive', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: identityForApi }),
        });

        if (!res.ok) {
          let errMsg = "Analysis Failed";
          try { const err = await res.json(); errMsg = err.error || errMsg; } catch { errMsg = `Server error (${res.status})`; }
          throw new Error(errMsg);
        }

        const data = await res.json();
        setCompetitiveReport(data);
        if (data.reportUrl) {
          setCompetitiveReportUrl(data.reportUrl);
          sendReportEmailAsync('competitive', data.reportUrl, locatedBusiness!.name, data.market_summary || 'Your competitive strategy report is ready.');
        }
        setMessages(prev => [...prev, msg('model', `Competitive Strategy complete! ${data.market_summary}\n\n[Schedule a call](https://hephae.co/schedule) to discuss your competitive positioning with our team.`)]);
        maybeShowAuthWall();

      } catch (e: any) {
        setMessages(prev => [...prev, msg('model', `Competitive analysis failed: ${e.message}`)]);
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
    const { identity, menu_items, strategic_advice, overall_score } = report;
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
  const dynamicChips = useMemo((): SuggestionChip[] => {
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
      hasCapabilities: capabilities.length > 0,
    });
  }, [isCentered, isDiscovering, isTyping, locatedBusiness, report, seoReport, forecast, competitiveReport, socialAuditReport, capabilities]);

  return (
    <main className={`flex flex-col md:flex-row h-screen w-screen overflow-hidden relative transition-colors duration-700 ${isCentered ? 'bg-white' : 'bg-gray-50'}`}>

      {/* BACKGROUND ANIMATION — blob at z-0 (decorative), neural canvas at z-10 (interactive) */}
      {isCentered && (
        <>
          <BlobBackground className="z-0 opacity-70" />
          <div className="absolute inset-0 z-10 opacity-70">
            <NeuralBackground />
          </div>
        </>
      )}

      {/* Search animation moved into ChatInterface to avoid overlapping the chat panel */}

      {/* Global Hephae logo — visible on home screen and during panel transition */}
      {(isCentered || (!report && !forecast && !seoReport && !competitiveReport && !socialAuditReport && !isDiscovering && !isTyping)) && (
        <div className="fixed top-4 left-4 z-[100] animate-fade-in pointer-events-none">
          <HephaeLogo size="sm" variant="color" />
        </div>
      )}

      {/* Auth buttons — only on home screen (centered), hidden when chat panel is active */}
      {isCentered && (
        <div className="fixed top-4 right-4 z-[100] animate-fade-in">
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
                      onClick={async () => {
                        setShowUserMenu(false);
                        await signOut();
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                      Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 hidden sm:inline">
                Free weekly business monitoring
              </span>
              <button
                onClick={signInWithGoogle}
                className="px-3 py-1.5 rounded-full border border-gray-200/80 bg-white/90 backdrop-blur-md shadow-md hover:shadow-lg hover:bg-white transition-all text-xs font-medium text-gray-600"
              >
                Sign in
              </button>
              <button
                onClick={signInWithGoogle}
                className="px-3 py-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 shadow-md hover:shadow-lg hover:from-indigo-400 hover:to-violet-500 transition-all text-xs font-medium text-white"
              >
                Register
              </button>
            </div>
          )}
        </div>
      )}

      {/* LEFT VISUALIZER PANEL - Hidden when centered, fills remaining space when active */}
      <div className={`relative z-10 transition-all duration-500 ease-in-out flex-col ${isCentered ? 'w-0 opacity-0 overflow-hidden hidden md:flex' : isChatCollapsed ? 'md:w-[calc(100%-56px)] w-full opacity-100' : `md:w-[55%] w-full opacity-100 ${mobilePanel === 'chat' ? 'hidden md:flex' : 'flex'}`} ${!isCentered ? 'h-full' : ''}`}>
        {!isCentered && (
          <>
            {(isTyping || isDiscovering) && <BlobBackground className="z-0 opacity-30" />}
            {/* Copy-link toast */}
            {copyToast && (
              <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-[60] bg-gray-900 text-white text-xs font-semibold px-4 py-2 rounded-full shadow-xl border border-white/10 animate-fade-in-up pointer-events-none">
                Link copied!
              </div>
            )}

            {!isDiscovering && !isTyping && (
              <div className="absolute bottom-6 left-4 right-4 z-50 animate-fade-in-up pointer-events-auto flex flex-col items-center gap-2">
                {/* Capability icons — compact grid */}
                <div className="flex items-center gap-1 bg-white/90 backdrop-blur-md px-2 py-1.5 rounded-2xl shadow-lg border border-gray-200/80">
                  {[
                    ...(locatedBusiness && ((locatedBusiness as any).menuUrl || (locatedBusiness as any).menuScreenshotUrl)
                      ? [{ id: "surgery", icon: BarChart3, label: "Optimize Prices", color: "text-indigo-500", hoverBg: "hover:bg-indigo-50" }]
                      : []),
                    { id: "traffic", icon: Users, label: "Foot Traffic", color: "text-emerald-500", hoverBg: "hover:bg-emerald-50" },
                    { id: "seo", icon: SearchIcon, label: "Find Me Online", color: "text-purple-500", hoverBg: "hover:bg-purple-50" },
                    { id: "competitive", icon: Swords, label: "Competitors", color: "text-orange-500", hoverBg: "hover:bg-orange-50" },
                    { id: "marketing", icon: Share2, label: "Social Media", color: "text-pink-500", hoverBg: "hover:bg-pink-50" },
                  ].map((cap) => {
                    const Icon = cap.icon;
                    return (
                      <button
                        key={cap.id}
                        onClick={() => handleSelectCapability(cap.id)}
                        className={`relative group w-9 h-9 rounded-xl ${cap.hoverBg} flex items-center justify-center transition-all hover:scale-110`}
                        title={cap.label}
                      >
                        <Icon className={`w-4 h-4 ${cap.color}`} />
                        {/* Tooltip */}
                        <span className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 rounded-lg bg-gray-900 text-white text-[10px] font-bold whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg">
                          {cap.label}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* CTAs — always prominent */}
                <div className="flex items-center gap-2">
                  <a
                    href="https://hephae.co/schedule"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition-all shadow-lg shadow-blue-600/25 group whitespace-nowrap"
                  >
                    <Calendar className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
                    Schedule Call
                  </a>

                  {activeReportUrl && (
                    <button
                      onClick={() => setShowSharePanel(true)}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-600/25 group whitespace-nowrap"
                    >
                      <Share2 className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
                      Share Report
                    </button>
                  )}

                  {user && locatedBusiness && !activeHeartbeatId && (
                    <button
                      onClick={() => setShowHeartbeatSetup(true)}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-600/25 group whitespace-nowrap"
                    >
                      <Activity className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
                      Monitor Weekly
                    </button>
                  )}

                  {activeHeartbeatId && (
                    <HeartbeatBadge onClick={() => setShowHeartbeatSetup(true)} />
                  )}
                </div>
              </div>
            )}

            {/* Hephae logo badge — persistent branding on left panel when no report is displayed */}
            {!report && !forecast && !seoReport && !competitiveReport && !socialAuditReport && !isDiscovering && !isTyping && (
              <div className="absolute top-4 right-4 z-50 animate-fade-in">
                <HephaeLogo size="sm" variant="color" />
              </div>
            )}

            {/* Business identity pill — only in empty fallback (no map), so it doesn't overlap MapVisualizer */}
            {!report && !forecast && !seoReport && !competitiveReport && !isTyping && !isDiscovering && locatedBusiness && !locatedBusiness.coordinates && (
              <div className="absolute top-4 left-4 z-50 flex items-center gap-2.5 bg-white/90 backdrop-blur-md px-3 py-2 rounded-2xl shadow-lg border border-gray-200/80 max-w-xs">
                {((locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon) ? (
                  <img
                    src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon}
                    alt="Logo"
                    className="w-9 h-9 rounded-full object-cover border border-gray-200 flex-shrink-0"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : (
                  <div className="w-9 h-9 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                    <Building2 className="w-4 h-4 text-indigo-600" />
                  </div>
                )}
                <div className="min-w-0">
                  <div
                    className="text-sm font-bold leading-tight truncate"
                    style={{ color: (locatedBusiness as any).primaryColor || '#1e293b' }}
                  >
                    {locatedBusiness.name}
                  </div>
                  {(locatedBusiness.address || (locatedBusiness as any).persona) && (
                    <div className="text-xs text-gray-500 leading-tight truncate">
                      {(locatedBusiness as any).persona || locatedBusiness.address}
                    </div>
                  )}
                </div>
                {isDiscovering && <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />}
              </div>
            )}

            {/* Full-panel loading overlay — covers entire left panel for capability runs (not discovery — that uses full-screen) */}
            {isTyping && activeCapability && activeCapability !== 'discovery' && (
              <LoadingOverlay
                capabilityId={activeCapability}
                startTime={capabilityStartTime}
                businessName={locatedBusiness?.name}
                businessLogo={(locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon}
              />
            )}

            {report ? (
              renderSurgeonReport()
            ) : forecast ? (
              renderTrafficForecast()
            ) : competitiveReport ? (
              renderCompetitiveReport()
            ) : socialAuditReport ? (
              renderSocialAuditReport()
            ) : seoReport ? (
              <div className="w-full h-full overflow-y-auto pb-20 animate-fade-in relative" style={{ background: 'linear-gradient(135deg, #faf5ff 0%, #ede9fe 40%, #e0e7ff 100%)', color: '#1e293b' }}>
                <BlobBackground className="opacity-25 fixed" />
                <div className="absolute inset-0 pointer-events-none opacity-[0.25]">
                  <NeuralBackground />
                </div>
                <div className="relative z-10 p-4 md:p-8">
                  {/* Gradient Header */}
                  <header className="mb-8 p-4 md:p-6 rounded-2xl bg-gradient-to-r from-purple-600 via-violet-500 to-indigo-500 shadow-xl animate-fade-in-up">
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-3 md:gap-4 min-w-0">
                        {((locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon) ? (
                          <img src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon} className="h-10 w-10 md:h-12 md:w-12 rounded-full object-cover border-2 border-white/30 shadow-lg flex-shrink-0" alt="Logo" />
                        ) : (
                          <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0">
                            <SearchIcon className="w-5 h-5 md:w-6 md:h-6 text-white" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <h1 className="text-lg md:text-xl font-bold text-white truncate">{locatedBusiness?.name || 'Business'}</h1>
                          <p className="text-purple-100 text-sm">Google Presence Check</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
                        <span className="hidden md:block"><HephaeLogo size="sm" variant="white" /></span>
                        <button onClick={() => setSeoReport(null)} className="w-9 h-9 md:w-10 md:h-10 rounded-full bg-white/20 hover:bg-white/30 text-white flex items-center justify-center transition-colors" title="Close SEO Report">
                          <X size={20} />
                        </button>
                      </div>
                    </div>
                  </header>
                  <div className="animate-fade-in-up stagger-1">
                    <ResultsDashboard report={seoReport} groundingChunks={(seoReport as any).groundingChunks || []} />
                  </div>
                </div>
              </div>
            ) : locatedBusiness && locatedBusiness.coordinates ? (
              <MapVisualizer lat={locatedBusiness.coordinates.lat} lng={locatedBusiness.coordinates.lng} businessName={locatedBusiness.name} business={locatedBusiness} isDiscovering={isDiscovering} dashboard={businessOverview?.dashboard} />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center bg-transparent gap-4 p-8">
                {((locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon) && (
                  <img src={(locatedBusiness as any).logoUrl || (locatedBusiness as any).favicon} className="w-16 h-16 rounded-full object-cover border-2 border-gray-200 shadow-sm" alt="" />
                )}
                {locatedBusiness && (
                  <div className="text-center">
                    <div className="text-lg font-bold text-gray-700">{locatedBusiness.name}</div>
                    <div className="text-sm text-gray-400 mt-1">Gathering location data...</div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* RIGHT CHATBOT PANEL - Full screen when centered, floating card when active */}
      {/* When centered: pointer-events-none on wrapper so neural background is interactive; children re-enable pointer-events-auto on inputs/buttons */}
      <div className={`relative z-20 flex-shrink-0 transition-all duration-700 ease-in-out h-full ${isCentered ? 'w-full max-w-none pointer-events-none' : isChatCollapsed ? 'md:w-14 hidden md:block' : `md:w-[45%] w-full ${mobilePanel === 'visualizer' ? 'hidden md:block' : 'block'}`}`}>
        <ChatInterface
          messages={messages}
          onSendMessage={sendMessage}
          onPlaceSelect={handlePlaceSelect}
          isTyping={isTyping}
          isDiscovering={isDiscovering}
          onReset={() => {
            setMessages([{ id: '1', role: 'model', text: 'Hi! I am Hephae.\nSearch for your business to get started.', createdAt: Date.now() }]);
            setLocatedBusiness(null);
            setReport(null);
            setForecast(null);
            setSeoReport(null);
            setCompetitiveReport(null);
            setSocialAuditReport(null);
            setCapabilities([]);
            setIsDiscovering(false);
            setProfileReportUrl(null);
            setMarginReportUrl(null);
            setTrafficReportUrl(null);
            setSeoReportUrl(null);
            setCompetitiveReportUrl(null);
            setMarketingReportUrl(null);
            setIsChatCollapsed(false);
          }}
          capabilities={capabilities}
          onSelectCapability={handleSelectCapability}
          capabilitiesLocked={!user && capabilities.length > 0}
          isCentered={isCentered}
          followUpChips={dynamicChips}
          isCollapsed={isChatCollapsed}
          onToggleCollapse={() => setIsChatCollapsed(v => !v)}
        />
      </div>

      {/* Mobile panel toggle button */}
      {!isCentered && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[70] flex md:hidden">
          <button
            onClick={() => setMobilePanel(mobilePanel === 'chat' ? 'visualizer' : 'chat')}
            className="flex items-center gap-2 px-4 py-2.5 bg-white/95 backdrop-blur-md rounded-full shadow-2xl border border-gray-200 text-sm font-bold text-gray-700 active:scale-95 transition-transform"
          >
            {mobilePanel === 'chat' ? (
              <><Map className="w-4 h-4 text-indigo-500" /> View Report / Map</>
            ) : (
              <><MessageCircle className="w-4 h-4 text-indigo-500" /> Back to Chat</>
            )}
          </button>
        </div>
      )}

      <AuthWall
        isOpen={showAuthWall}
        onGoogleSignIn={async () => {
          await signInWithGoogle();
          setShowAuthWall(false);
          setHasProvidedEmail(true);
          // Start profile building if a business is located
          if (locatedBusiness) {
            startProfileBuilding();
          }
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

      {/* Full-screen discovery overlay — renders independently of panel transitions */}
      {isDiscovering && (
        <div className="fixed inset-0 z-[55] bg-white animate-fade-in">
          <LoadingOverlay
            capabilityId={activeCapability}
            startTime={capabilityStartTime}
            businessName={locatedBusiness?.name}
            businessLogo={(locatedBusiness as any)?.logoUrl || (locatedBusiness as any)?.favicon}
          />
        </div>
      )}
    </main>
  );
}
