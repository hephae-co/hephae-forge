import React from 'react';
import { TimeSlot, DailyForecast, TrafficLevel } from './types';

interface DetailPanelProps {
  day: DailyForecast | null;
  slot: TimeSlot | null;
  onAskAI: (query: string) => void;
}

const DetailPanel: React.FC<DetailPanelProps> = ({ day, slot, onAskAI }) => {
  const [showAllEvents, setShowAllEvents] = React.useState(false);

  if (!day || !slot) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm mb-4 text-center">
        <p className="text-gray-400 text-sm">Select a time slot below to view analysis</p>
      </div>
    );
  }

  const getLevelColor = (level: TrafficLevel) => {
    switch (level) {
      case TrafficLevel.LOW: return 'bg-gray-100 text-gray-500 border-gray-200';
      case TrafficLevel.MEDIUM: return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case TrafficLevel.HIGH: return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case TrafficLevel.VERY_HIGH: return 'bg-emerald-600 text-white border-emerald-700 shadow-sm';
      case TrafficLevel.CLOSED: return 'bg-slate-200 text-slate-400 border-slate-300';
      default: return 'bg-gray-50 text-gray-400';
    }
  };

  const visibleEvents = showAllEvents ? day.localEvents : day.localEvents.slice(0, 4);
  const hiddenCount = day.localEvents.length - 4;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm mb-4 overflow-hidden">
      {/* Compact Header with Score */}
      <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider">{day.dayOfWeek} • {slot.label}</div>
          <div className="text-lg font-bold text-gray-900 leading-tight mt-1">{slot.reason.split('.')[0]}.</div>
        </div>
        <div className={`px-3 py-2 rounded-xl border flex flex-col items-center min-w-[80px] ${getLevelColor(slot.level)}`}>
          <span className="text-lg font-black leading-none uppercase">{slot.level}</span>
          <span className="text-[10px] font-bold uppercase opacity-80">Traffic</span>
        </div>
      </div>

      {/* Quick Actions / Deep Analysis */}
      <div className="p-3 bg-indigo-50/50 border-b border-indigo-100 flex gap-2 overflow-x-auto">
        <span className="text-xs font-bold text-indigo-400 uppercase py-1.5 px-1 whitespace-nowrap">Deep Analysis:</span>
        <button
          onClick={() => onAskAI(`How should I adjust staffing for ${day.dayOfWeek} ${slot.label} considering traffic is ${slot.level}?`)}
          className="px-3 py-2 md:py-1 bg-white border border-indigo-200 text-indigo-700 text-xs rounded-full hover:bg-indigo-50 shadow-sm whitespace-nowrap transition-colors"
        >
          👨‍🍳 Staffing?
        </button>
        <button
          onClick={() => onAskAI(`Suggest a promotion to capitalize on ${slot.level} traffic on ${day.dayOfWeek} ${slot.label}.`)}
          className="px-3 py-2 md:py-1 bg-white border border-indigo-200 text-indigo-700 text-xs rounded-full hover:bg-indigo-50 shadow-sm whitespace-nowrap transition-colors"
        >
          📢 Promo Idea?
        </button>
        <button
          onClick={() => onAskAI(`Why exactly is traffic ${slot.level} on ${day.dayOfWeek} ${slot.label}? Expand on the reason.`)}
          className="px-3 py-2 md:py-1 bg-white border border-indigo-200 text-indigo-700 text-xs rounded-full hover:bg-indigo-50 shadow-sm whitespace-nowrap transition-colors"
        >
          🔍 Analyze Why
        </button>
      </div>

      {/* Context Details */}
      <div className="p-4 grid grid-cols-2 gap-4">
        {day.localEvents.length > 0 && (
          <div className="col-span-2">
            <div className="flex justify-between items-end mb-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">Impactful Events (Click to Ask AI)</div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {visibleEvents.map((evt, i) => (
                <button
                  key={i}
                  onClick={() => onAskAI(`Tell me more about the event "${evt}" and how it impacts traffic on ${day.dayOfWeek}.`)}
                  className="inline-flex items-center px-2 py-1 rounded bg-blue-50 text-blue-700 text-xs font-medium border border-blue-100 hover:bg-blue-100 hover:border-blue-300 transition-colors cursor-pointer text-left"
                  title="Ask AI about this event"
                >
                  <span className="mr-1">📅</span>
                  {evt}
                </button>
              ))}

              {!showAllEvents && hiddenCount > 0 && (
                <button
                  onClick={() => setShowAllEvents(true)}
                  className="inline-flex items-center px-2 py-1 rounded bg-gray-50 text-gray-500 text-xs font-medium border border-gray-200 hover:bg-gray-100 transition-colors"
                >
                  +{hiddenCount} more
                </button>
              )}

              {showAllEvents && hiddenCount > 0 && (
                <button
                  onClick={() => setShowAllEvents(false)}
                  className="inline-flex items-center px-2 py-1 rounded bg-gray-50 text-gray-500 text-xs font-medium border border-gray-200 hover:bg-gray-100 transition-colors"
                >
                  Show Less
                </button>
              )}
            </div>
          </div>
        )}

        <div className="col-span-2 text-sm text-gray-600 leading-relaxed bg-gray-50 p-3 rounded-lg border border-gray-100">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wide">AI Logic & Raw Factors</span>
            <div className="h-px bg-gray-200 flex-grow"></div>
          </div>
          <ul className="space-y-1.5">
            {slot.reason.split('. ').map((point, idx) => (
              point.length > 2 && (
                <li key={idx} className="flex gap-2 text-xs text-gray-700 leading-snug">
                  <span className="text-indigo-400 mt-0.5">•</span>
                  <span>{point.replace(/\.$/, '')}.</span>
                </li>
              )
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default DetailPanel;