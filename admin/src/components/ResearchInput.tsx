'use client';

import { useState } from 'react';
import { Brain, Loader2, RefreshCw } from 'lucide-react';

interface ResearchInputProps {
    onResearchComplete?: () => void;
}

export default function ResearchInput({ onResearchComplete }: ResearchInputProps) {
    const [zipCode, setZipCode] = useState('');
    const [isResearching, setIsResearching] = useState(false);
    const [status, setStatus] = useState<string | null>(null);

    const handleRunResearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!/^\d{5}$/.test(zipCode)) {
            setStatus("Please enter a valid 5-digit zip code");
            return;
        }

        setIsResearching(true);
        setStatus(`Running fresh research for ${zipCode}...`);

        try {
            const res = await fetch(`/api/zipcode-research/${zipCode}?force=true`, {
                method: 'POST',
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || 'Research failed');
            }

            setStatus('Research complete — new run saved.');
            onResearchComplete?.();
        } catch (err: any) {
            setStatus("Error: " + err.message);
        } finally {
            setIsResearching(false);
        }
    };

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <Brain className="w-5 h-5 text-emerald-500" />
                Market Research
            </h2>
            <form onSubmit={handleRunResearch} className="flex flex-col md:flex-row gap-4">
                <input
                    type="text"
                    placeholder="Enter Zip Code (e.g. 07110)"
                    value={zipCode}
                    onChange={(e) => setZipCode(e.target.value)}
                    className="flex-1 bg-gray-50 border border-gray-300 rounded-lg px-4 py-2 text-gray-900 focus:outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 transition-all"
                    maxLength={5}
                />
                <button
                    type="submit"
                    disabled={isResearching || !/^\d{5}$/.test(zipCode)}
                    className="bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold px-6 py-2 rounded-lg flex items-center gap-2 transition-all shadow-md"
                >
                    {isResearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    {isResearching ? "Researching..." : "Run Research"}
                </button>
            </form>
            {status && (
                <p className={`mt-4 text-sm ${status.includes('Error') ? 'text-red-500' : 'text-emerald-600'}`}>
                    {status}
                </p>
            )}
        </div>
    );
}
