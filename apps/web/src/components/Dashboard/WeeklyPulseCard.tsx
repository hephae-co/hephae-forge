'use client';

import { TrendingUp, MapPin } from 'lucide-react';
import dynamic from 'next/dynamic';
import { Label } from './Card';
import { LockedCard } from './LockedCard';
import type { DashboardData } from './types';

const MiniBar = dynamic(() => import('recharts').then(m => {
  const { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } = m;
  const C = ({ data, colors, tickColor }: { data: { label: string; value: number }[]; colors?: string[]; tickColor?: string }) => (
    <ResponsiveContainer width="100%" height={90}>
      <BarChart data={data} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 9, fill: tickColor ?? '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis hide domain={[0, 100]} />
        <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,.08)', fontSize: 11 }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={20}>
          {data.map((_, i) => (
            <Cell key={i} fill={colors?.[i % (colors?.length ?? 1)] ?? '#7c3aed'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
  C.displayName = 'MiniBar';
  return C;
}), { ssr: false });

export function WeeklyPulseCard({ dashboard, onNominateZip }: { dashboard: DashboardData | null; onNominateZip?: () => void }) {
  if (!dashboard?.pulseHeadline) {
    return <LockedCard title="Weekly Pulse" icon={TrendingUp} action="Load Business" className="h-full" />;
  }

  const metrics = dashboard.keyMetrics
    ? Object.entries(dashboard.keyMetrics).map(([label, value]) => ({ label, value }))
    : [];

  if (dashboard.isNational) {
    return (
      <div className="bg-gradient-to-br from-amber-700 to-orange-600 rounded-2xl p-6 flex flex-col justify-between h-full shadow-lg shadow-amber-900/20 text-white">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-amber-200">National Benchmarks</p>
            <span className="text-[9px] font-bold uppercase tracking-widest bg-amber-600/40 px-1.5 py-0.5 rounded text-amber-100">BLS · USDA</span>
          </div>
          <p className="text-white font-black text-lg mt-2 leading-snug">{dashboard.pulseHeadline}</p>
          <p className="text-amber-200 text-xs mt-2 leading-relaxed">Local weekly pulse unavailable — zip not yet monitored</p>
        </div>
        {metrics.length > 0 && (
          <div className="mt-4">
            <MiniBar data={metrics} colors={['#fde68a', '#fcd34d', '#fbbf24', '#f59e0b']} tickColor="#fef3c7" />
          </div>
        )}
        {onNominateZip && (
          <button
            onClick={onNominateZip}
            className="mt-4 flex items-center justify-center gap-2 bg-white/15 hover:bg-white/25 border border-white/25 text-white px-4 py-2.5 rounded-xl text-xs font-bold transition-colors"
          >
            <MapPin className="w-3.5 h-3.5" /> Get local data — nominate this zip
          </button>
        )}
      </div>
    );
  }

  const COLORS = ['#c4b5fd', '#a78bfa', '#8b5cf6', '#7c3aed'];

  return (
    <div className="bg-gradient-to-br from-purple-900 to-violet-800 rounded-2xl p-6 flex flex-col justify-between h-full shadow-lg shadow-purple-900/20 text-white">
      <div>
        <Label>Weekly Pulse</Label>
        <p className="text-white font-black text-xl mt-2 leading-tight">{dashboard.pulseHeadline}</p>
        {!!dashboard.confirmedSources && (
          <p className="text-purple-300 text-xs mt-2">{dashboard.confirmedSources} verified sources</p>
        )}
      </div>
      {metrics.length > 0 && (
        <div className="mt-4">
          <MiniBar data={metrics} colors={COLORS} tickColor="#c4b5fd" />
        </div>
      )}
    </div>
  );
}
