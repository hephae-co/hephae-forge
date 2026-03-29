"use client";

import { useState, useEffect } from "react";
import {
  X,
  Database,
  Sparkles,
  BrainCircuit,
  Radio,
  MapPin,
  BarChart3,
  Bookmark,
  ArrowRight,
  Lock,
  Cpu,
} from "lucide-react";

interface DashboardData {
  confirmedSources?: number;
  aiTools?: unknown[];
  topInsights?: unknown[];
  coverage?: string;
}

interface StoryContext {
  isUltralocal: boolean;
  isAuthenticated: boolean;
  hasInsights: boolean;
  hasAiTools: boolean;
  confirmedSources: number;
}

interface StoryCard {
  id: string;
  Icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  headline: string;
  description: string;
  cta?: {
    label: string;
    action: "nominate" | "profile" | "heartbeat" | "signin";
  };
  showWhen: (ctx: StoryContext) => boolean;
}

const CARDS: StoryCard[] = [
  {
    id: "national_signals",
    Icon: Database,
    iconColor: "text-sky-400",
    iconBg: "bg-sky-400/15",
    headline: "15+ Federal Data Sources",
    description:
      "BLS prices, USDA commodity costs, FDA recalls, Census demographics, NWS weather — all cross-referenced automatically for this location.",
    showWhen: () => true,
  },
  {
    id: "industry_intel",
    Icon: Sparkles,
    iconColor: "text-violet-400",
    iconBg: "bg-violet-400/15",
    headline: "Weekly Industry AI Scout",
    description:
      "Every week, AI agents discover new tools, pricing shifts, and competitor moves specific to this industry.",
    showWhen: (ctx) => ctx.hasAiTools,
  },
  {
    id: "agentic_synthesis",
    Icon: BrainCircuit,
    iconColor: "text-indigo-400",
    iconBg: "bg-indigo-400/15",
    headline: "Agentic Intelligence",
    description: `${
      "N"
    } specialized AI agents ran in parallel to produce the snapshot you see — economist, market scout, local analyst, and critic.`,
    showWhen: (ctx) => ctx.confirmedSources > 0,
  },
  {
    id: "ultralocal_active",
    Icon: Radio,
    iconColor: "text-emerald-400",
    iconBg: "bg-emerald-400/15",
    headline: "Ultra-Local Monitoring",
    description:
      "This zip is in our weekly pulse program — 17 signals tracked every Monday including events, permits, competitor moves, and trend shifts.",
    showWhen: (ctx) => ctx.isUltralocal,
  },
  {
    id: "ultralocal_nominate",
    Icon: MapPin,
    iconColor: "text-amber-400",
    iconBg: "bg-amber-400/15",
    headline: "Nominate This Zip",
    description:
      "Get weekly 17-signal monitoring for this area — local events, competitor alerts, regulatory notices, and trend shifts every Monday.",
    cta: { label: "Request monitoring", action: "nominate" },
    showWhen: (ctx) => !ctx.isUltralocal,
  },
  {
    id: "profile_deepdive",
    Icon: BarChart3,
    iconColor: "text-pink-400",
    iconBg: "bg-pink-400/15",
    headline: "Unlock Deep Analysis",
    description:
      "Build a business profile to run margin surgery, foot traffic forecasting, SEO audits, and competitive threat analysis.",
    cta: { label: "Build profile", action: "profile" },
    showWhen: (ctx) => ctx.isAuthenticated,
  },
  {
    id: "profile_guest",
    Icon: Lock,
    iconColor: "text-pink-400",
    iconBg: "bg-pink-400/15",
    headline: "Sign In for Deep Analysis",
    description:
      "Signed-in users unlock margin surgery, traffic forecasting, SEO audits, and competitive reports.",
    cta: { label: "Sign in free", action: "signin" },
    showWhen: (ctx) => !ctx.isAuthenticated,
  },
  {
    id: "weekly_pulse",
    Icon: Cpu,
    iconColor: "text-teal-400",
    iconBg: "bg-teal-400/15",
    headline: "Weekly Business Pulse",
    description:
      "Subscribe to get a weekly AI-generated intelligence brief for this business — price alerts, competitor moves, and local events.",
    cta: { label: "Subscribe free", action: "heartbeat" },
    showWhen: (ctx) => ctx.isAuthenticated,
  },
  {
    id: "long_term_memory",
    Icon: Bookmark,
    iconColor: "text-slate-400",
    iconBg: "bg-slate-400/15",
    headline: "Persistent Memory",
    description:
      "We track this business over time — every analysis adds to a growing picture so future conversations start smarter.",
    showWhen: (ctx) => ctx.isAuthenticated,
  },
];

