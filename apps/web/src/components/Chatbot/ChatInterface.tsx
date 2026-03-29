"use client";

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChatMessage, SuggestionChip } from './types';
import { BaseIdentity } from '@/types/api';
import MarkdownRenderer from './MarkdownRenderer';
import BlobBackground from '@/components/BlobBackground';
import HephaeLogo from '@/components/HephaeLogo';
import { Bot, RefreshCcw, Info, BarChart3, Users, Search as SearchIcon, Swords, Share2, Sparkles, MapPin, Loader2, Lock, PanelRightClose, ChevronLeft, ChevronDown, Copy, Check, Lightbulb, ArrowRight } from 'lucide-react';
import ExplainerModal from './ExplainerModal';
import DiscoveryProgress, { ALL_DISCOVERY_MESSAGES, useRotatingMessage } from './DiscoveryProgress';
import { NeuralBackground } from './NeuralBackground';
import { usePlacesAutocomplete } from './usePlacesAutocomplete';
import type { PlacePrediction } from './usePlacesAutocomplete';
// OverviewCard removed — overview data renders on map panel + conversational message

// PlacePrediction type imported from usePlacesAutocomplete

interface ChatInterfaceProps {
    messages: ChatMessage[];
    onSendMessage: (text: string) => void;
    onPlaceSelect?: (identity: BaseIdentity) => void;
    isTyping: boolean;
    isDiscovering?: boolean;
    onReset: () => void;
    capabilities?: { id: string; label: string; icon?: React.ReactNode }[];
    onSelectCapability?: (id: string) => void;
    capabilitiesLocked?: boolean;
    isCentered?: boolean;
    followUpChips?: SuggestionChip[];
    isCollapsed?: boolean;
    onToggleCollapse?: () => void;
    addMyAreaCity?: string | null;
    onAddMyArea?: () => void;
    authUser?: { displayName?: string | null; email?: string | null; photoURL?: string | null } | null;
    onSignIn?: () => void;
    onSignOut?: () => void;
    lightMode?: boolean;
    profileBuildingMode?: boolean;
    profileChips?: { label: string; value: string }[];
}

// Skip autocomplete for inputs that are clearly chat messages
const CHAT_PREFIXES = /^(what|how|why|can |tell|show|run |analyze|help|which|when|where|is |are |do |does|explain|compare|generate|create|my |the |a |an |i |we |it |this |hey|hi |hello|thank|please|ok |yes|no |none|nope|nah|sure|give|skip|done|finish|don't|i don't|n\/a)/i;

const shouldAutocomplete = (text: string): boolean => {
    const trimmed = text.trim();
    if (trimmed.length < 3) return false;
    if (CHAT_PREFIXES.test(trimmed)) return false;
    return true;
};

const LOADING_QUOTES = [
    // Data-driven insights
    "A 1% drop in food costs has 3× the profit impact of a 1% revenue bump.",
    "The top 20% of menu items typically drive 70% of revenue.",
    "Egg prices rose over 60% in two years — we're mapping that to your menu.",
    "The average restaurant runs on just 3–5% net profit. Every dollar counts.",
    "73% of diners check a restaurant online before their first visit.",
    "Online ordering boosts average check size by 20–30%.",
    "Proximity to event venues can boost weeknight traffic by up to 25%.",
    // Humorous / engaging
    "Crunching numbers harder than a kitchen crunch rush...",
    "Teaching AI to appreciate good food — it's a process.",
    "If this analysis were a steak, it'd be well-seasoned and medium-rare.",
    "Checking if their competitors are sweating yet...",
    "Our AI doesn't eat, but it has strong opinions about your menu prices.",
    "Running more calculations than a waiter splitting a 12-person check.",
    "Scanning the internet faster than a foodie scrolling Instagram.",
    "No restaurants were harmed in the making of this report.",
    "Doing the math your accountant wishes they could do this fast.",
    "Hold tight — genius takes a minute. Mediocrity is instant.",
];

/** Typewriter effect — renders text character by character */
const TypewriterText: React.FC<{ text: string; speed?: number }> = ({ text, speed = 35 }) => {
    const [displayed, setDisplayed] = useState('');
    const [done, setDone] = useState(false);

    useEffect(() => {
        setDisplayed('');
        setDone(false);
        let i = 0;
        const timer = setInterval(() => {
            i++;
            setDisplayed(text.slice(0, i));
            if (i >= text.length) {
                clearInterval(timer);
                setDone(true);
            }
        }, speed);
        return () => clearInterval(timer);
    }, [text, speed]);

    const lines = displayed.split('\n');
    return (
        <span>
            {lines.map((line, i) => (
                <React.Fragment key={i}>
                    {i > 0 && <br />}
                    {line}
                </React.Fragment>
            ))}
            {!done && <span className="inline-block w-0.5 h-5 bg-gray-400 align-middle ml-0.5 animate-pulse" />}
        </span>
    );
};

