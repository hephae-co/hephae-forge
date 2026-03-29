'use client';

import { Brain } from 'lucide-react';
import dynamic from 'next/dynamic';
import { Card, Label } from './Card';
import type { TrafficCardData } from './types';

const TrafficBar = dynamic(() => import('recharts').then(m => {
  const { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } = m;
  const C = ({ data, colorFn }: { data: { label: string; value: number }[]; colorFn?: (v: number) => string }) => (
    <ResponsiveContainer width="100%" height={100}>
      <BarChart data={data} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
        <YAxis hide domain={[0, 110]} />
        <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,.08)', fontSize: 11 }} />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} barSize={24}>
          {data.map((d, i) => (
            <Cell key={i} fill={colorFn ? colorFn(d.value) : '#7c3aed'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
  C.displayName = 'TrafficBar';
  return C;
}), { ssr: false });

export function FootTrafficCard({ traffic, onExpand }: { traffic: TrafficCardData; onExpand?: () => void }) {
  const scoreColor = traffic.weeklyScore >= 75 ? 'text-emerald-600' : traffic.weeklyScore >= 50 ? 'text-amber-500' : 'text-red-500';
  const barColor = (v: number) => v >= 80 ? '#7c3aed' : v >= 50 ? '#a78bfa' : '#ddd6fe';

  const dayData  = traffic.byDay.map(d => ({ label: d.day, value: d.score }));
  const hourData = traffic.hourly.map(d => ({ label: d.hour, value: d.score }));

  return (
    <Card className="p-6 border-l-4 border-sky-500 h-full flex flex-col cursor-pointer hover:shadow-md transition-shadow" onClick={onExpand}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <Label>Foot Traffic Forecast</Label>
          <h3 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Weekly Traffic Analysis</h3>
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          <span className={`block text-3xl font-black ${scoreColor}`}>{traffic.weeklyScore}</span>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">/100</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Peak Day</p>
          <p className="text-base font-black text-slate-900 mt-0.5">{traffic.peakDay}</p>
        </div>
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Peak Hour</p>
          <p className="text-base font-black text-slate-900 mt-0.5">{traffic.peakHour}</p>
        </div>
        <div className="bg-sky-50/60 rounded-xl px-3 py-2.5">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">This Week</p>
          <p className="text-base font-black text-emerald-600 mt-0.5">Forecast</p>
        </div>
      </div>

      <div className="mb-1">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Day of Week</p>
        <TrafficBar data={dayData} colorFn={barColor} />
      </div>

      <div className="mb-4">
        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Hourly Pattern</p>
        <TrafficBar data={hourData} colorFn={barColor} />
      </div>

      <div className="mt-auto bg-sky-50 border border-sky-100 rounded-xl p-3 flex items-start gap-2.5">
        <Brain className="w-4 h-4 text-sky-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-sky-800 leading-relaxed">{traffic.forecast}</p>
      </div>
    </Card>
  );
}
