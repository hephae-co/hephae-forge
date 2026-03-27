"use client";

import React, { useState } from 'react';
import { MapPin, Loader2, CheckCircle2, Sparkles, ArrowRight, Radio } from 'lucide-react';

type CoverageState =
    | { status: 'idle' }
    | { status: 'checking' }
    | { status: 'covered'; city: string; state: string; headline: string | null; pulseCount: number }
    | { status: 'not_covered'; zipCode: string; city: string | null; state: string | null; interestCount: number }
    | { status: 'submitted'; zipCode: string; city: string | null; message: string }
    | { status: 'error'; message: string };

interface UltralocalWidgetProps {
    /** Called with the API base path (e.g. '/api') — widget handles its own fetch */
    apiBase?: string;
}

export const UltralocalWidget: React.FC<UltralocalWidgetProps> = ({ apiBase = '/api' }) => {
    const [zip, setZip] = useState('');
    const [email, setEmail] = useState('');
    const [coverage, setCoverage] = useState<CoverageState>({ status: 'idle' });
    const [businessType, setBusinessType] = useState('');

    const checkZip = async (zipCode: string) => {
        if (!/^\d{5}$/.test(zipCode)) return;
        setCoverage({ status: 'checking' });
        try {
            const res = await fetch(`${apiBase}/pulse/zipcode/${zipCode}`);
            const data = await res.json();
            if (data.ultralocal) {
                setCoverage({
                    status: 'covered',
                    city: data.city || zipCode,
                    state: data.state || '',
                    headline: data.latestHeadline || null,
                    pulseCount: data.pulseCount || 0,
                });
            } else {
                setCoverage({
                    status: 'not_covered',
                    zipCode,
                    city: data.city,
                    state: data.state,
                    interestCount: data.interestCount || 0,
                });
            }
        } catch {
            setCoverage({ status: 'error', message: 'Could not check coverage. Try again.' });
        }
    };

    const submitInterest = async () => {
        if (coverage.status !== 'not_covered') return;
        setCoverage({ status: 'checking' });
        try {
            const res = await fetch(`${apiBase}/pulse/zipcode-interest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    zipCode: coverage.zipCode,
                    email: email || undefined,
                    businessType: businessType || undefined,
                }),
            });
            const data = await res.json();
            setCoverage({
                status: 'submitted',
                zipCode: coverage.zipCode,
                city: coverage.city,
                message: data.message || `You're on the list for ${coverage.zipCode}!`,
            });
        } catch {
            setCoverage({ status: 'error', message: 'Submission failed. Please try again.' });
        }
    };

    const handleZipInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value.replace(/\D/g, '').slice(0, 5);
        setZip(val);
        if (val.length === 5) checkZip(val);
    };

    return (
        <div className="pointer-events-auto w-full max-w-sm mx-auto">
            {/* Idle / checking / zip entry */}
            {(coverage.status === 'idle' || coverage.status === 'checking') && (
                <div className="flex items-center gap-2 bg-white/80 backdrop-blur-sm border border-gray-200/80 rounded-2xl px-4 py-3 shadow-sm">
                    <MapPin className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                    <input
                        type="text"
                        inputMode="numeric"
                        placeholder="Enter your zip code"
                        value={zip}
                        onChange={handleZipInput}
                        maxLength={5}
                        className="flex-1 text-sm bg-transparent outline-none text-gray-700 placeholder-gray-400 min-w-0"
                    />
                    {coverage.status === 'checking' ? (
                        <Loader2 className="w-4 h-4 text-indigo-400 animate-spin flex-shrink-0" />
                    ) : (
                        <span className="text-[10px] font-semibold text-gray-400 tracking-wide uppercase">Is your area covered?</span>
                    )}
                </div>
            )}

            {/* Covered — ultralocal badge */}
            {coverage.status === 'covered' && (
                <div className="bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200/60 rounded-2xl px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 mb-1.5">
                        <div className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.9)] animate-pulse" />
                            <span className="text-[10px] font-bold text-emerald-600 tracking-wider uppercase">Ultralocal</span>
                        </div>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    </div>
                    <p className="text-sm font-semibold text-gray-800">
                        {coverage.city}{coverage.state ? `, ${coverage.state}` : ''} has weekly coverage
                    </p>
                    {coverage.headline && (
                        <p className="text-xs text-gray-500 mt-1 leading-relaxed line-clamp-2">
                            {coverage.headline}
                        </p>
                    )}
                    <p className="text-[10px] text-emerald-600/70 mt-1.5 font-medium">
                        {coverage.pulseCount} weekly pulse{coverage.pulseCount !== 1 ? 's' : ''} generated
                    </p>
                </div>
            )}

            {/* Not covered — submission form */}
            {coverage.status === 'not_covered' && (
                <div className="bg-white/90 backdrop-blur-sm border border-indigo-100 rounded-2xl px-4 py-3 shadow-sm space-y-2.5">
                    <div className="flex items-center gap-2">
                        <Radio className="w-3.5 h-3.5 text-indigo-400" />
                        <p className="text-xs font-semibold text-gray-700">
                            {coverage.city ? `${coverage.city} isn't on Hephae yet` : `Zip ${coverage.zipCode} isn't covered yet`}
                        </p>
                        {coverage.interestCount > 0 && (
                            <span className="text-[10px] bg-indigo-50 text-indigo-500 font-semibold px-1.5 py-0.5 rounded-full border border-indigo-100">
                                {coverage.interestCount} interested
                            </span>
                        )}
                    </div>
                    <p className="text-[11px] text-gray-500 leading-relaxed">
                        Submit your zip and we'll add it to our coverage roadmap. Get hyperlocal weekly intelligence for your neighborhood.
                    </p>
                    <div className="space-y-1.5">
                        <input
                            type="email"
                            placeholder="Email (optional — we'll notify you)"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="w-full text-xs bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 outline-none focus:border-indigo-300 text-gray-700 placeholder-gray-400"
                        />
                        <input
                            type="text"
                            placeholder="Business type (e.g. Restaurant, Salon)"
                            value={businessType}
                            onChange={e => setBusinessType(e.target.value)}
                            className="w-full text-xs bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 outline-none focus:border-indigo-300 text-gray-700 placeholder-gray-400"
                        />
                        <button
                            onClick={submitInterest}
                            className="w-full flex items-center justify-center gap-1.5 text-xs font-semibold bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl px-3 py-2 transition-colors active:scale-95"
                        >
                            Request coverage <ArrowRight className="w-3 h-3" />
                        </button>
                    </div>
                </div>
            )}

            {/* Submitted confirmation */}
            {coverage.status === 'submitted' && (
                <div className="bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-200/60 rounded-2xl px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 mb-1">
                        <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                        <span className="text-[10px] font-bold text-violet-600 tracking-wider uppercase">You're on the list</span>
                    </div>
                    <p className="text-xs text-gray-600 leading-relaxed">{coverage.message}</p>
                </div>
            )}

            {/* Error */}
            {coverage.status === 'error' && (
                <div className="bg-red-50 border border-red-200/60 rounded-2xl px-4 py-2.5">
                    <p className="text-xs text-red-600">{coverage.message}</p>
                    <button
                        onClick={() => setCoverage({ status: 'idle' })}
                        className="text-[10px] text-red-500 underline mt-1"
                    >Try again</button>
                </div>
            )}
        </div>
    );
};

export default UltralocalWidget;
