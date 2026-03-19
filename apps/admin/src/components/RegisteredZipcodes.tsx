'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  MapPin,
  Loader2,
  RefreshCw,
  Plus,
  Trash2,
  Pause,
  Play,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Calendar,
  XCircle,
} from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────────────

interface RegisteredZipcode {
  id: string;
  zipCode: string;
  businessType: string;
  city: string;
  state: string;
  county: string;
  status: 'active' | 'paused';
  registeredAt: string;
  lastPulseAt: string | null;
  lastPulseId: string | null;
  pulseCount: number;
  nextScheduledAt: string | null;
}

interface CronRun {
  jobId: string;
  zipCode: string;
  businessType: string;
  status: string;
  createdAt: string | null;
  completedAt: string | null;
  error: string | null;
}

interface CronStatus {
  activeZipcodes: number;
  pausedZipcodes: number;
  nextRunAt: string;
  schedule: string;
  recentRuns: CronRun[];
}

const BUSINESS_TYPES = [
  'Restaurants', 'Bakeries', 'Cafes', 'Coffee Shops', 'Pizza',
  'Retail', 'Salons', 'Spas', 'Barbers', 'Grocery',
  'Boutique', 'Florist', 'Hardware', 'Pet Store',
];

// ── Helpers ─────────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Main Component ──────────────────────────────────────────────────────

