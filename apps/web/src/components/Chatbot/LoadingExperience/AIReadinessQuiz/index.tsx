"use client";

import React, { useState, useCallback } from "react";
import { RotateCcw } from "lucide-react";
import { MISSIONS } from "./missions";
import { GameHistory, Choice, QuizResult } from "./types";
import { computeResult } from "./scoring";

type Phase = "playing" | "results";

const TYPE_ICONS: Record<string, string> = {
  manual: "\u270D\uFE0F",
  digital: "\u{1F4BB}",
  ai: "\u2728",
};

const TYPE_LABELS: Record<string, string> = {
  manual: "Manual Execution",
  digital: "Standard Digital",
  ai: "AI-Augmented",
};

interface AIReadinessQuizProps {
  businessName?: string;
}

export default function AIReadinessQuiz({ businessName }: AIReadinessQuizProps) {
  const [phase, setPhase] = useState<Phase>("playing");
  const [currentIdx, setCurrentIdx] = useState(0);
  const [stats, setStats] = useState({ time: 100, budget: 100, sanity: 100 });
  const [history, setHistory] = useState<GameHistory["choices"]>([]);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const mission = MISSIONS[currentIdx];

  const handleChoice = useCallback(
    (choice: Choice) => {
      const newStats = {
        time: Math.max(0, Math.min(100, stats.time + choice.effects.time)),
        budget: Math.max(
          0,
          Math.min(100, stats.budget + choice.effects.budget)
        ),
        sanity: Math.max(
          0,
          Math.min(100, stats.sanity + choice.effects.sanity)
        ),
      };
      setStats(newStats);

      const newHistory = [
        ...history,
        {
          missionId: mission.id,
          choiceId: choice.id,
          type: choice.type,
        },
      ];
      setHistory(newHistory);

      if (currentIdx < MISSIONS.length - 1) {
        setTransitioning(true);
        setTimeout(() => {
          setCurrentIdx(currentIdx + 1);
          setTransitioning(false);
        }, 300);
      } else {
        const gameHistory: GameHistory = {
          choices: newHistory,
          finalStats: newStats,
        };
        setResult(computeResult(gameHistory));
        setPhase("results");
      }
    },
    [stats, history, currentIdx, mission]
  );

  const reset = () => {
    setPhase("playing");
    setCurrentIdx(0);
    setStats({ time: 100, budget: 100, sanity: 100 });
    setHistory([]);
    setResult(null);
    setTransitioning(false);
  };

  if (phase === "results" && result) {
    return <ResultsView result={result} onReset={reset} businessName={businessName} />;
  }

  return (
    <div className="w-full h-full overflow-y-auto px-4 py-3">
      <div className="max-w-md mx-auto">
        {/* Progress header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">
            Scenario {currentIdx + 1} of {MISSIONS.length}
          </span>
          <div className="h-1.5 w-24 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-500"
              style={{
                width: `${((currentIdx + 1) / MISSIONS.length) * 100}%`,
              }}
            />
          </div>
        </div>

        {/* Resource bars */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <ResourceBar
            value={stats.time}
            color="bg-blue-500"
            icon={"\u23F1\uFE0F"}
            label="Time"
          />
          <ResourceBar
            value={stats.budget}
            color="bg-emerald-500"
            icon={"\u{1F4B0}"}
            label="Budget"
          />
          <ResourceBar
            value={stats.sanity}
            color="bg-amber-500"
            icon={"\u{1F9E0}"}
            label="Capacity"
          />
        </div>

        {/* Live AI readiness preview */}
        {history.length > 0 && (
          <div className="mb-4 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-2.5 border border-indigo-100 flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center shrink-0">
              <span className="text-xs font-black text-white">
                {Math.min(100, history.filter(h => h.type === 'ai').length * 18 + history.filter(h => h.type === 'digital').length * 10 + history.filter(h => h.type === 'manual').length * 4 + Math.round(((stats.time + stats.budget + stats.sanity) / 3) * 0.1))}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider">AI Readiness</div>
              <div className="w-full h-1 bg-indigo-200 rounded-full mt-0.5 overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, history.filter(h => h.type === 'ai').length * 18 + history.filter(h => h.type === 'digital').length * 10 + history.filter(h => h.type === 'manual').length * 4 + Math.round(((stats.time + stats.budget + stats.sanity) / 3) * 0.1))}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Mission card */}
        <div
          className={`bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mb-4 transition-all duration-300 ${
            transitioning
              ? "opacity-0 translate-x-8 scale-95"
              : "opacity-100 translate-x-0 scale-100"
          }`}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="text-3xl">{mission.emoji}</div>
            {businessName && (
              <span className="text-[9px] font-bold text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full uppercase tracking-wider">
                {businessName}
              </span>
            )}
          </div>
          <h3 className="text-base font-bold text-gray-900 mb-1.5">
            {mission.title}
          </h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            {mission.description}
          </p>
        </div>

        {/* Choices */}
        <div
          className={`space-y-2.5 transition-all duration-300 ${
            transitioning
              ? "opacity-0 translate-x-8"
              : "opacity-100 translate-x-0"
          }`}
        >
          <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
            How would you handle this?
          </p>
          {mission.choices.map((choice) => (
            <button
              key={choice.id}
              onClick={() => handleChoice(choice)}
              className="w-full group bg-white hover:bg-gray-50 border border-gray-100 hover:border-indigo-200 p-3.5 rounded-xl text-left transition-all active:scale-[0.98] shadow-sm hover:shadow-md flex items-start gap-3"
            >
              <span className="text-xl mt-0.5 opacity-80 group-hover:opacity-100 flex-shrink-0">
                {TYPE_ICONS[choice.type]}
              </span>
              <div className="min-w-0">
                <span className="font-semibold text-gray-900 text-sm block leading-tight">
                  {choice.text}
                </span>
                <span className="text-gray-400 text-xs font-medium">
                  {TYPE_LABELS[choice.type]}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ResourceBar({
  value,
  color,
  icon,
  label,
}: {
  value: number;
  color: string;
  icon: string;
  label: string;
}) {
  return (
    <div className="bg-gray-50 rounded-xl p-2.5 border border-gray-100">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1">
          <span className="text-sm">{icon}</span>
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-tight">
            {label}
          </span>
        </div>
        <span className="text-xs font-bold text-gray-800">{value}%</span>
      </div>
      <div className="w-full bg-gray-200 h-1.5 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function ResultsView({
  result,
  onReset,
  businessName,
}: {
  result: QuizResult;
  onReset: () => void;
  businessName?: string;
}) {
  const scoreColor =
    result.score >= 70
      ? "text-emerald-600"
      : result.score >= 40
        ? "text-blue-600"
        : "text-amber-600";
  const scoreBg =
    result.score >= 70
      ? "from-emerald-500 to-teal-500"
      : result.score >= 40
        ? "from-blue-500 to-indigo-500"
        : "from-amber-500 to-orange-500";

  return (
    <div className="w-full h-full overflow-y-auto px-4 py-4">
      <div className="max-w-sm mx-auto text-center">
        {/* Score ring */}
        <div className="mb-4 animate-fade-in">
          <div
            className={`w-24 h-24 mx-auto rounded-full bg-gradient-to-br ${scoreBg} flex items-center justify-center shadow-lg`}
          >
            <div className="w-20 h-20 rounded-full bg-white flex items-center justify-center">
              <span className={`text-2xl font-black ${scoreColor}`}>
                {result.score}
              </span>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2 font-medium">
            {businessName ? `${businessName}'s AI Readiness` : 'AI Readiness Score'}
          </p>
        </div>

        {/* Archetype */}
        <div
          className="mb-4 animate-fade-in-up"
          style={{ animationDelay: "0.2s" }}
        >
          <p className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest mb-1">
            Your AI Persona
          </p>
          <h2 className="text-xl font-black text-gray-900">
            {result.archetype}
          </h2>
        </div>

        {/* Summary */}
        <div
          className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 mb-5 animate-fade-in-up"
          style={{ animationDelay: "0.35s" }}
        >
          <p className="text-sm text-gray-600 leading-relaxed">
            {result.summary}
          </p>
        </div>

        {/* CTA */}
        <div
          className="animate-fade-in-up"
          style={{ animationDelay: "0.5s" }}
        >
          <p className="text-xs text-gray-400 mb-3">
            Discovery is still running — try another activity or play again!
          </p>
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-indigo-50 border border-indigo-100 text-sm font-semibold text-indigo-600 hover:bg-indigo-100 transition-colors"
          >
            <RotateCcw size={14} />
            Play Again
          </button>
        </div>
      </div>
    </div>
  );
}
