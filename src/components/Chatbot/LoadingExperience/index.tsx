"use client";

import React, { useState } from "react";
import { ArrowLeft, Gamepad2, ClipboardList, Lightbulb } from "lucide-react";
import HephaeLogo from "@/components/HephaeLogo";
import { useRotatingMessage } from "@/components/Chatbot/DiscoveryProgress";
import AgentTimeline from "./AgentTimeline";
import DataStreamGame from "./DataStreamGame";
import HephaeExplainer from "./HephaeExplainer";
import AIReadinessQuiz from "./AIReadinessQuiz";
import { NeuralBackground } from "@/components/Chatbot/NeuralBackground";
import { CAPABILITY_CONFIGS, GENERIC_QUOTES } from "./loadingConfig";

type Activity = "menu" | "game" | "quiz" | "learn";

const ACTIVITIES = [
  {
    id: "game" as const,
    icon: Gamepad2,
    title: "Play a Game",
    description: "Catch data streams while our agents work",
    gradient: "from-indigo-500 to-purple-500",
    hoverBorder: "hover:border-indigo-300",
    iconBg: "bg-indigo-100",
    iconColor: "text-indigo-600",
  },
  {
    id: "quiz" as const,
    icon: ClipboardList,
    title: "AI Readiness Quiz",
    description: "See how ready your business is for AI",
    gradient: "from-blue-500 to-cyan-500",
    hoverBorder: "hover:border-blue-300",
    iconBg: "bg-blue-100",
    iconColor: "text-blue-600",
  },
  {
    id: "learn" as const,
    icon: Lightbulb,
    title: "How Hephae Works",
    description: "Learn what our AI agents do for you",
    gradient: "from-emerald-500 to-teal-500",
    hoverBorder: "hover:border-emerald-300",
    iconBg: "bg-emerald-100",
    iconColor: "text-emerald-600",
  },
];

interface LoadingOverlayProps {
  capabilityId: string | null;
  startTime: number | null;
  businessName?: string;
  businessLogo?: string;
}

