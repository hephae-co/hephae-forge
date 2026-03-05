"use client";

import React, { useState, useEffect } from "react";
import { Check, ScanEye, Scale, TrendingUp, Scissors, Lightbulb, CloudSun, Calendar, BarChart3, MapPin, Globe, Gauge, FileText, Award, Building2, Search, Shield, Target, Share2, PenTool, Heart, FileEdit, Compass, Wifi, Users, Camera, CheckCircle } from "lucide-react";
import type { PipelineStage } from "./loadingConfig";

// Map icon name strings to actual components
const ICON_MAP: Record<string, React.ElementType> = {
  ScanEye, Scale, TrendingUp, Scissors, Lightbulb,
  CloudSun, Calendar, BarChart3, MapPin,
  Globe, Gauge, FileText, Award,
  Building2, Search, Shield, Target,
  Share2, PenTool, Heart, FileEdit,
  Compass, Wifi, Users, Camera, CheckCircle,
};

function useActiveStage(
  stages: PipelineStage[],
  startTime: number | null,
  estimatedDurationMs: number,
) {
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!startTime) return;
    const id = setInterval(() => setTick((t) => t + 1), 500);
    return () => clearInterval(id);
  }, [startTime]);

  if (!startTime) return { activeIndex: 0, stageProgress: 0, overallProgress: 0 };

  const elapsed = Date.now() - startTime;
  const overallProgress = Math.min(elapsed / estimatedDurationMs, 0.95);

  let cumulative = 0;
  for (let i = 0; i < stages.length; i++) {
    const stageEnd = cumulative + stages[i].durationPercent / 100;
    if (overallProgress < stageEnd) {
      const stageStart = cumulative;
      const stageProgress = (overallProgress - stageStart) / (stages[i].durationPercent / 100);
      return { activeIndex: i, stageProgress, overallProgress };
    }
    cumulative = stageEnd;
  }

  return { activeIndex: stages.length - 1, stageProgress: 0.95, overallProgress: 0.95 };
}

interface AgentTimelineProps {
  stages: PipelineStage[];
  startTime: number | null;
  estimatedDurationMs: number;
  accentHex: string;
}

export default function AgentTimeline({ stages, startTime, estimatedDurationMs, accentHex }: AgentTimelineProps) {
  const { activeIndex, stageProgress, overallProgress } = useActiveStage(stages, startTime, estimatedDurationMs);
  const isOvertime = startTime ? (Date.now() - startTime) > estimatedDurationMs : false;

  return (
    <div className="flex flex-col gap-0.5">
      {stages.map((stage, i) => {
        const isCompleted = i < activeIndex;
        const isActive = i === activeIndex;
        const isPending = i > activeIndex;
        const IconComp = ICON_MAP[stage.icon] || Globe;
        const isLast = i === stages.length - 1;

        return (
          <div key={stage.id} className="flex items-start gap-3">
            {/* Icon + connector */}
            <div className="flex flex-col items-center flex-shrink-0">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-500 ${
                  isCompleted
                    ? "bg-emerald-100 text-emerald-600"
                    : isActive
                    ? "text-white shadow-lg"
                    : "bg-gray-100 text-gray-400"
                }`}
                style={isActive ? { backgroundColor: accentHex } : undefined}
              >
                {isCompleted ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <IconComp className={`w-4 h-4 ${isActive ? "animate-pulse" : ""}`} />
                )}
              </div>
              {!isLast && (
                <div
                  className={`w-0.5 h-6 transition-all duration-500 ${
                    isCompleted ? "bg-emerald-300" : isActive ? "bg-gradient-to-b from-current to-gray-200" : "bg-gray-200"
                  }`}
                  style={isActive ? { color: accentHex } : undefined}
                />
              )}
            </div>

            {/* Label + progress */}
            <div className="flex-1 pt-1">
              <div
                className={`text-sm transition-all duration-300 ${
                  isCompleted
                    ? "text-gray-500 font-medium"
                    : isActive
                    ? "font-semibold"
                    : "text-gray-400"
                }`}
                style={isActive ? { color: accentHex } : undefined}
              >
                {stage.label}
                {isActive && isOvertime && (
                  <span className="ml-2 text-xs text-gray-400 font-normal">(finishing up...)</span>
                )}
              </div>

              {/* Mini progress bar for active stage */}
              {isActive && (
                <div className="mt-1.5 h-1 w-full max-w-[160px] bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(stageProgress * 100, 95)}%`,
                      backgroundColor: accentHex,
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
