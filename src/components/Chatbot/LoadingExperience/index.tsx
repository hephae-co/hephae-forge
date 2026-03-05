"use client";

import React from "react";
import HephaeLogo from "@/components/HephaeLogo";
import { useRotatingMessage } from "@/components/Chatbot/DiscoveryProgress";
import AgentTimeline from "./AgentTimeline";
import DataStreamGame from "./DataStreamGame";
import { CAPABILITY_CONFIGS, GENERIC_QUOTES } from "./loadingConfig";

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

  return (
    <div className="absolute inset-0 z-[60] bg-white/95 backdrop-blur-sm flex flex-col overflow-hidden">
      {/* Data stream game fills entire background */}
      <div className="absolute inset-0">
        <DataStreamGame active={true} accentColor={config?.accentHex || "#0052CC"} />
      </div>

      {/* Content overlay — compact top bar + bottom quote */}
      <div className="relative z-10 flex flex-col h-full pointer-events-none">
        {/* Top section: header + timeline */}
        <div className="flex-shrink-0 px-4 pt-4 pb-2 pointer-events-auto">
          <div className="bg-white/90 backdrop-blur-md rounded-2xl shadow-lg border border-gray-100 px-5 py-4 max-w-md mx-auto">
            {/* Header: Logo ring + business name */}
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

            {/* Timeline — compact */}
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

        {/* Bottom: rotating quote + bouncing dots */}
        <div className="mt-auto flex-shrink-0 pb-4 px-4">
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
      </div>
    </div>
  );
}
