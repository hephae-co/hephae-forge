'use client';

import { Calendar } from 'lucide-react';
import { Card, Label } from './Card';
import { LockedCard } from './LockedCard';
import type { DashEvent } from './types';

const DAY_KEYWORDS: Record<string, string[]> = {
  Mon: ['monday', 'mon '],
  Tue: ['tuesday', 'tue '],
  Wed: ['wednesday', 'wed '],
  Thu: ['thursday', 'thu '],
  Fri: ['friday', 'fri '],
  Sat: ['saturday', 'sat '],
  Sun: ['sunday', 'sun ', 'easter', 'brunch'],
};
const DOT_COLORS = ['bg-purple-500', 'bg-violet-500', 'bg-indigo-500', 'bg-sky-500', 'bg-teal-500', 'bg-emerald-500', 'bg-amber-500'];

export function WeekCalendarCard({ events }: { events: DashEvent[] | null | undefined }) {
  if (!events?.length) {
    return <LockedCard title="This Week's Events" icon={Calendar} action="Load Business" />;
  }
  const assignedEvents = events.map((ev, idx) => {
    const lower = (ev.what + ' ' + ev.when).toLowerCase();
    const day = Object.entries(DAY_KEYWORDS).find(([, kws]) => kws.some(kw => lower.includes(kw)))?.[0] ?? null;
    return { ...ev, day, color: DOT_COLORS[idx % DOT_COLORS.length] };
  });
  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  return (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <Label>This Week&apos;s Events</Label>
        <Calendar className="w-4 h-4 text-purple-300" />
      </div>
      <div className="grid grid-cols-7 gap-1 mb-4">
        {DAYS.map(day => {
          const dayEvents = assignedEvents.filter(e => e.day === day);
          const isToday = new Date().toLocaleDateString('en-US', { weekday: 'short' }).slice(0, 3) === day;
          return (
            <div
              key={day}
              className={`rounded-xl p-2 text-center transition-all ${isToday ? 'bg-purple-700 text-white' : 'bg-slate-50 text-slate-600'}`}
            >
              <p className="text-[10px] font-bold uppercase">{day}</p>
              <div className="flex justify-center gap-0.5 mt-1.5 flex-wrap">
                {dayEvents.map((e, i) => (
                  <div key={i} className={`w-2 h-2 rounded-full ${e.color}`} title={e.what} />
                ))}
                {dayEvents.length === 0 && <div className="w-2 h-2 rounded-full bg-slate-200" />}
              </div>
            </div>
          );
        })}
      </div>
      <div className="space-y-2">
        {assignedEvents.slice(0, 4).map((e, i) => (
          <div key={i} className="flex items-start gap-2.5 text-xs">
            <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${e.color}`} />
            <div>
              <span className="font-bold text-slate-700">{e.what}</span>
              {e.day && <span className="text-purple-600 font-semibold ml-1.5">· {e.day}</span>}
              <p className="text-slate-400 leading-tight mt-0.5">{e.when}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
