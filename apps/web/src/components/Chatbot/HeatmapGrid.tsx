import React from 'react';
import { DailyForecast, TimeSlot, TrafficLevel } from './types';

interface HeatmapGridProps {
    forecast: DailyForecast[];
    onSlotClick?: (day: DailyForecast, slot: TimeSlot) => void;
    selectedSlot?: { dayStr: string; slotLabel: string } | null;
}

const getLevelColor = (level: TrafficLevel) => {
    switch (level) {
        case TrafficLevel.LOW: return 'bg-gray-100 text-gray-500 border-gray-200';
        case TrafficLevel.MEDIUM: return 'bg-yellow-50 text-yellow-700 border-yellow-300 hover:bg-yellow-100';
        case TrafficLevel.HIGH: return 'bg-emerald-100 text-emerald-700 border-emerald-400 hover:bg-emerald-200';
        case TrafficLevel.VERY_HIGH: return 'bg-emerald-500 text-white border-emerald-400 hover:bg-emerald-400';
        case TrafficLevel.CLOSED: return 'bg-slate-100 text-slate-400 border-slate-200 opacity-70';
        default: return 'bg-gray-100 text-gray-500';
    }
};

const HeatmapGrid: React.FC<HeatmapGridProps> = ({ forecast, onSlotClick, selectedSlot }) => {
    return (
        <div className="overflow-x-auto pb-4 w-full h-full">
            <div className="w-full min-w-[600px] md:min-w-0">
                <div className="grid grid-cols-8 gap-2 mb-2">
                    <div className="col-span-1 font-semibold text-gray-600 text-sm flex items-end justify-center pb-2">Day</div>
                    {['Morning', 'Lunch', 'Afternoon', 'Evening'].map((time) => (
                        <div key={time} className="col-span-1 font-semibold text-gray-600 text-sm flex items-end justify-center pb-2">
                            {time}
                        </div>
                    ))}
                    <div className="col-span-3 font-semibold text-gray-600 text-sm flex items-end justify-start pl-4 pb-2">
                        Key Drivers
                    </div>
                </div>

                {forecast.map((day) => (
                    <div key={day.date} className="grid grid-cols-8 gap-2 mb-3 items-center group">
                        <div className="col-span-1 flex flex-col items-center justify-center p-2 rounded-xl bg-gray-50 shadow-sm border border-gray-200">
                            <span className="text-xs font-bold text-gray-500 uppercase">{day.dayOfWeek.substring(0, 3)}</span>
                            <span className="font-bold text-gray-700">{day.date.split('-')[2]}</span>
                        </div>

                        {day.slots.map((slot: any) => {
                            const isSelected = selectedSlot?.dayStr === day.date && selectedSlot?.slotLabel === slot.label;
                            return (
                                <button
                                    key={slot.label}
                                    onClick={() => onSlotClick && onSlotClick(day, slot)}
                                    className={`
                    col-span-1 h-14 rounded-xl border transition-all duration-200 flex flex-col items-center justify-center ${onSlotClick ? 'cursor-pointer' : 'cursor-default'} relative
                    ${getLevelColor(slot.level)}
                    ${isSelected ? 'ring-2 ring-blue-500 ring-offset-2 ring-offset-white z-10 scale-105 shadow-md' : 'border-transparent'}
                  `}
                                >
                                    <span className="text-[10px] font-bold tracking-wider">{slot.level}</span>
                                </button>
                            );
                        })}

                        <div className="col-span-3 pl-4 text-sm text-gray-700 bg-gray-50 rounded-r-xl p-2 h-full flex flex-col justify-center border-l-2 border-gray-200">
                            {day.localEvents.length > 0 ? (
                                <div className="flex flex-col gap-1.5">
                                    {day.localEvents.slice(0, 3).map((event: any, idx: any) => {
                                        const isSevere = event.toLowerCase().match(/(snow|storm|rain|alert|warning)/);
                                        return (
                                            <span key={idx} className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium whitespace-normal text-left leading-tight ${isSevere ? 'bg-red-50 text-red-600 border border-red-200 animate-pulse' : 'bg-indigo-50 text-indigo-700 border border-indigo-200'}`}>
                                                {isSevere && <span className="mr-1">⚠️</span>}
                                                {event}
                                            </span>
                                        );
                                    })}
                                    {day.localEvents.length > 3 && <span className="text-[10px] uppercase tracking-wide text-gray-400">+{day.localEvents.length - 3} more</span>}
                                </div>
                            ) : (
                                <span className="text-gray-400 italic text-xs">Regular traffic patterns</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default HeatmapGrid;
