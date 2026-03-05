"use client";

import React from "react";
import BlobBackground from "@/components/BlobBackground";
import HephaeLogo from "@/components/HephaeLogo";
import { useRotatingMessage } from "@/components/Chatbot/DiscoveryProgress";
import AgentTimeline from "./AgentTimeline";
import BubblePopGame from "./BubblePopGame";
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
    <div className="absolute inset-0 z-20 bg-white/95 backdrop-blur-sm flex flex-col items-center justify-center p-6 sm:p-8 overflow-hidden">
      <BlobBackground className="opacity-10" />

      <div className="relative z-10 flex flex-col items-center gap-5 max-w-3xl w-full">
        {/* Header: Logo ring + business name */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="relative w-20 h-20 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-4 border-[#0052CC]/10 animate-pulse" />
            <div
              className="absolute inset-1 rounded-full border-2 border-[#00C2FF]/30 animate-spin"
              style={{ animationDuration: "3s" }}
            />
            {businessLogo ? (
              <img src={businessLogo} className="w-10 h-10 rounded-full object-cover" alt="" />
            ) : (
              <HephaeLogo size="sm" variant="color" showWordmark={false} />
            )}
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">
              {businessName || "Analyzing..."}
            </div>
            <div
              className="text-sm font-semibold tracking-wide"
              style={{ color: config?.accentHex || "#4f46e5" }}
            >
              {config ? `Running ${config.label}...` : "Deep analysis in progress..."}
            </div>
          </div>
        </div>

        {/* Main content: Timeline + Bubble Game */}
        <div className="flex flex-col sm:flex-row gap-6 w-full items-stretch min-h-[240px]">
          {/* Timeline */}
          <div className="flex-[55] flex flex-col justify-center">
            {config ? (
              <AgentTimeline
                stages={config.stages}
                startTime={startTime}
                estimatedDurationMs={config.estimatedDurationMs}
                accentHex={config.accentHex}
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-3">
                <div className="w-8 h-8 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-gray-500">Processing...</p>
              </div>
            )}
          </div>

          {/* Bubble Pop Game */}
          <div className="flex-[45] relative rounded-2xl overflow-hidden border border-gray-100 bg-gradient-to-b from-blue-50/50 to-white/30 min-h-[200px] sm:min-h-0">
            <BubblePopGame active={true} accentColor={config?.accentHex || "#0052CC"} />
          </div>
        </div>

        {/* Rotating quote */}
        <div
          className="text-base font-medium text-gray-500 leading-relaxed italic transition-opacity duration-500 text-center px-4 max-w-xl"
          style={{ opacity: quoteVisible ? 1 : 0 }}
        >
          &ldquo;{quote}&rdquo;
        </div>

        {/* Bouncing dots */}
        <div className="flex gap-2">
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }} />
          <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }} />
        </div>
      </div>
    </div>
  );
}
