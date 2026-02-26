'use client';

import { useState, useEffect } from 'react';
import { Download, AlertTriangle, TrendingUp, Loader2, BarChart3, Users, Search as SearchIcon } from 'lucide-react';
import { SurgicalReport } from '@/lib/types';
import clsx from 'clsx';
import ChatInterface from '@/components/Chatbot/ChatInterface';
import MapVisualizer from '@/components/Chatbot/MapVisualizer';
import HeatmapGrid from '@/components/Chatbot/HeatmapGrid';
import { ChatMessage, ForecastResponse } from '@/components/Chatbot/types';
import { BaseIdentity } from '@/lib/agents/core/types';
import { NeuralBackground } from '@/components/Chatbot/NeuralBackground';
import { EmailWall } from '@/components/Chatbot/EmailWall';
import ResultsDashboard from '@/components/Chatbot/seo/ResultsDashboard';
import { SeoReport } from '@/lib/types';

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: '1', role: 'model', text: 'Hi! I am Hephae.\nType the name of a business you want to analyze or just ask me anything.' }
  ]);
  const [isTyping, setIsTyping] = useState(false);

  // App States
  const [locatedBusiness, setLocatedBusiness] = useState<BaseIdentity | null>(null);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [capabilities, setCapabilities] = useState<{ id: string, label: string, icon?: React.ReactNode }[]>([]);

  const [report, setReport] = useState<SurgicalReport | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [seoReport, setSeoReport] = useState<SeoReport | null>(null);

  // Email Lead Capture States
  const [searchDocId, setSearchDocId] = useState<string | null>(null);
  const [showEmailWall, setShowEmailWall] = useState(false);
  const [hasProvidedEmail, setHasProvidedEmail] = useState(false);
  const [pendingCapability, setPendingCapability] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('hephae_has_provided_email');
      if (stored === 'true') {
        setHasProvidedEmail(true);
      }
    }
  }, []);

  const handleEmailSubmit = async (email: string) => {
    if (!searchDocId) return;
    const res = await fetch('/api/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: searchDocId, email })
    });
    if (res.ok) {
      setShowEmailWall(false);
      setHasProvidedEmail(true);
      localStorage.setItem('hephae_has_provided_email', 'true');

      // Resume the capability execution if one was pending
      if (pendingCapability) {
        const capToRun = pendingCapability;
        setPendingCapability(null);
        executeCapability(capToRun);
      }
    } else {
      throw new Error("Failed to save email");
    }
  };

  const sendMessage = async (text: string) => {
    // 1. Append user message
    const newMessages: ChatMessage[] = [...messages, { id: Date.now().toString(), role: 'user', text }];
    setMessages(newMessages);
    setIsTyping(true);
    setCapabilities([]); // Clear capabilities when a new message is sent

    // Lead Capture Interception: Always silently track the first query
    if (!hasProvidedEmail && !searchDocId) {
      try {
        const trackRes = await fetch('/api/track', {
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
      fetch('/api/track', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      }).catch(() => { }); // fire and forget
    }

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages })
      });

      if (!res.ok) throw new Error("Chat request failed");
      const data = await res.json();

      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: data.text }]);

      // Trigger Orchestrator State Change
      if (data.triggerCapabilityHandoff && data.locatedBusiness) {
        setLocatedBusiness(data.locatedBusiness);
        setReport(null);
        setForecast(null);
        setCapabilities([]); // Clear capabilities initially

        // Spawn Background Discovery
        triggerDiscoveryOrchestrator(data.locatedBusiness);
      }

    } catch (e: any) {
      console.error(e);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'model', text: "I encountered an error connecting to my core logic layer." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const triggerDiscoveryOrchestrator = async (identity: BaseIdentity) => {
    setIsDiscovering(true);
    try {
      const res = await fetch('/api/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identity })
      });
      if (res.ok) {
        const enrichedProfile = await res.json();
        setLocatedBusiness(enrichedProfile); // Update to enriched profile
        setCapabilities([
          { id: 'surgery', label: 'Analyze Menu Margins' },
          { id: 'traffic', label: 'Forecast Foot Traffic' },
          { id: 'seo', label: 'Run SEO Deep Audit' }
        ]);
        // Note: we do NOT add a new message, we just unlock the capabilities in the UI
      }
    } catch (e) {
      console.error("Discovery failed", e);
      // Fallback: unlock capabilities anyway
      setCapabilities([
        { id: 'surgery', label: 'Analyze Menu Margins' },
        { id: 'traffic', label: 'Forecast Foot Traffic' },
        { id: 'seo', label: 'Run SEO Deep Audit' }
      ]);
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleSelectCapability = async (capId: string) => {
    if (!locatedBusiness) return;

    if (!hasProvidedEmail) {
      // Block UI with Email Wall and pause capability
      setPendingCapability(capId);
      setShowEmailWall(true);
      return;
    }

    executeCapability(capId);
  };

  const executeCapability = async (capId: string) => {
    if (!locatedBusiness) return;

    if (capId === 'surgery') {
      const msgId = Date.now().toString();
      setMessages(prev => [...prev, { id: msgId, role: 'model', text: "Starting Margin Surgery. Deploying ProfilerAgent to crawl the website, this may take a moment to retrieve the menu screenshots and calculate commodity impacts... ⏱️" }]);
      setCapabilities([]);
      setIsTyping(true);

      try {
        // We now pass the enriched business down to /api/analyze to skip Crawler if menuScreenshotBase64 exists
        const payload = {
          url: locatedBusiness.officialUrl,
          enrichedProfile: locatedBusiness // Contains menuScreenshotBase64
        };
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "Analysis Failed");
        }

        const data = await res.json();
        setReport(data);
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: "Surgery complete. The surgical dashboard has been rendered." }]);

      } catch (e: any) {
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: `Failed to execute Margin Surgery: ${e.message}` }]);
      } finally {
        setIsTyping(false);
      }
    } else if (capId === 'traffic') {
      const msgId = Date.now().toString();
      setMessages(prev => [...prev, { id: msgId, role: 'model', text: "Starting Foot Traffic Forecast. Deploying ForecasterAgent to analyze local events, weather, and compute traffic models... ⏱️" }]);
      setCapabilities([]);
      setIsTyping(true);

      try {
        const res = await fetch('/api/capabilities/traffic', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: locatedBusiness }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "Analysis Failed");
        }

        const data = await res.json();
        setForecast(data);
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: `Forecast complete!\n\n**Executive Summary**:\n${data.summary}` }]);

      } catch (e: any) {
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: `Failed to execute Foot Traffic Forecast: ${e.message}` }]);
      } finally {
        setIsTyping(false);
      }
    } else if (capId === 'seo') {
      const msgId = Date.now().toString();
      setMessages(prev => [...prev, { id: msgId, role: 'model', text: "Deploying SEO Auditor to analyze indexing, web vitals, and content hierarchy... ⏱️" }]);
      setCapabilities([]);
      setIsTyping(true);

      try {
        const res = await fetch('/api/capabilities/seo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identity: locatedBusiness }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || "Analysis Failed");
        }

        const data = await res.json();
        setSeoReport(data);
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: `SEO Audit complete! Verified ${data.sections?.length || 0} critical infrastructure categories.` }]);

      } catch (e: any) {
        setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: 'model', text: `Failed to execute SEO Audit: ${e.message}` }]);
      } finally {
        setIsTyping(false);
      }
    }
  };

  const downloadSocialCard = async () => {
    if (!report) return;
    const topLeak = report.menu_items.sort((a, b) => b.price_leakage - a.price_leakage)[0];
    const totalLeakage = report.menu_items.reduce((s, i) => s + i.price_leakage, 0);

    const res = await fetch('/api/social-card', {
      method: "POST",
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

    return (
      <div className="w-full h-full overflow-y-auto pb-20 p-8 animate-fade-in" style={{ backgroundColor: '#0f172a', color: '#ffffff' }}>
        <header className="flex justify-between items-center mb-8 p-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md">
          <div className="flex items-center gap-4">
            {identity.logoUrl && <img src={identity.logoUrl} className="h-12 w-12 rounded-full object-cover" alt="Logo" />}
            <div>
              <h1 className="text-2xl font-bold" style={{ color: identity.primaryColor }}>{identity.name}</h1>
              <p className="text-sm opacity-70">{identity.persona}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm opacity-60">Surgical Score</div>
            <div className={clsx("text-4xl font-black", overall_score > 80 ? "text-green-400" : "text-yellow-400")}>{overall_score}/100</div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-8">
          <div className="p-8 rounded-3xl bg-gradient-to-br from-red-900/40 to-slate-900 border border-red-500/30">
            <h3 className="text-red-300 font-medium mb-1 flex items-center gap-2">
              <AlertTriangle size={18} /> DETECTED PROFIT LEAKAGE
            </h3>
            <div className="text-5xl font-bold text-white tracking-tight">
              ${totalLeakage.toLocaleString()} <span className="text-xl opacity-50 font-normal">/ cycle</span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
            <div className="p-6 border-b border-white/10"><h3 className="font-bold text-lg">Surgical Breakdown</h3></div>
            <table className="w-full text-left text-sm">
              <thead className="bg-white/5 text-xs uppercase tracking-wider opacity-60">
                <tr>
                  <th className="p-4">Item</th>
                  <th className="p-4">Benchmark</th>
                  <th className="p-4">Price</th>
                  <th className="p-4 text-green-400">Rec.</th>
                  <th className="p-4 text-right">Leakage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {topLeaks.map((item, i) => (
                  <tr key={i} className="hover:bg-white/5">
                    <td className="p-4">{item.item_name}</td>
                    <td className="p-4 opacity-70">${item.competitor_benchmark.toFixed(2)}</td>
                    <td className="p-4 opacity-70 border-l border-white/5">${item.current_price.toFixed(2)}</td>
                    <td className="p-4 font-bold text-green-400 border-l border-white/5">${item.recommended_price.toFixed(2)}</td>
                    <td className="p-4 text-right font-mono text-red-400">+${item.price_leakage.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-6 rounded-2xl bg-blue-900/20 border border-blue-500/30">
            <h3 className="text-blue-300 font-bold mb-4 flex items-center gap-2"><TrendingUp size={18} /> STRATEGIC ADVICE</h3>
            <div className="space-y-4">
              {strategic_advice.map((tip, i) => <div key={i} className="p-4 rounded-xl bg-blue-950/50 border border-blue-800/50 text-sm">"{tip}"</div>)}
            </div>
          </div>

          <button onClick={downloadSocialCard} className="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 font-bold text-white shadow-lg flex items-center justify-center gap-2 transition-all">
            <Download size={20} /> Download Integrity Report
          </button>
        </div>
      </div>
    );
  };

  const renderTrafficForecast = () => {
    if (!forecast) return null;
    return (
      <div className="w-full h-full overflow-y-auto pb-20 p-8 animate-fade-in" style={{ backgroundColor: '#0f172a', color: '#ffffff' }}>
        <header className="flex justify-between items-center mb-8 p-6 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="text-2xl font-bold" style={{ color: '#4ade80' }}>{forecast.business.name}</h1>
              <p className="text-sm opacity-70">Hephae Traffic forecaster</p>
            </div>
          </div>
        </header>

        <div className="p-8 rounded-3xl bg-slate-900 border border-slate-700 shadow-xl overflow-hidden mb-6">
          <HeatmapGrid forecast={forecast.forecast} />
        </div>
      </div>
    );
  };

  const isCentered = !locatedBusiness && !report && !forecast;

  return (
    <main className={`flex h-screen w-screen overflow-hidden relative transition-colors duration-700 ${isCentered ? 'bg-white' : 'bg-slate-950'}`}>

      {/* BACKGROUND ANIMATION */}
      {isCentered && (
        <div className="absolute inset-0 z-0 opacity-40 mix-blend-multiply pointer-events-none">
          <NeuralBackground />
        </div>
      )}

      {/* LEFT VISUALIZER PANEL - Hidden when centered */}
      <div className={`relative z-10 transition-all duration-700 ease-in-out flex flex-col ${isCentered ? 'w-0 opacity-0 overflow-hidden' : 'flex-1 opacity-100'}`}>
        {!isCentered && (
          <>
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 animate-fade-in-up pointer-events-auto bg-white/90 backdrop-blur-md p-1.5 rounded-full shadow-2xl border border-gray-200/80">
              <button onClick={() => handleSelectCapability("surgery")} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold text-gray-600 hover:text-indigo-600 hover:bg-indigo-50/80 transition-all group">
                <BarChart3 className="w-3.5 h-3.5 text-indigo-500 group-hover:scale-110 transition-transform" />
                Menu Margins
              </button>

              <div className="w-px h-4 bg-gray-200 mx-1"></div>

              <button onClick={() => handleSelectCapability("traffic")} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold text-gray-600 hover:text-emerald-600 hover:bg-emerald-50/80 transition-all group">
                <Users className="w-3.5 h-3.5 text-emerald-500 group-hover:scale-110 transition-transform" />
                Foot Traffic
              </button>

              <div className="w-px h-4 bg-gray-200 mx-1"></div>

              <button onClick={() => handleSelectCapability("seo")} className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold text-gray-600 hover:text-purple-600 hover:bg-purple-50/80 transition-all group">
                <SearchIcon className="w-3.5 h-3.5 text-purple-500 group-hover:scale-110 transition-transform" />
                SEO Auditor
              </button>
            </div>

            {report ? (
              renderSurgeonReport()
            ) : forecast ? (
              renderTrafficForecast()
            ) : seoReport ? (
              <div className="w-full h-full overflow-y-auto pb-20 p-8 pt-12 animate-fade-in" style={{ backgroundColor: '#0f172a' }}>
                <ResultsDashboard report={seoReport} groundingChunks={(seoReport as any).groundingChunks || []} />
              </div>
            ) : locatedBusiness && locatedBusiness.coordinates ? (
              <MapVisualizer lat={locatedBusiness.coordinates.lat} lng={locatedBusiness.coordinates.lng} businessName={locatedBusiness.name} business={locatedBusiness} isDiscovering={isDiscovering} />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-transparent mt-16 px-4">
                {/* Fallback space when left panel is active but no content is loaded */}
              </div>
            )}
          </>
        )}
      </div>

      {/* RIGHT CHATBOT PANEL - Expands to full screen when centered */}
      <div className={`relative z-20 flex-shrink-0 transition-all duration-700 ease-in-out h-full ${isCentered ? 'w-full max-w-none' : 'w-full max-w-[420px]'}`}>
        <ChatInterface
          messages={messages}
          onSendMessage={sendMessage}
          isTyping={isTyping}
          onReset={() => {
            setMessages([{ id: '1', role: 'model', text: 'Hi! I am Hephae. Type the name of a business you want to analyze or just ask me anything.' }]);
            setLocatedBusiness(null);
            setReport(null);
            setForecast(null);
            setSeoReport(null);
            setCapabilities([]);
            setIsDiscovering(false);
          }}
          capabilities={capabilities}
          onSelectCapability={handleSelectCapability}
          isCentered={isCentered}
          followUpChips={
            isCentered
              ? ["Analyze Bosphorus Nutley", "Find Tick Tock Diner Clifton", "What is my profit margin?"]
              : (locatedBusiness ? [
                `Tell me more about ${locatedBusiness.name}`,
                `Who are ${locatedBusiness.name}'s competitors?`,
                `What are the busiest hours?`
              ] : [])
          }
        />
      </div>

      <EmailWall isOpen={showEmailWall} onSubmit={handleEmailSubmit} />
    </main>
  );
}