export default function RegisteredZipcodes() {
  const [zipcodes, setZipcodes] = useState<RegisteredZipcode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Registration form
  const [zipInput, setZipInput] = useState('');
  const [bizType, setBizType] = useState('Restaurants');
  const [registering, setRegistering] = useState(false);
  const [regSuccess, setRegSuccess] = useState<string | null>(null);

  // Action loading states
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  // Cron status
  const [cronStatus, setCronStatus] = useState<CronStatus | null>(null);
  const [cronLoading, setCronLoading] = useState(true);

  const fetchZipcodes = useCallback(async () => {
    try {
      const res = await fetch('/api/registered-zipcodes');
      if (res.ok) setZipcodes(await res.json());
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  const fetchCronStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/registered-zipcodes/cron-status');
      if (res.ok) setCronStatus(await res.json());
    } catch { /* ignore */ } finally { setCronLoading(false); }
  }, []);

  useEffect(() => { fetchZipcodes(); fetchCronStatus(); }, [fetchZipcodes, fetchCronStatus]);

  const handleRegister = async () => {
    if (!zipInput.match(/^\d{5}$/)) {
      setError('Enter a valid 5-digit zip code');
      return;
    }
    setRegistering(true);
    setError(null);
    setRegSuccess(null);
    try {
      const res = await fetch('/api/registered-zipcodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zipCode: zipInput, businessType: bizType }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
        throw new Error(err.detail || 'Registration failed');
      }
      const data = await res.json();
      setRegSuccess(`Registered ${zipInput} (${data.city}, ${data.state}) for ${bizType}`);
      setZipInput('');
      fetchZipcodes();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRegistering(false);
    }
  };

  const handleUnregister = async (zip: RegisteredZipcode) => {
    if (!confirm(`Unregister ${zip.zipCode} / ${zip.businessType}? This cannot be undone.`)) return;
    const key = `del-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(`/api/registered-zipcodes/${zip.zipCode}/${zip.businessType}`, { method: 'DELETE' });
      if (res.ok) setZipcodes(prev => prev.filter(z => z.id !== zip.id));
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleToggleStatus = async (zip: RegisteredZipcode) => {
    const action = zip.status === 'active' ? 'pause' : 'resume';
    const key = `toggle-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(`/api/registered-zipcodes/${zip.zipCode}/${zip.businessType}/${action}`, { method: 'POST' });
      if (res.ok) {
        setZipcodes(prev => prev.map(z =>
          z.id === zip.id ? { ...z, status: action === 'pause' ? 'paused' : 'active' } : z
        ));
      }
    } catch { /* ignore */ } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const handleRunNow = async (zip: RegisteredZipcode) => {
    const key = `run-${zip.id}`;
    setActionLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch('/api/weekly-pulse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          zipCode: zip.zipCode,
          businessType: zip.businessType,
          force: true,
        }),
      });
      if (!res.ok) throw new Error('Failed to trigger pulse');
      const { jobId } = await res.json();

      // Poll for completion (max 3 minutes)
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const pollRes = await fetch(`/api/weekly-pulse/jobs/${jobId}`);
        if (!pollRes.ok) continue;
        const job = await pollRes.json();
        if (job.status === 'COMPLETED') {
          fetchZipcodes();
          return;
        }
        if (job.status === 'FAILED') throw new Error(job.error || 'Pulse generation failed');
      }
      throw new Error('Timed out');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  // ── Render ──────────────────────────────────────────────────────────

  const activeCount = zipcodes.filter(z => z.status === 'active').length;
  const pausedCount = zipcodes.filter(z => z.status === 'paused').length;

  return (
    <div className="space-y-6">
      {/* Registration Form */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <MapPin className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-bold text-gray-900">Register Zipcode</h2>
        </div>
        <div className="flex flex-col md:flex-row gap-3">
          <input
            type="text"
            placeholder="Zip code (e.g. 07110)"
            value={zipInput}
            onChange={(e) => setZipInput(e.target.value.replace(/\D/g, '').slice(0, 5))}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm w-48"
          />
          <select
            value={bizType}
            onChange={(e) => setBizType(e.target.value)}
            className="bg-gray-50 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all text-sm"
          >
            {BUSINESS_TYPES.map(bt => <option key={bt} value={bt}>{bt}</option>)}
          </select>
          <button
            onClick={handleRegister}
            disabled={registering || !zipInput}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm"
          >
            {registering ? (
              <><Loader2 className="w-4 h-4 animate-spin" />Registering...</>
            ) : (
              <><Plus className="w-4 h-4" />Register</>
            )}
          </button>
        </div>

        {regSuccess && (
          <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            {regSuccess}
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Registered Zipcodes Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-gray-400" />
            Registered Zipcodes
            <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full font-medium">{activeCount} active</span>
            {pausedCount > 0 && (
              <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full font-medium">{pausedCount} paused</span>
            )}
          </h3>
          <button
            onClick={() => { setLoading(true); fetchZipcodes(); }}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="p-10 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
          </div>
        ) : zipcodes.length === 0 ? (
          <div className="p-10 text-center text-gray-400 text-sm">
            No zipcodes registered yet. Use the form above to add one.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
                  <th className="text-left px-6 py-3">Zip Code</th>
                  <th className="text-left px-4 py-3">City / State</th>
                  <th className="text-left px-4 py-3">Business Type</th>
                  <th className="text-center px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Last Pulse</th>
                  <th className="text-center px-4 py-3">Count</th>
                  <th className="text-right px-6 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {zipcodes.map((zip) => (
                  <tr key={zip.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3">
                      <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">
                        {zip.zipCode}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {zip.city}, {zip.state}
                      {zip.county && (
                        <span className="text-xs text-gray-400 ml-1">({zip.county})</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-700">{zip.businessType}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        zip.status === 'active'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}>
                        {zip.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {relativeTime(zip.lastPulseAt)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-xs font-mono text-gray-600">{zip.pulseCount ?? 0}</span>
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* Run Now */}
                        <button
                          onClick={() => handleRunNow(zip)}
                          disabled={!!actionLoading[`run-${zip.id}`]}
                          className="p-1.5 rounded-lg text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                          title="Run pulse now"
                        >
                          {actionLoading[`run-${zip.id}`] ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Zap className="w-4 h-4" />
                          )}
                        </button>
                        {/* Pause / Resume */}
                        <button
                          onClick={() => handleToggleStatus(zip)}
                          disabled={!!actionLoading[`toggle-${zip.id}`]}
                          className={`p-1.5 rounded-lg transition-colors disabled:opacity-50 ${
                            zip.status === 'active'
                              ? 'text-amber-500 hover:text-amber-700 hover:bg-amber-50'
                              : 'text-emerald-500 hover:text-emerald-700 hover:bg-emerald-50'
                          }`}
                          title={zip.status === 'active' ? 'Pause' : 'Resume'}
                        >
                          {actionLoading[`toggle-${zip.id}`] ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : zip.status === 'active' ? (
                            <Pause className="w-4 h-4" />
                          ) : (
                            <Play className="w-4 h-4" />
                          )}
                        </button>
                        {/* Delete */}
                        <button
                          onClick={() => handleUnregister(zip)}
                          disabled={!!actionLoading[`del-${zip.id}`]}
                          className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                          title="Unregister"
                        >
                          {actionLoading[`del-${zip.id}`] ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Cron Status */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            Weekly Cron Status
          </h3>
          <button
            onClick={() => { setCronLoading(true); fetchCronStatus(); }}
            className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>

        {cronLoading ? (
          <div className="p-10 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-gray-300 animate-spin" />
          </div>
        ) : cronStatus ? (
          <div className="p-6 space-y-5">
            {/* Schedule overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                <p className="text-xs text-gray-400">Schedule</p>
                <p className="text-sm font-semibold text-gray-800">{cronStatus.schedule}</p>
              </div>
              <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                <p className="text-xs text-gray-400">Next Run</p>
                <p className="text-sm font-semibold text-gray-800">
                  {new Date(cronStatus.nextRunAt).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                  {' '}
                  {new Date(cronStatus.nextRunAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                </p>
              </div>
              <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
                <p className="text-xs text-emerald-500">Active in Cron</p>
                <p className="text-sm font-semibold text-emerald-800">{cronStatus.activeZipcodes} zipcodes</p>
              </div>
              <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                <p className="text-xs text-amber-500">Paused</p>
                <p className="text-sm font-semibold text-amber-800">{cronStatus.pausedZipcodes} zipcodes</p>
              </div>
            </div>

            {/* Recent cron runs */}
            {cronStatus.recentRuns.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Recent Cron Runs</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
                        <th className="text-left px-4 py-2">Zip / Type</th>
                        <th className="text-center px-4 py-2">Status</th>
                        <th className="text-left px-4 py-2">Started</th>
                        <th className="text-left px-4 py-2">Completed</th>
                        <th className="text-left px-4 py-2">Job ID</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {cronStatus.recentRuns.map((run, i) => (
                        <tr key={i} className="hover:bg-gray-50/50">
                          <td className="px-4 py-2">
                            <span className="text-xs font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">{run.zipCode}</span>
                            <span className="text-xs text-gray-400 ml-1">{run.businessType}</span>
                          </td>
                          <td className="px-4 py-2 text-center">
                            {run.status === 'COMPLETED' ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">Completed</span>
                            ) : run.status === 'FAILED' ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 font-medium" title={run.error || ''}>Failed</span>
                            ) : run.status === 'RUNNING' ? (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 font-medium">Running</span>
                            ) : (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 font-medium">{run.status}</span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-xs text-gray-500">{run.createdAt ? relativeTime(run.createdAt) : '-'}</td>
                          <td className="px-4 py-2 text-xs text-gray-500">{run.completedAt ? relativeTime(run.completedAt) : '-'}</td>
                          <td className="px-4 py-2 text-xs font-mono text-gray-400 truncate max-w-[120px]">{run.jobId}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {cronStatus.recentRuns.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-4">No cron runs yet. The first run will happen at the next scheduled time.</p>
            )}
          </div>
        ) : (
          <div className="p-10 text-center text-gray-400 text-sm">
            Could not load cron status.
          </div>
        )}
      </div>
    </div>
  );
}