interface IntelligenceStoryStripProps {
  dashboard: DashboardData | null;
  businessName: string;
  businessSlug?: string;
  zipCode?: string;
  isAuthenticated: boolean;
  onNominateZip?: () => void;
  onBuildProfile?: () => void;
  onHeartbeat?: () => void;
  onSignIn?: () => void;
}

export default function IntelligenceStoryStrip({
  dashboard,
  businessName,
  businessSlug,
  zipCode,
  isAuthenticated,
  onNominateZip,
  onBuildProfile,
  onHeartbeat,
  onSignIn,
}: IntelligenceStoryStripProps) {
  const [dismissed, setDismissed] = useState(false);
  const [dismissing, setDismissing] = useState(false);

  // Persist dismissal per business in sessionStorage
  const storageKey = `hephae_story_dismissed_${businessSlug ?? ""}`;

  useEffect(() => {
    if (typeof window !== "undefined" && sessionStorage.getItem(storageKey)) {
      setDismissed(true);
    }
  }, [storageKey]);

  if (!dashboard || dismissed) return null;

  const ctx: StoryContext = {
    isUltralocal: dashboard.coverage === "ultralocal",
    isAuthenticated,
    hasInsights: (dashboard.topInsights?.length ?? 0) > 0,
    hasAiTools: (dashboard.aiTools?.length ?? 0) > 0,
    confirmedSources: dashboard.confirmedSources ?? 0,
  };

  const visibleCards = CARDS.filter((c) => c.showWhen(ctx));

  const handleDismiss = () => {
    setDismissing(true);
    setTimeout(() => {
      setDismissed(true);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(storageKey, "1");
      }
    }, 300);
  };

  const handleCta = (action: NonNullable<StoryCard["cta"]>["action"]) => {
    if (action === "nominate") onNominateZip?.();
    else if (action === "profile") onBuildProfile?.();
    else if (action === "heartbeat") onHeartbeat?.();
    else if (action === "signin") onSignIn?.();
  };

  // Replace the "N" placeholder in the agentic synthesis card
  const getDescription = (card: StoryCard): string => {
    if (card.id === "agentic_synthesis") {
      return `${ctx.confirmedSources} specialized AI agents ran in parallel to produce the snapshot you see — economist, market scout, local analyst, and critic.`;
    }
    return card.description;
  };

  return (
    <div
      className={`px-3 py-2.5 border-b border-white/5 transition-all duration-300 ${
        dismissing ? "opacity-0 -translate-y-1" : "opacity-100 translate-y-0"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-indigo-500" />
          How This Intelligence Works
        </span>
        <button
          onClick={handleDismiss}
          className="w-5 h-5 rounded-full hover:bg-white/8 flex items-center justify-center text-slate-600 hover:text-slate-400 transition-colors"
          aria-label="Dismiss"
        >
          <X className="w-3 h-3" />
        </button>
      </div>

      {/* Scrollable card row */}
      <div className="flex gap-2 overflow-x-auto scrollbar-hide snap-x snap-mandatory pb-1">
        {visibleCards.map((card, i) => {
          const { Icon } = card;
          return (
            <div
              key={card.id}
              className="flex-shrink-0 w-[188px] bg-slate-800/60 backdrop-blur-sm border border-white/6 rounded-xl p-2.5 flex flex-col gap-1.5 snap-start animate-fade-in-up"
              style={{ animationDelay: `${i * 0.06}s`, animationFillMode: "both" }}
            >
              {/* Icon + headline */}
              <div className="flex items-start gap-2">
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${card.iconBg}`}
                >
                  <Icon className={`w-3 h-3 ${card.iconColor}`} />
                </div>
                <span className="text-[11px] font-bold text-white leading-tight">
                  {card.headline}
                </span>
              </div>

              {/* Description */}
              <p className="text-[10px] text-slate-400 leading-relaxed flex-1 line-clamp-3">
                {getDescription(card)}
              </p>

              {/* CTA */}
              {card.cta && (
                <button
                  onClick={() => handleCta(card.cta!.action)}
                  className={`mt-0.5 text-[10px] font-bold flex items-center gap-0.5 transition-colors ${card.iconColor} opacity-80 hover:opacity-100`}
                >
                  {card.cta.label}
                  <ArrowRight className="w-2.5 h-2.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Source count badge */}
      {ctx.confirmedSources > 0 && (
        <p className="text-[9px] text-slate-600 mt-1.5 flex items-center gap-1">
          <span className="w-1 h-1 rounded-full bg-emerald-500 inline-block" />
          {ctx.confirmedSources} verified data sources used for {businessName}
        </p>
      )}
    </div>
  );
}
