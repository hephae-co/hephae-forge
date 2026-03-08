"use client";

import React from "react";
import { Globe, Users, Share2, ShieldCheck, Zap, Search, BarChart3, Store, Newspaper, MapPin, TrendingUp, Target } from "lucide-react";

const PIPELINE_STEPS = [
  {
    icon: Globe,
    title: "Website Crawl",
    description: "Our SiteCrawler agent scans your website for menus, hours, delivery platforms, social links, and structured data.",
    color: "from-blue-500 to-cyan-500",
    borderColor: "border-blue-200",
    bgColor: "bg-blue-50",
  },
  {
    icon: Users,
    title: "7-Agent Research Team",
    description: "Seven specialized agents fan out in parallel — researching your brand theme, contact info, social profiles, menu, Google Maps listing, competitors, and news mentions.",
    color: "from-indigo-500 to-purple-500",
    borderColor: "border-indigo-200",
    bgColor: "bg-indigo-50",
    subAgents: [
      { icon: Store, label: "Theme" },
      { icon: Search, label: "Contact" },
      { icon: Share2, label: "Social" },
      { icon: BarChart3, label: "Menu" },
      { icon: MapPin, label: "Maps" },
      { icon: Target, label: "Competitors" },
      { icon: Newspaper, label: "News" },
    ],
  },
  {
    icon: TrendingUp,
    title: "Social Media Profiling",
    description: "We crawl your Instagram, Facebook, Twitter, TikTok, and Yelp profiles to measure follower counts, engagement rates, and posting frequency.",
    color: "from-pink-500 to-rose-500",
    borderColor: "border-pink-200",
    bgColor: "bg-pink-50",
  },
  {
    icon: ShieldCheck,
    title: "URL Validation",
    description: "Every discovered URL and data point is cross-referenced, validated with HTTP checks, and corrected via Google Search if invalid.",
    color: "from-emerald-500 to-teal-500",
    borderColor: "border-emerald-200",
    bgColor: "bg-emerald-50",
  },
  {
    icon: Zap,
    title: "Capabilities Unlocked",
    description: "Once complete, you can run Margin Surgery, Traffic Forecasts, SEO Deep Audits, Competitive Analysis, and Social Media Insights.",
    color: "from-amber-500 to-orange-500",
    borderColor: "border-amber-200",
    bgColor: "bg-amber-50",
  },
];

export default function HephaeExplainer() {
  return (
    <div className="w-full h-full overflow-y-auto px-6 py-4">
      <div className="max-w-md mx-auto">
        <h2 className="text-lg font-bold text-gray-900 mb-1 animate-fade-in">
          How Hephae Discovery Works
        </h2>
        <p className="text-sm text-gray-500 mb-6 animate-fade-in" style={{ animationDelay: "0.1s" }}>
          Our AI pipeline runs 4 stages to build a complete business profile.
        </p>

        <div className="relative">
          {/* Vertical connecting line */}
          <div className="absolute left-5 top-6 bottom-6 w-0.5 bg-gradient-to-b from-blue-200 via-purple-200 via-pink-200 via-emerald-200 to-amber-200" />

          <div className="space-y-5">
            {PIPELINE_STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <div
                  key={i}
                  className="relative flex gap-4 animate-fade-in-up"
                  style={{ animationDelay: `${0.15 + i * 0.12}s` }}
                >
                  {/* Icon circle */}
                  <div className={`relative z-10 flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br ${step.color} flex items-center justify-center shadow-md`}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>

                  {/* Content card */}
                  <div className={`flex-1 p-4 rounded-xl ${step.bgColor} border ${step.borderColor} shadow-sm`}>
                    <h3 className="font-bold text-gray-900 text-sm mb-1">{step.title}</h3>
                    <p className="text-xs text-gray-600 leading-relaxed">{step.description}</p>

                    {/* Sub-agent pills for the fan-out step */}
                    {step.subAgents && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {step.subAgents.map((sa, j) => {
                          const SaIcon = sa.icon;
                          return (
                            <span
                              key={j}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/80 border border-indigo-100 text-[10px] font-semibold text-indigo-600 animate-fade-in"
                              style={{ animationDelay: `${0.5 + j * 0.06}s` }}
                            >
                              <SaIcon className="w-2.5 h-2.5" />
                              {sa.label}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer badge */}
        <div className="mt-6 mb-4 text-center animate-fade-in" style={{ animationDelay: "1s" }}>
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 border border-gray-200 text-xs font-medium text-gray-500">
            Powered by Google ADK + Gemini
          </span>
        </div>
      </div>
    </div>
  );
}
