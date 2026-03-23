'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Scorecard from '@/components/Scorecard';
import BusinessDiscovery from '@/components/BusinessDiscovery';
import BusinessBrowser from '@/components/BusinessBrowser';
import MarketResearchSection from '@/components/MarketResearchSection';
import WorkflowDashboard from '@/components/WorkflowDashboard';
import TestFixturesBrowser from '@/components/TestFixturesBrowser';
import ContentStudio from '@/components/ContentStudio';
import RegisteredZipcodes from '@/components/RegisteredZipcodes';
import DashboardOverview from '@/components/DashboardOverview';
import IntelligenceDashboard from '@/components/IntelligenceDashboard';
import { RunSummary } from '@/lib/tester/storage';
import { PlayCircle, RefreshCw, ServerCrash, Store, Workflow, FlaskConical, Users, PenSquare, LayoutDashboard, Settings, X, LogOut, Zap, MapPin, Brain } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

type Tab = 'dashboard' | 'businesses' | 'workflows' | 'content' | 'zipcodes' | 'intelligence';

type ZipSubTab = 'onboarded' | 'weekly' | 'tests';

function ZipcodesSection() {
  const [subTab, setSubTab] = useState<ZipSubTab>('onboarded');
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
      <div className="flex items-center gap-1 bg-white p-1 rounded-lg border border-gray-200 shadow-sm w-fit">
        <button
          onClick={() => setSubTab('onboarded')}
          className={`px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-all ${subTab === 'onboarded' ? 'bg-indigo-600 text-white shadow' : 'text-gray-500 hover:text-gray-900'}`}
        >
          <MapPin className="w-4 h-4" /> Onboarded Zips
        </button>
        <button
          onClick={() => setSubTab('weekly')}
          className={`px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-all ${subTab === 'weekly' ? 'bg-indigo-600 text-white shadow' : 'text-gray-500 hover:text-gray-900'}`}
        >
          <Zap className="w-4 h-4" /> Weekly Runs
        </button>
        <button
          onClick={() => setSubTab('tests')}
          className={`px-4 py-2 rounded-md text-sm font-semibold flex items-center gap-2 transition-all ${subTab === 'tests' ? 'bg-amber-500 text-white shadow' : 'text-gray-500 hover:text-gray-900'}`}
        >
          <FlaskConical className="w-4 h-4" /> Test Runs
        </button>
      </div>
      <RegisteredZipcodes activeSubTab={subTab} />
    </div>
  );
}