const ChatInterface: React.FC<ChatInterfaceProps> = ({
    messages,
    onSendMessage,
    onPlaceSelect,
    isTyping,
    isDiscovering = false,
    onReset,
    capabilities = [],
    onSelectCapability,
    capabilitiesLocked = false,
    isCentered = false,
    followUpChips = [],
    isCollapsed = false,
    onToggleCollapse,
    addMyAreaCity = null,
    onAddMyArea,
    authUser = null,
    onSignIn,
    onSignOut,
    lightMode = false,
    profileBuildingMode = false,
    profileChips = [],
}) => {
    const [input, setInput] = useState('');
    const [isExplainerOpen, setIsExplainerOpen] = useState(false);
    const [showAuthMenu, setShowAuthMenu] = useState(false);
    const [quoteIndex, setQuoteIndex] = useState(0);
    const [quoteVisible, setQuoteVisible] = useState(true);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Autocomplete state (client-side Google Maps JS API)
    const { predictions, fetchPredictions, getPlaceDetails, clearPredictions } = usePlacesAutocomplete();
    const [showDropdown, setShowDropdown] = useState(false);
    const [selectedIdx, setSelectedIdx] = useState(-1);
    const [isResolving, setIsResolving] = useState(false);
    const debounceRef = useRef<NodeJS.Timeout>(undefined);
    const dropdownRef = useRef<HTMLFormElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Scroll-to-bottom & copy state
    const [showScrollBtn, setShowScrollBtn] = useState(false);
    const [copiedId, setCopiedId] = useState<string | null>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        setShowScrollBtn(false);
    };

    const handleScroll = useCallback(() => {
        const el = scrollContainerRef.current;
        if (!el) return;
        const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
        setShowScrollBtn(distFromBottom > 120);
    }, []);

    useEffect(() => {
        if (!showScrollBtn) scrollToBottom();
    }, [messages, isTyping, isDiscovering, capabilities]);

    // Cycle quotes while loading
    useEffect(() => {
        if (!isTyping) {
            setQuoteIndex(0);
            setQuoteVisible(true);
            return;
        }
        const interval = setInterval(() => {
            setQuoteVisible(false);
            setTimeout(() => {
                setQuoteIndex(i => (i + 1) % LOADING_QUOTES.length);
                setQuoteVisible(true);
            }, 300);
        }, 3800);
        return () => clearInterval(interval);
    }, [isTyping]);

    // Debounced Places Autocomplete (client-side Google Maps JS API)
    useEffect(() => {
        // Disable autocomplete entirely during profile building
        if (profileBuildingMode) {
            clearPredictions();
            setShowDropdown(false);
            return;
        }

        const shouldFetch = isCentered
            ? input.trim().length >= 3
            : shouldAutocomplete(input);

        if (!shouldFetch) {
            clearPredictions();
            setShowDropdown(false);
            return;
        }

        clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            fetchPredictions(input);
        }, 300);

        return () => clearTimeout(debounceRef.current);
    }, [input, isCentered, fetchPredictions, clearPredictions]);

    // Show/hide dropdown when predictions change
    useEffect(() => {
        setShowDropdown(predictions.length > 0);
        setSelectedIdx(-1);
    }, [predictions]);

    // Click outside to close dropdown
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    // Resolve a place prediction into a full identity (client-side Google Maps API)
    const handlePredictionSelect = useCallback(async (prediction: PlacePrediction) => {
        setShowDropdown(false);
        clearPredictions();
        setInput(prediction.mainText);

        if (!onPlaceSelect) {
            onSendMessage(prediction.description);
            setInput('');
            return;
        }

        setIsResolving(true);
        try {
            const details = await getPlaceDetails(prediction.placeId);
            if (details) {
                setInput('');
                onPlaceSelect({
                    name: details.name,
                    address: details.address,
                    officialUrl: details.officialUrl || '',
                    coordinates: details.coordinates || undefined,
                    zipCode: details.zipCode || '',
                } as any);
            } else {
                onSendMessage(prediction.description);
                setInput('');
            }
        } catch {
            onSendMessage(prediction.description);
            setInput('');
        } finally {
            setIsResolving(false);
        }
    }, [onPlaceSelect, onSendMessage, getPlaceDetails, clearPredictions]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        // If a prediction is highlighted, select it
        if (showDropdown && selectedIdx >= 0 && predictions[selectedIdx]) {
            handlePredictionSelect(predictions[selectedIdx]);
            return;
        }

        // In search mode: if predictions visible, auto-select the first one
        if (isCentered && showDropdown && predictions.length > 0) {
            handlePredictionSelect(predictions[0]);
            return;
        }

        // Otherwise send as regular message (text-search fallback in search mode, normal chat in chat mode)
        setShowDropdown(false);
        clearPredictions();
        if (!input.trim() || isTyping || isResolving) return;
        onSendMessage(input);
        setInput('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (!showDropdown || predictions.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setSelectedIdx(prev => Math.min(prev + 1, predictions.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setSelectedIdx(prev => Math.max(prev - 1, -1));
        } else if (e.key === 'Escape') {
            setShowDropdown(false);
            setSelectedIdx(-1);
        }
    };

    const isInputDisabled = isTyping || isResolving || isDiscovering;

    // Collapsed sliver mode
    if (isCollapsed && !isCentered) {
        return (
            <div className="flex flex-col h-full bg-gradient-to-b from-slate-800 to-slate-900 items-center justify-center w-full relative z-30">
                <button
                    onClick={onToggleCollapse}
                    className="p-3 text-white/70 hover:text-white hover:bg-white/15 rounded-xl transition-all group"
                    title="Open Chat"
                >
                    <ChevronLeft className="w-5 h-5 transition-transform group-hover:-translate-x-0.5" />
                </button>
                <div className="mt-4">
                    <span
                        className="text-[9px] font-bold text-white/40 uppercase tracking-widest"
                        style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
                    >
                        Chat
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className={`flex flex-col h-full relative z-30 transition-all duration-700 w-full ${!isCentered ? (lightMode ? 'bg-[#f0eef8]' : 'bg-slate-900 border-l border-white/8') : 'bg-transparent justify-center items-center pointer-events-none'}`}>

            {/* Header - Hidden when centered */}
            {!isCentered && (
                <div className={`px-4 py-3 flex justify-between items-center z-10 flex-shrink-0 ${lightMode ? 'bg-white/80 backdrop-blur-sm border-b border-purple-100/60' : 'bg-gradient-to-r from-slate-800 via-slate-800 to-slate-900'}`}>
                    <div className="flex items-center gap-2">
                        {onToggleCollapse && (
                            <button
                                onClick={onToggleCollapse}
                                className="p-1.5 -ml-1 text-white/50 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                title="Hide Chat"
                            >
                                <PanelRightClose className="w-4 h-4" />
                            </button>
                        )}
                        <button
                            onClick={onReset}
                            className={`p-1.5 rounded-lg transition-colors ${lightMode ? 'text-slate-400 hover:text-slate-700 hover:bg-purple-50' : 'text-white/50 hover:text-white hover:bg-white/10'}`}
                            title="Start Over"
                        >
                            <RefreshCcw className="w-4 h-4" />
                        </button>
                        <span className={`w-px h-4 block ${lightMode ? 'bg-purple-200' : 'bg-white/15'}`} />
                        <HephaeLogo size="sm" variant={lightMode ? "color" : "white"} />
                        <p className={`text-[10px] font-semibold tracking-wider uppercase hidden md:block ${lightMode ? 'text-purple-400' : 'text-white/40'}`}>AI Concierge</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.9)] animate-pulse"></div>
                            <span className="text-[10px] text-white/40 font-medium">Live</span>
                        </div>
                        {/* Auth indicator in header */}
                        {authUser ? (
                            <div className="relative">
                                <button
                                    onClick={() => setShowAuthMenu(v => !v)}
                                    className="flex items-center gap-1.5 pl-1.5 pr-2 py-1 rounded-full bg-white/8 hover:bg-white/15 border border-white/10 transition-all"
                                >
                                    {authUser.photoURL ? (
                                        <img src={authUser.photoURL} alt="" className="w-5 h-5 rounded-full" referrerPolicy="no-referrer" />
                                    ) : (
                                        <div className="w-5 h-5 rounded-full bg-indigo-500/40 flex items-center justify-center">
                                            <span className="text-[9px] font-bold text-indigo-200">{authUser.displayName?.[0] || authUser.email?.[0] || '?'}</span>
                                        </div>
                                    )}
                                    <span className="text-[10px] text-white/60 hidden sm:block max-w-[80px] truncate">{authUser.displayName || authUser.email?.split('@')[0]}</span>
                                </button>
                                {showAuthMenu && (
                                    <>
                                        <div className="fixed inset-0 z-[49]" onClick={() => setShowAuthMenu(false)} />
                                        <div className="absolute right-0 top-full mt-1.5 w-44 bg-slate-800 rounded-xl shadow-xl border border-white/10 py-1 z-50">
                                            <div className="px-3 py-1.5 border-b border-white/8">
                                                <p className="text-xs font-medium text-white/80 truncate">{authUser.displayName}</p>
                                                <p className="text-[10px] text-white/40 truncate">{authUser.email}</p>
                                            </div>
                                            <button
                                                onClick={() => { setShowAuthMenu(false); onSignOut?.(); }}
                                                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-white/60 hover:text-white hover:bg-white/8 transition-colors"
                                            >
                                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
                                                Sign out
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        ) : (
                            <button
                                onClick={onSignIn}
                                className="px-2.5 py-1 rounded-full bg-indigo-500/20 hover:bg-indigo-500/35 border border-indigo-400/20 text-[10px] font-semibold text-indigo-300 transition-all"
                            >
                                Sign in
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Messages Area */}
            <div
                ref={scrollContainerRef}
                onScroll={handleScroll}
                className={`relative overflow-y-auto p-4 flex flex-col w-full ${isCentered ? 'items-center max-w-3xl flex-none space-y-6 pointer-events-none' : `flex-grow space-y-4 pointer-events-auto ${lightMode ? 'bg-transparent' : 'bg-slate-900'}`}`}
            >
                {!isCentered && <BlobBackground className="opacity-15" />}
                {!isCentered && (isDiscovering || isTyping) && (
                    <div className="absolute inset-0 opacity-20 pointer-events-none z-0">
                        <NeuralBackground />
                    </div>
                )}
                <div className={`w-full ${isCentered ? 'space-y-8' : 'space-y-5'}`}>

                    {/* Home screen: Hephae logo + tagline + intro text */}
                    {isCentered && (
                        <div className="flex flex-col items-center gap-3 pt-8 pb-2 animate-fade-in-up">
                            <HephaeLogo size="lg" variant="color" />
                            <p className="text-slate-500 text-sm font-medium tracking-wide mt-1">Big AI for small businesses</p>
                            <p className="text-slate-400 text-sm text-center max-w-md leading-relaxed mt-2">
                                Free weekly intelligence for local businesses. Search for your business below — we&apos;ll analyze your market, pricing, foot traffic, and competitive landscape using 12+ verified data sources.
                            </p>
                        </div>
                    )}


                    {messages.map((msg, idx) => {
                        const isWelcome = isCentered && msg.role === 'model' && msg.id === '1';
                        return (
                        <div
                            key={msg.id}
                            className={`flex animate-fade-in-up ${isWelcome ? 'justify-center' : msg.role === 'user' ? 'justify-end' : 'justify-start items-end gap-2'}`}
                            style={{ animationDelay: `${Math.min(idx * 0.04, 0.24)}s` }}
                        >

                            {/* Bot avatar for AI messages */}
                            {msg.role === 'model' && !isCentered && (
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mb-0.5 shadow-sm ${lightMode ? 'bg-gradient-to-br from-purple-100 to-violet-100 border border-purple-200/60' : 'bg-gradient-to-br from-indigo-900/50 to-violet-900/50 border border-indigo-500/25'}`}>
                                    <Bot className={`w-3.5 h-3.5 ${lightMode ? 'text-purple-600' : 'text-indigo-400'}`} />
                                </div>
                            )}

                            <div className="flex flex-col">
                                <div style={{ overflowWrap: 'anywhere', wordBreak: 'break-word' }} className={`group relative p-3.5 rounded-2xl ${
                                    isWelcome
                                        ? 'text-2xl font-light text-center p-6 bg-transparent border-none shadow-none ring-0 text-slate-700 max-w-full'
                                        : msg.role === 'user'
                                            ? `max-w-[82%] rounded-br-md shadow-md ${lightMode ? 'bg-purple-600 text-white shadow-purple-200/40' : 'bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-indigo-200/40'}`
                                            : `max-w-[88%] rounded-bl-md shadow-sm ${lightMode ? 'bg-white text-slate-700 border border-purple-100/60 shadow-purple-900/5' : 'bg-slate-800/80 text-white/88 border border-white/8'}`
                                }`}>
                                    {isWelcome ? (
                                        <TypewriterText text={msg.text} />
                                    ) : msg.role === 'model' ? (
                                        <MarkdownRenderer content={msg.text} />
                                    ) : (
                                        <div className="text-sm leading-relaxed">{msg.text}</div>
                                    )}

                                    {/* Copy button on bot messages */}
                                    {!isWelcome && msg.role === 'model' && !isCentered && (
                                        <button
                                            onClick={() => {
                                                navigator.clipboard.writeText(msg.text);
                                                setCopiedId(msg.id);
                                                setTimeout(() => setCopiedId(null), 2000);
                                            }}
                                            className="absolute -bottom-2 right-2 opacity-60 md:opacity-0 md:group-hover:opacity-100 transition-opacity p-2 md:p-1.5 bg-slate-700 border border-white/10 rounded-lg shadow-sm hover:bg-slate-600 text-white/40 hover:text-white/70"
                                            title="Copy message"
                                        >
                                            {copiedId === msg.id
                                                ? <Check className="w-3 h-3 text-emerald-500" />
                                                : <Copy className="w-3 h-3" />
                                            }
                                        </button>
                                    )}
                                </div>

                                {/* Timestamp */}
                                {!isWelcome && msg.createdAt && !isCentered && (
                                    <div className={`text-[10px] text-white/30 mt-1 px-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                                        {new Date(msg.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </div>
                                )}
                            </div>
                        </div>
                    );})}

                    {/* Home Screen Capabilities UI */}
                    {isCentered && messages.length === 1 && (
                        <div className="w-full mt-12 mb-8 animate-fade-in-up">
                            <div className="text-center mb-6">
                                <h2 className="text-xl font-black text-slate-800 tracking-tight">What We Can Do For You</h2>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
                                {([
                                    { icon: <BarChart3 className="w-3.5 h-3.5" />, label: "Optimize My Prices", cls: "bg-indigo-50 text-indigo-600" },
                                    { icon: <Users className="w-3.5 h-3.5" />, label: "Predict Foot Traffic", cls: "bg-emerald-50 text-emerald-600" },
                                    { icon: <SearchIcon className="w-3.5 h-3.5" />, label: "Check My Google Presence", cls: "bg-purple-50 text-purple-600" },
                                    { icon: <Swords className="w-3.5 h-3.5" />, label: "Compare to Competitors", cls: "bg-orange-50 text-orange-600" },
                                    { icon: <Share2 className="w-3.5 h-3.5" />, label: "Audit My Social Media", cls: "bg-pink-50 text-pink-600" },
                                ] as const).map(({ icon, label, cls }) => (
                                    <div key={label}
                                        className="bg-white/80 border border-purple-100 px-3 py-2.5 rounded-xl shadow-sm shadow-purple-900/5 backdrop-blur-xl flex items-center gap-2.5 text-left hover:shadow-md hover:border-purple-200 transition-all">
                                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${cls}`}>
                                            {icon}
                                        </div>
                                        <span className="text-xs font-semibold text-slate-700 leading-tight">{label}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Capability Buttons */}
                    {capabilities.length > 0 && !isTyping && (
                        <div className="flex justify-start animate-fade-in-up mt-2 pl-9">
                            <div className="flex flex-col gap-2 w-full">
                                <div className="flex items-center justify-between px-1 mb-1">
                                    <div className="flex items-center gap-1.5">
                                        <Sparkles className="w-3 h-3 text-indigo-500" />
                                        <p className="text-xs font-bold text-white/40 uppercase tracking-wider">What to explore next</p>
                                    </div>
                                    <button
                                        onClick={() => setIsExplainerOpen(true)}
                                        className="flex items-center gap-1 text-[10px] font-bold text-indigo-400 bg-indigo-500/15 px-2 py-1 rounded-md hover:bg-indigo-500/25 transition-colors"
                                    >
                                        <Info className="w-3 h-3" />
                                        How this works
                                    </button>
                                </div>
                                {capabilities.map((cap, i) => (
                                    <button
                                        key={cap.id}
                                        onClick={() => onSelectCapability && onSelectCapability(cap.id)}
                                        className={`flex items-center gap-3 px-4 py-3.5 border shadow-sm rounded-2xl text-sm font-semibold text-left animate-fade-in-up transition-all ${
                                            lightMode
                                                ? (capabilitiesLocked
                                                    ? 'bg-white border-slate-200 text-slate-400 cursor-pointer hover:bg-purple-50'
                                                    : 'bg-white border-purple-200 text-purple-700 hover:bg-purple-50 hover:border-purple-300 hover:-translate-y-0.5 hover:shadow-md hover:shadow-purple-200/50')
                                                : (capabilitiesLocked
                                                    ? 'bg-slate-800 border-white/8 text-white/30 cursor-pointer hover:bg-slate-700'
                                                    : 'bg-slate-800 border-indigo-500/20 text-indigo-300 hover:bg-indigo-500/10 hover:border-indigo-400/30 hover:-translate-y-0.5 hover:shadow-md hover:shadow-indigo-900/50')
                                        }`}
                                        style={{ animationDelay: `${0.06 + i * 0.07}s` }}
                                    >
                                        {capabilitiesLocked ? <Lock className="w-4 h-4 text-gray-400" /> : cap.icon}
                                        {cap.label}
                                        {capabilitiesLocked && <span className="ml-auto text-xs text-gray-400">Sign in</span>}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Discovery indicator — minimal in chat, main progress is on the map overlay */}
                    {isDiscovering && !isTyping && (
                        <div className="flex justify-start items-end gap-2 animate-fade-in-up">
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center flex-shrink-0 mb-0.5 border border-indigo-200/60 shadow-sm">
                                <Bot className="w-3.5 h-3.5 text-indigo-600" />
                            </div>
                            <div className="bg-slate-800 border border-white/8 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
                                <p className="text-sm text-white/80 font-medium">Deep discovery in progress — watch the map for live updates.</p>
                            </div>
                        </div>
                    )}

                    {/* Loading indicator — centered card on home, bot bubble in chat */}
                    {isTyping && isCentered && (
                        <div className="flex justify-center pointer-events-auto animate-fade-in-up">
                            <div className="bg-white/90 backdrop-blur-md rounded-2xl px-6 py-5 shadow-xl shadow-purple-900/10 border border-purple-100 max-w-sm">
                                <p className="text-sm font-bold text-slate-800 mb-3">Locating your business...</p>
                                <div className="space-y-2">
                                    {[
                                        { icon: "🔍", text: "7 AI agents mapping your digital presence" },
                                        { icon: "📊", text: "Menu, pricing & competitor benchmarks" },
                                        { icon: "🗺️", text: "Foot traffic, SEO & social analysis" },
                                    ].map((step, i) => (
                                        <div key={i} className="flex items-center gap-2.5 animate-fade-in-up" style={{ animationDelay: `${0.3 + i * 0.25}s` }}>
                                            <span className="text-base">{step.icon}</span>
                                            <span className="text-xs text-slate-500">{step.text}</span>
                                        </div>
                                    ))}
                                </div>
                                <div className="flex gap-1.5 mt-3">
                                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce" />
                                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                                </div>
                            </div>
                        </div>
                    )}
                    {isTyping && !isCentered && (
                        <div className="flex justify-start items-end gap-2">
                            <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mb-0.5 shadow-sm ${lightMode ? 'bg-gradient-to-br from-purple-100 to-violet-100 border border-purple-200/60' : 'bg-gradient-to-br from-indigo-100 to-violet-100 border border-indigo-200/60'}`}>
                                <Bot className={`w-3.5 h-3.5 ${lightMode ? 'text-purple-600' : 'text-indigo-600'}`} />
                            </div>
                            <div className={`px-4 py-3.5 rounded-2xl rounded-bl-md shadow-sm max-w-[82%] ${lightMode ? 'bg-white border border-purple-100/60' : 'bg-slate-800 border border-white/8'}`}>
                                <div className="flex items-center gap-1.5 mb-2.5">
                                    <span className={`w-1.5 h-1.5 rounded-full animate-bounce ${lightMode ? 'bg-purple-400' : 'bg-indigo-400'}`}></span>
                                    <span className={`w-1.5 h-1.5 rounded-full animate-bounce ${lightMode ? 'bg-purple-400' : 'bg-indigo-400'}`} style={{ animationDelay: '0.15s' }}></span>
                                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></span>
                                </div>
                                <p
                                    className="text-xs text-indigo-600/70 font-medium leading-relaxed transition-opacity duration-300"
                                    style={{ opacity: quoteVisible ? 1 : 0 }}
                                >
                                    {LOADING_QUOTES[quoteIndex]}
                                </p>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Scroll-to-bottom button */}
                {showScrollBtn && !isCentered && (
                    <button
                        onClick={scrollToBottom}
                        className="absolute bottom-4 right-4 z-20 w-8 h-8 rounded-full bg-slate-800 shadow-lg border border-white/10 flex items-center justify-center text-white/50 hover:text-indigo-400 hover:border-indigo-500/30 hover:shadow-indigo-900/50 transition-all animate-scale-in"
                        title="Scroll to bottom"
                    >
                        <ChevronDown className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* Input Area */}
            <div className={`flex flex-col flex-shrink-0 pointer-events-auto ${isCentered ? 'p-4 items-center mb-10 bg-transparent border-none w-full' : `px-4 pt-3 pb-4 backdrop-blur-sm ${lightMode ? 'bg-white/80 border-t border-purple-100/60' : 'bg-slate-900/95 border-t border-white/8'}`}`}>
                <div className={`w-full ${isCentered ? 'max-w-3xl' : ''}`}>
                    {/* Centered mode: search example chips */}
                    {followUpChips.length > 0 && isCentered && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {followUpChips.map(chip => (
                                <button
                                    key={chip.text}
                                    onClick={() => {
                                        setInput(chip.text);
                                        inputRef.current?.focus();
                                    }}
                                    disabled={isInputDisabled}
                                    className="text-xs font-medium px-4 py-1.5 rounded-full whitespace-nowrap transition-all disabled:opacity-50 shadow-sm flex items-center gap-1.5 bg-white/80 border border-purple-100 hover:bg-purple-50 hover:border-purple-200 text-slate-600"
                                >
                                    <MapPin className="w-3 h-3 text-purple-400" />
                                    {chip.text}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Ultralocal coverage CTA — compact inline chip */}
                    {addMyAreaCity && onAddMyArea && !isCentered && (
                        <div className="mb-2 mx-1">
                            <button
                                onClick={onAddMyArea}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-teal-500/10 border border-teal-400/25 hover:bg-teal-500/20 hover:border-teal-400/50 transition-all text-left group text-xs"
                            >
                                <svg className="w-3 h-3 text-teal-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                                <span className="font-semibold text-teal-300">Suggest {addMyAreaCity} for weekly intel</span>
                                <svg className="w-3 h-3 text-teal-400/50 shrink-0 group-hover:text-teal-400 group-hover:translate-x-0.5 transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/></svg>
                            </button>
                        </div>
                    )}

                    {/* Chat mode: categorized suggestion chips */}
                    {followUpChips.length > 0 && !isCentered && (() => {
                        const insightChips = followUpChips.filter(c => c.category === 'insight');
                        const actionChips = followUpChips.filter(c => c.category === 'action');
                        return (
                            <div className="flex flex-col gap-2.5 mb-3">
                                {insightChips.length > 0 && (
                                    <div>
                                        <p className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 px-1 ${lightMode ? 'text-slate-400' : 'text-white/35'}`}>Ask about results</p>
                                        <div className="flex flex-wrap gap-2">
                                            {insightChips.map(chip => (
                                                <button
                                                    key={chip.text}
                                                    onClick={() => onSendMessage(chip.text)}
                                                    disabled={isInputDisabled}
                                                    className={`text-xs font-medium px-3.5 py-1.5 rounded-full whitespace-nowrap transition-all disabled:opacity-50 shadow-sm flex items-center gap-1.5 ${
                                                        lightMode
                                                            ? 'bg-white border border-slate-200 hover:bg-amber-50 hover:border-amber-200 text-slate-600'
                                                            : 'bg-slate-800 border border-white/10 hover:bg-slate-700 hover:border-white/20 text-white/60'
                                                    }`}
                                                >
                                                    <Lightbulb className={`w-3 h-3 flex-shrink-0 ${lightMode ? 'text-amber-500' : 'text-amber-500'}`} />
                                                    {chip.text}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {actionChips.length > 0 && (
                                    <div>
                                        <p className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 px-1 ${lightMode ? 'text-purple-500' : 'text-indigo-400'}`}>Try next</p>
                                        <div className="flex flex-wrap gap-2">
                                            {actionChips.map(chip => (
                                                <button
                                                    key={chip.text}
                                                    onClick={() => onSendMessage(chip.text)}
                                                    disabled={isInputDisabled}
                                                    className={`text-xs font-semibold px-3.5 py-1.5 rounded-full whitespace-nowrap transition-all disabled:opacity-50 shadow-sm flex items-center gap-1.5 ${
                                                        lightMode
                                                            ? 'bg-purple-50 border border-purple-200 hover:bg-purple-100 hover:border-purple-300 text-purple-700'
                                                            : 'bg-indigo-500/15 border border-indigo-500/25 hover:bg-indigo-500/25 hover:border-indigo-400/40 text-indigo-300'
                                                    }`}
                                                >
                                                    <ArrowRight className={`w-3 h-3 flex-shrink-0 ${lightMode ? 'text-purple-500' : ''}`} />
                                                    {chip.text}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })()}

                    {/* Profile building quick-select chips */}
                    {profileBuildingMode && profileChips.length > 0 && !isTyping && (
                        <div className="flex flex-wrap gap-2 mb-3">
                            {profileChips.map(chip => (
                                <button
                                    key={chip.value}
                                    onClick={() => onSendMessage(chip.value)}
                                    className={`text-xs font-semibold px-3.5 py-2 rounded-xl whitespace-nowrap transition-all shadow-sm flex items-center gap-1.5 ${
                                        lightMode
                                            ? 'bg-white border border-purple-200 text-purple-700 hover:bg-purple-50 hover:border-purple-300'
                                            : 'bg-indigo-500/15 border border-indigo-500/25 hover:bg-indigo-500/25 text-indigo-300'
                                    }`}
                                >
                                    {chip.label}
                                </button>
                            ))}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="relative" ref={dropdownRef}>
                        {/* Places Autocomplete Dropdown — appears above the input */}
                        {showDropdown && predictions.length > 0 && (
                            <div className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl shadow-2xl z-50 overflow-hidden animate-fade-in ${isCentered ? 'bg-white border border-purple-100 shadow-purple-900/10' : 'bg-slate-900 border border-white/10'}`}>
                                <div className={`px-3 py-1.5 border-b ${isCentered ? 'border-purple-100 bg-purple-50/60' : 'border-white/8 bg-slate-800/80'}`}>
                                    <span className={`text-[10px] font-bold uppercase tracking-wider ${isCentered ? 'text-purple-500' : 'text-white/40'}`}>Matching businesses</span>
                                </div>
                                {predictions.map((pred, idx) => (
                                    <button
                                        key={pred.placeId}
                                        type="button"
                                        onClick={() => handlePredictionSelect(pred)}
                                        className={`w-full px-3 py-2.5 text-left flex items-center gap-3 transition-colors border-b last:border-b-0 ${isCentered
                                            ? `border-purple-50 ${idx === selectedIdx ? 'bg-purple-50 border-l-2 border-l-purple-500' : 'hover:bg-purple-50/60 border-l-2 border-l-transparent'}`
                                            : `border-gray-50 ${idx === selectedIdx ? 'bg-indigo-500/15 border-l-2 border-l-indigo-500' : 'hover:bg-slate-800 border-l-2 border-l-transparent'}`
                                        }`}
                                    >
                                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isCentered
                                            ? (idx === selectedIdx ? 'bg-purple-100' : 'bg-slate-100')
                                            : (idx === selectedIdx ? 'bg-indigo-500/20' : 'bg-slate-700')
                                        }`}>
                                            <MapPin className={`w-4 h-4 ${isCentered
                                                ? (idx === selectedIdx ? 'text-purple-600' : 'text-slate-400')
                                                : (idx === selectedIdx ? 'text-indigo-400' : 'text-white/30')
                                            }`} />
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <div className={`text-sm font-semibold truncate ${isCentered
                                                ? (idx === selectedIdx ? 'text-slate-900' : 'text-slate-700')
                                                : (idx === selectedIdx ? 'text-white' : 'text-white/80')
                                            }`}>
                                                {pred.mainText}
                                            </div>
                                            <div className={`text-xs truncate ${isCentered ? 'text-slate-400' : 'text-white/40'}`}>{pred.secondaryText}</div>
                                        </div>
                                        {idx === selectedIdx && (
                                            <span className="text-[10px] text-indigo-400 font-medium shrink-0">Enter</span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Resolving indicator */}
                        {isResolving && (
                            <div className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl shadow-xl z-50 px-4 py-3 flex items-center gap-3 animate-fade-in ${isCentered ? 'bg-white border border-purple-200 shadow-purple-900/10' : 'bg-slate-900 border border-indigo-500/30'}`}>
                                <Loader2 className={`w-4 h-4 animate-spin ${isCentered ? 'text-purple-500' : 'text-indigo-400'}`} />
                                <span className={`text-sm font-medium ${isCentered ? 'text-purple-700' : 'text-indigo-300'}`}>Resolving location...</span>
                            </div>
                        )}

                        <input
                            ref={inputRef}
                            type="text"
                            className={`w-full pl-5 pr-14 rounded-full border transition-all outline-none focus:ring-2 ${
                                isCentered
                                    ? 'py-5 text-lg bg-white/90 border-purple-200 text-slate-800 placeholder-slate-400 focus:ring-purple-400/30 focus:border-purple-400 shadow-lg shadow-purple-900/10'
                                    : lightMode
                                        ? `py-3.5 text-base md:text-sm text-slate-800 placeholder-slate-400 focus:ring-purple-400/30 focus:border-purple-300 shadow-sm ${isDiscovering ? 'bg-white border-amber-300' : 'bg-white border-purple-200/60 focus:bg-white'}`
                                        : `py-3.5 text-base md:text-sm text-white/90 placeholder-white/30 focus:ring-indigo-500/30 focus:border-indigo-500/40 shadow-sm ${isDiscovering ? 'bg-slate-800 border-amber-500/30' : 'bg-slate-800 border-white/10 focus:bg-slate-800'}`
                            }`}
                            placeholder={isDiscovering ? "Discovery in progress — chat unlocks when done..." : isCentered ? "Search for a business by name or city..." : "Ask anything about this business..."}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onFocus={() => {
                                if (predictions.length > 0 && (isCentered || shouldAutocomplete(input))) {
                                    setShowDropdown(true);
                                }
                            }}
                            disabled={isInputDisabled}
                        />
                        {isCentered ? (
                            <button
                                type="submit"
                                disabled={!input.trim() || isInputDisabled}
                                className={`absolute right-2 top-3 p-2.5 text-purple-400 hover:text-purple-600 rounded-xl hover:bg-purple-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all`}
                            >
                                <SearchIcon className="w-5 h-5" />
                            </button>
                        ) : (
                            <button
                                type="submit"
                                disabled={!input.trim() || isInputDisabled}
                                className={`absolute right-1.5 top-1.5 p-3 md:p-2.5 bg-gradient-to-br from-indigo-500 to-violet-600 text-white rounded-full hover:from-indigo-400 hover:to-violet-500 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-200/50 hover:shadow-indigo-200 hover:scale-105`}
                            >
                                <svg className="w-5 h-5 md:w-4 md:h-4 transform rotate-90" fill="currentColor" viewBox="0 0 20 20"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"></path></svg>
                            </button>
                        )}
                    </form>
                </div>
            </div>

            <ExplainerModal isOpen={isExplainerOpen} onClose={() => setIsExplainerOpen(false)} />
        </div>
    );
};

export default ChatInterface;
