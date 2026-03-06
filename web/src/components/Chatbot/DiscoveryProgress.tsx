"use client";

import React, { useState, useEffect } from 'react';

// ─── Discovery phase messages ────────────────────────────────────────────────
// Grouped by phase so they can be used independently (e.g. per-tab in MapVisualizer)
// or as a flat rotating list (e.g. in the chat sidebar or loading overlay).

export const DISCOVERY_PHASES = {
    general: [
        "Getting to know the business inside and out...",
        "Pulling up everything we can find online...",
        "Reading between the lines of their digital presence...",
        "Building a 360-degree view of the business...",
        "Cross-referencing public records and listings...",
        "Basically doing a background check — but for restaurants.",
    ],
    theme: [
        "Studying the brand identity and visual style...",
        "Extracting logo, colors, and brand personality...",
        "Figuring out the vibe — fine dining or fast casual?",
        "Checking if their brand tells the right story...",
        "Judging the font choices... we all do it.",
    ],
    contact: [
        "Hunting down phone, email, and hours...",
        "Checking Google, Yelp, and the website for contact info...",
        "Making sure we have the right phone number, not the fax...",
        "Verifying hours so no one shows up to a closed door...",
    ],
    social: [
        "Tracking down their social media profiles...",
        "Checking Instagram, Facebook, TikTok, Yelp...",
        "Seeing how active they are on social media...",
        "Looking for their digital footprint across platforms...",
        "Rating their Instagram game (no pressure)...",
    ],
    menu: [
        "Searching for their menu and online ordering links...",
        "Checking DoorDash, Grubhub, Uber Eats...",
        "Finding out where customers can order from...",
        "Menu hunting — the most delicious part of the job.",
    ],
    competitors: [
        "Scouting the neighborhood for direct competitors...",
        "Finding out who else is fighting for the same customers...",
        "Mapping the competitive landscape within a mile radius...",
        "Identifying the 3 biggest threats nearby...",
        "Spying on the competition — legally, of course.",
    ],
    overview: [
        "Generating an AI overview of the business...",
        "Summarizing everything the internet knows about them...",
        "Building a business intelligence brief...",
        "Compiling reputation signals and highlights...",
    ],
} as const;

// Flat list for general-purpose rotating display
export const ALL_DISCOVERY_MESSAGES = [
    ...DISCOVERY_PHASES.general,
    ...DISCOVERY_PHASES.theme,
    ...DISCOVERY_PHASES.social,
    ...DISCOVERY_PHASES.menu,
    ...DISCOVERY_PHASES.competitors,
    ...DISCOVERY_PHASES.contact,
    ...DISCOVERY_PHASES.overview,
];

// ─── Hook: useRotatingMessage ────────────────────────────────────────────────
// Returns a message string that rotates through the given array on an interval.
// Includes a visibility flag for crossfade animation.

export function useRotatingMessage(
    messages: readonly string[],
    intervalMs = 3500,
    active = true,
): { message: string; visible: boolean } {
    const [index, setIndex] = useState(0);
    const [visible, setVisible] = useState(true);

    useEffect(() => {
        if (!active) {
            setIndex(0);
            setVisible(true);
            return;
        }
        const timer = setInterval(() => {
            setVisible(false);
            setTimeout(() => {
                setIndex(i => (i + 1) % messages.length);
                setVisible(true);
            }, 350);
        }, intervalMs);
        return () => clearInterval(timer);
    }, [active, messages, intervalMs]);

    return { message: messages[index], visible };
}

// ─── Component: DiscoveryProgress ────────────────────────────────────────────
// Reusable loading indicator with rotating messages.
//
// Variants:
//   "dots"   — bouncing dots + message (for compact spaces like MapVisualizer tabs)
//   "inline" — spinner + message (for chat sidebar or headers)
//   "banner" — full-width card with icon (for prominent display)

interface DiscoveryProgressProps {
    /** Which phase messages to show, or "all" for the combined list */
    phase?: keyof typeof DISCOVERY_PHASES | 'all';
    /** Visual variant */
    variant?: 'dots' | 'inline' | 'banner';
    /** Whether to animate (set false to freeze) */
    active?: boolean;
    /** Override messages instead of using a phase */
    messages?: readonly string[];
    /** Rotation interval in ms (default 3500) */
    intervalMs?: number;
}

export default function DiscoveryProgress({
    phase = 'all',
    variant = 'dots',
    active = true,
    messages: customMessages,
    intervalMs = 3500,
}: DiscoveryProgressProps) {
    const msgs = customMessages || (phase === 'all' ? ALL_DISCOVERY_MESSAGES : DISCOVERY_PHASES[phase]);
    const { message, visible } = useRotatingMessage(msgs, intervalMs, active);

    if (variant === 'dots') {
        return (
            <div className="flex flex-col items-center justify-center h-full space-y-3 py-4">
                <div className="flex space-x-1">
                    <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <p
                    className="text-slate-400 text-sm text-center leading-relaxed transition-opacity duration-300 px-2"
                    style={{ opacity: visible ? 1 : 0 }}
                >
                    {message}
                </p>
            </div>
        );
    }

    if (variant === 'inline') {
        return (
            <p className="text-amber-400 text-xs font-medium tracking-wider animate-pulse flex items-center gap-1.5 mt-0.5">
                <svg className="w-3 h-3 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span
                    className="transition-opacity duration-300"
                    style={{ opacity: visible ? 1 : 0 }}
                >
                    {message}
                </span>
            </p>
        );
    }

    // variant === 'banner'
    return (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-indigo-50 border border-indigo-100">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-indigo-500 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
            </div>
            <p
                className="text-sm text-indigo-800 font-medium leading-relaxed transition-opacity duration-300"
                style={{ opacity: visible ? 1 : 0 }}
            >
                {message}
            </p>
        </div>
    );
}