export default function HephaeAdminDashboard() {
  const { user, signOut } = useAuth();
  const [activeTab, setActiveTabState] = useState<Tab>('dashboard');
  const setActiveTab = (tab: Tab) => {
    setActiveTabState(tab);
    if (typeof window !== 'undefined') localStorage.setItem('hephae_active_tab', tab);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      let saved = localStorage.getItem('hephae_active_tab') as string | null;
      if (saved === 'research') saved = 'businesses';
      if (saved === 'pulse') saved = 'zipcodes';
      if (saved) setActiveTabState(saved as Tab);
    }
  }, []);
  const [qaOpen, setQaOpen] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedZip, setSelectedZipState] = useState<string>('');
  const [browserRefreshKey, setBrowserRefreshKey] = useState(0);

  const setSelectedZip = (zip: string) => {
    setSelectedZipState(zip);
    if (typeof window !== 'undefined') localStorage.setItem('hephae_selected_zip', zip);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('hephae_selected_zip');
      if (saved) setSelectedZipState(saved);
    }
  }, []);
  const fetchRuns = async () => {
    try {
      const res = await fetch('/api/run-tests');
      if (!res.ok) throw new Error("Failed to fetch history");
      const data = await res.json();
      setRuns(data.sort((a: RunSummary, b: RunSummary) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (qaOpen) {
      fetchRuns();
    }
  }, [qaOpen]);

  const handleRunTests = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const res = await fetch('/api/run-tests', { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Execution failed");
      }
      await fetchRuns();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsRunning(false);
    }
  };

  const latestRun = runs[0];
  const historicalRuns = runs.slice(1);

  const tabs: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { key: 'zipcodes', label: 'Zipcodes', icon: MapPin },
    { key: 'intelligence', label: 'Intelligence', icon: Brain },
    { key: 'businesses', label: 'Businesses', icon: Store },
    { key: 'workflows', label: 'Workflows', icon: Workflow },
    { key: 'content', label: 'Content', icon: PenSquare },
  ];

  return (
    <main className="min-h-screen bg-gray-50 text-gray-900 font-sans selection:bg-indigo-100">
      {/* Accent gradient bar */}
      <div className="h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />

      <div className="max-w-[90rem] mx-auto px-6 py-8">
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
          <div className="flex items-center gap-4 shrink-0">
            <Image src="/hephae_logo_blue.png" alt="Hephae" width={44} height={44} className="rounded-lg" />
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-3xl font-extrabold text-gray-900 whitespace-nowrap">Hephae</h1>
                <span className="text-[10px] font-bold uppercase tracking-widest bg-indigo-100 text-indigo-600 px-2 py-0.5 rounded-full border border-indigo-200">Admin</span>
              </div>
              <p className="text-gray-500 mt-0.5 text-sm">Industry Intelligence Pipeline</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <nav className="flex bg-white p-1 rounded-xl border border-gray-200 shadow-sm">
              {tabs.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 transition-all ${activeTab === key ? 'bg-indigo-600 text-white shadow-md' : 'text-gray-500 hover:text-gray-900'}`}
                >
                  <Icon className="w-4 h-4" /> {label}
                </button>
              ))}
            </nav>
            <button
              onClick={() => setQaOpen(true)}
              className="p-2.5 rounded-lg border border-gray-200 bg-white text-gray-500 hover:text-gray-900 hover:bg-gray-50 transition-colors shadow-sm"
              title="QA Suite"
            >
              <Settings className="w-4 h-4" />
            </button>
            {user && (
              <div className="flex items-center gap-2 ml-2 pl-2 border-l border-gray-200">
                {user.photoURL ? (
                  <img src={user.photoURL} alt="" className="w-7 h-7 rounded-full" referrerPolicy="no-referrer" />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold">
                    {(user.email || '?')[0].toUpperCase()}
                  </div>
                )}
                <span className="text-xs text-gray-500 hidden md:block max-w-[140px] truncate">{user.email}</span>
                <button
                  onClick={signOut}
                  className="p-2 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Sign out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </header>

        {error && !qaOpen && (
          <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-600">
            <ServerCrash className="w-6 h-6" />
            <div>
              <h3 className="font-bold">Error</h3>
              <p>{error}</p>
            </div>
          </div>
        )}

        {activeTab === 'dashboard' && (
          <DashboardOverview />
        )}

        {activeTab === 'businesses' && (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
            <MarketResearchSection />
            <BusinessDiscovery
              onZipCodeSubmit={(zip) => setSelectedZip(zip)}
              onDiscoveryComplete={(zip) => { setSelectedZip(zip); setBrowserRefreshKey(k => k + 1); }}
            />
            <BusinessBrowser key={browserRefreshKey} zipCode={selectedZip} />
          </div>
        )}

        {activeTab === 'workflows' && (
          <WorkflowDashboard />
        )}

        {activeTab === 'content' && (
          <ContentStudio />
        )}

        {activeTab === 'zipcodes' && (
          <ZipcodesSection />
        )}

        {activeTab === 'intelligence' && (
          <IntelligenceDashboard />
        )}
      </div>

      {/* QA Slide-out Panel */}
      {qaOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/30 z-40 transition-opacity"
            onClick={() => setQaOpen(false)}
          />
          {/* Panel */}
          <div className="fixed top-0 right-0 h-full w-full max-w-2xl bg-gray-50 z-50 shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-300">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-5 h-5 text-indigo-600" />
                <h2 className="text-lg font-bold text-gray-900">QA Suite</h2>
              </div>
              <button
                onClick={() => setQaOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-12">
              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-red-600">
                  <ServerCrash className="w-5 h-5" />
                  <div>
                    <h3 className="font-bold text-sm">Error</h3>
                    <p className="text-sm">{error}</p>
                  </div>
                </div>
              )}

              {/* Evaluation Suite */}
              <div>
                <div className="flex justify-between items-center mb-8 bg-white border border-gray-200 p-6 rounded-xl shadow-sm">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">Evaluation Suite</h3>
                    <p className="text-sm text-gray-500">Run technical specs and capability checks</p>
                  </div>
                  <button
                    onClick={handleRunTests}
                    disabled={isRunning}
                    className="group relative px-6 py-3 font-semibold text-white bg-indigo-600 rounded-lg overflow-hidden transition-all hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-md"
                  >
                    {isRunning ? <RefreshCw className="w-5 h-5 animate-spin" /> : <PlayCircle className="w-5 h-5 group-hover:scale-110 transition-transform" />}
                    {isRunning ? "Running Suite..." : "Run Tests Now"}
                  </button>
                </div>

                <section className="mb-16">
                  <h2 className="text-2xl border-b border-gray-200 pb-2 mb-6 font-semibold flex items-center gap-2 text-gray-800">
                    <span className="w-3 h-3 rounded-full bg-green-500 animate-pulse"></span>
                    Latest Results
                  </h2>
                  {latestRun ? (
                    <Scorecard run={latestRun} />
                  ) : (
                    <div className="text-center py-20 border border-dashed border-gray-300 rounded-xl text-gray-400">
                      No test runs found. Click &quot;Run Tests Now&quot; to start.
                    </div>
                  )}
                </section>

                {historicalRuns.length > 0 && (
                  <section>
                    <h2 className="text-2xl border-b border-gray-200 pb-2 mb-6 font-semibold text-gray-700">Run History</h2>
                    <div className="grid gap-6 text-sm opacity-90">
                      {historicalRuns.map((run, idx) => (
                        <Scorecard key={idx} run={run} />
                      ))}
                    </div>
                  </section>
                )}
              </div>

              {/* Test Fixtures */}
              <TestFixturesBrowser />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
