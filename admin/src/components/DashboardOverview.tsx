'use client';

import { useEffect, useState } from 'react';
import {
  RefreshCw,
  Search,
  MapPin,
  Clock,
  GitBranch,
  Building2,
  Send,
  FileText,
  Share2,
  Map,
  Layers,
} from 'lucide-react';

interface DashboardStats {
  research: {
    totalRuns: number;
    uniqueZipCodes: number;
    lastRunAt: string | null;
    areaResearchCount: number;
    combinedContextCount: number;
  };
  workflows: {
    totalWorkflows: number;
    completedWorkflows: number;
    totalBusinessesDiscovered: number;
    totalOutreachComplete: number;
  };
  content: {
    totalPosts: number;
    publishedPosts: number;
    byPlatform: Record<string, number>;
  };
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function StatCard({
  icon: Icon,
  label,
  value,
  subtitle,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  subtitle?: string;
  accent: string;
}) {
  return (
    <div className={`bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex items-start gap-4 border-l-4 ${accent}`}>
      <div className="p-2 bg-gray-50 rounded-lg">
        <Icon className="w-5 h-5 text-gray-500" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm font-medium text-gray-600">{label}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex items-start gap-4 border-l-4 border-l-gray-200 animate-pulse">
      <div className="p-2 bg-gray-100 rounded-lg w-9 h-9" />
      <div className="space-y-2 flex-1">
        <div className="h-7 bg-gray-100 rounded w-16" />
        <div className="h-4 bg-gray-100 rounded w-24" />
      </div>
    </div>
  );
}

export default function DashboardOverview() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error('Failed to fetch stats');
      setStats(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const platformLabel = (key: string) => {
    const map: Record<string, string> = { x: 'X', instagram: 'Instagram', facebook: 'Facebook', blog: 'Blog' };
    return map[key] || key;
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-sm text-gray-500 mt-0.5">Overview of your research, workflows, and content</p>
        </div>
        <button
          onClick={fetchStats}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !stats && (
        <div className="space-y-8">
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Market Research</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <SkeletonCard /><SkeletonCard /><SkeletonCard />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Workflows &amp; Outreach</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <SkeletonCard /><SkeletonCard /><SkeletonCard />
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <>
          {/* Market Research */}
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Market Research</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard
                icon={Search}
                label="Total Runs"
                value={stats.research.totalRuns}
                accent="border-l-blue-500"
              />
              <StatCard
                icon={MapPin}
                label="Unique Zip Codes"
                value={stats.research.uniqueZipCodes}
                accent="border-l-indigo-500"
              />
              <StatCard
                icon={Clock}
                label="Last Run"
                value={stats.research.lastRunAt ? relativeTime(stats.research.lastRunAt) : 'Never'}
                accent="border-l-purple-500"
              />
            </div>
          </div>

          {/* Workflows & Outreach */}
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Workflows &amp; Outreach</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard
                icon={GitBranch}
                label="Total Workflows"
                value={stats.workflows.totalWorkflows}
                subtitle={`${stats.workflows.completedWorkflows} completed`}
                accent="border-l-emerald-500"
              />
              <StatCard
                icon={Building2}
                label="Businesses Discovered"
                value={stats.workflows.totalBusinessesDiscovered}
                accent="border-l-teal-500"
              />
              <StatCard
                icon={Send}
                label="Outreach Delivered"
                value={stats.workflows.totalOutreachComplete}
                accent="border-l-cyan-500"
              />
            </div>
          </div>

          {/* Content */}
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Content</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StatCard
                icon={FileText}
                label="Published Posts"
                value={stats.content.publishedPosts}
                subtitle={`${stats.content.totalPosts} total`}
                accent="border-l-orange-500"
              />
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5 flex items-start gap-4 border-l-4 border-l-pink-500">
                <div className="p-2 bg-gray-50 rounded-lg">
                  <Share2 className="w-5 h-5 text-gray-500" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-600 mb-2">Platform Breakdown</p>
                  {Object.keys(stats.content.byPlatform).length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(stats.content.byPlatform).map(([platform, count]) => (
                        <span
                          key={platform}
                          className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-700"
                        >
                          {platformLabel(platform)}: {count}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400">No posts yet</p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Other */}
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Other</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <StatCard
                icon={Map}
                label="Area Research"
                value={stats.research.areaResearchCount}
                accent="border-l-violet-500"
              />
              <StatCard
                icon={Layers}
                label="Combined Contexts"
                value={stats.research.combinedContextCount}
                accent="border-l-fuchsia-500"
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