export default function LoadingOverlay({
  capabilityId,
  startTime,
  businessName,
  businessLogo,
}: LoadingOverlayProps) {
  const config = capabilityId ? CAPABILITY_CONFIGS[capabilityId] : null;
  const quotes = config?.quotes ?? GENERIC_QUOTES;
  const { message: quote, visible: quoteVisible } = useRotatingMessage(quotes, 4000, true);
  const [activity, setActivity] = useState<Activity>("menu");

  return (
    <div className="absolute inset-0 z-[60] bg-white/95 backdrop-blur-sm flex flex-col overflow-hidden">
      {/* Background: only show game canvas when game is active */}
      {activity === "game" && (
        <div className="absolute inset-0">
          <DataStreamGame active={true} accentColor={config?.accentHex || "#0052CC"} />
        </div>
      )}

      {/* Neural background animation for menu/quiz/learn */}
      {activity !== "game" && (
        <div className="absolute inset-0 pointer-events-none opacity-[0.20]">
          <NeuralBackground />
        </div>
      )}

      {/* Content overlay — pointer-events-none in game mode so clicks reach the canvas */}
      <div className={`relative z-10 flex flex-col h-full ${activity === "game" ? "pointer-events-none" : ""}`}>
        {/* Top: header + timeline (always visible) */}
        <div className="flex-shrink-0 px-4 pt-4 pb-2">
          <div className="bg-white/90 backdrop-blur-md rounded-2xl shadow-lg border border-gray-100 px-5 py-4 max-w-md mx-auto">
            {/* Header row */}
            <div className="flex items-center gap-3 mb-3">
              <div className="relative w-12 h-12 flex-shrink-0 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-[3px] border-[#0052CC]/10 animate-pulse" />
                <div
                  className="absolute inset-0.5 rounded-full border-[1.5px] border-[#00C2FF]/30 animate-spin"
                  style={{ animationDuration: "3s" }}
                />
                {businessLogo ? (
                  <img src={businessLogo} className="w-7 h-7 rounded-full object-cover" alt="" />
                ) : (
                  <HephaeLogo size="xs" variant="color" showWordmark={false} />
                )}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-bold text-gray-900 truncate">
                  {businessName || "Analyzing..."}
                </div>
                <div
                  className="text-xs font-semibold tracking-wide"
                  style={{ color: config?.accentHex || "#4f46e5" }}
                >
                  {config ? `Running ${config.label}...` : "Deep analysis in progress..."}
                </div>
              </div>
            </div>

            {/* Timeline */}
            {config ? (
              <AgentTimeline
                stages={config.stages}
                startTime={startTime}
                estimatedDurationMs={config.estimatedDurationMs}
                accentHex={config.accentHex}
              />
            ) : (
              <div className="flex items-center gap-3 py-2">
                <div className="w-6 h-6 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-gray-500">Processing...</p>
              </div>
            )}
          </div>
        </div>

        {/* Back button (when in an activity) */}
        {activity !== "menu" && (
          <div className="flex-shrink-0 px-4 pt-2 pointer-events-auto">
            <button
              onClick={() => setActivity("menu")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/90 backdrop-blur-sm shadow-md border border-gray-200 text-sm font-medium text-gray-600 hover:bg-white transition-colors"
            >
              <ArrowLeft size={14} />
              Back
            </button>
          </div>
        )}

        {/* Main content area */}
        <div className="flex-1 min-h-0 flex flex-col">
          {/* ===== MENU: 3 activity cards ===== */}
          {activity === "menu" && (
            <div className="flex-1 flex flex-col items-center justify-center px-4">
              {/* Expectation-setting text */}
              <div className="text-center mb-6 animate-fade-in">
                <p className="text-base font-bold text-gray-800">
                  Our AI agents are deep-diving your business
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  This usually takes 2–3 minutes. Pick something to do while you wait!
                </p>
              </div>

              {/* Activity cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg w-full">
                {ACTIVITIES.map((act, i) => {
                  const Icon = act.icon;
                  return (
                    <button
                      key={act.id}
                      onClick={() => setActivity(act.id)}
                      className={`group p-4 rounded-2xl bg-white border border-gray-100 ${act.hoverBorder} shadow-sm hover:shadow-lg transition-all hover:scale-[1.03] text-left animate-fade-in-up`}
                      style={{ animationDelay: `${0.2 + i * 0.1}s` }}
                    >
                      {/* Icon area */}
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${act.gradient} flex items-center justify-center mb-3 shadow-sm group-hover:scale-110 transition-transform`}>
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <h3 className="text-sm font-bold text-gray-900 mb-1">
                        {act.title}
                      </h3>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        {act.description}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ===== GAME: DataStreamGame ===== */}
          {activity === "game" && (
            <div className="flex-1 flex flex-col pointer-events-none">
              <div className="flex-shrink-0 px-4 pt-2 pb-1">
                <div className="text-center">
                  <p className="text-sm font-semibold text-gray-600">
                    Tap the glowing dots! 👆
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Purple = 50 pts &middot; Green = 25 pts &middot; Blue = 10 pts
                  </p>
                </div>
              </div>
              {/* Game canvas fills remaining space — rendered in the absolute background above */}
              <div className="flex-1" />
            </div>
          )}

          {/* ===== QUIZ: Native AI Readiness Quiz ===== */}
          {activity === "quiz" && (
            <div className="flex-1 min-h-0 overflow-hidden">
              <AIReadinessQuiz />
            </div>
          )}

          {/* ===== LEARN: HephaeExplainer ===== */}
          {activity === "learn" && (
            <div className="flex-1 min-h-0 overflow-hidden">
              <HephaeExplainer />
            </div>
          )}
        </div>

        {/* Bottom: rotating quote + bouncing dots (visible on menu and game) */}
        {(activity === "menu" || activity === "game") && (
          <div className={`flex-shrink-0 pb-4 px-4 ${activity === "game" ? "pointer-events-none" : ""}`}>
            <div className="bg-white/85 backdrop-blur-sm rounded-xl px-4 py-3 max-w-lg mx-auto text-center shadow-sm border border-gray-100/80">
              <div
                className="text-sm font-medium text-gray-500 leading-relaxed italic transition-opacity duration-500"
                style={{ opacity: quoteVisible ? 1 : 0 }}
              >
                &ldquo;{quote}&rdquo;
              </div>
              <div className="flex gap-1.5 justify-center mt-2">
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }} />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
