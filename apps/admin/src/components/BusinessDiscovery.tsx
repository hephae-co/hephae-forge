'use client';

import { useState } from 'react';
import { Store, Search, Loader2, Database } from 'lucide-react';

interface BusinessDiscoveryProps {
    onZipCodeSubmit: (zipCode: string) => void;
    onDiscoveryComplete?: (zipCode: string) => void;
}

export default function BusinessDiscovery({ onZipCodeSubmit, onDiscoveryComplete }: BusinessDiscoveryProps) {
    const [zipCode, setZipCode] = useState('');
    const [isDiscovering, setIsDiscovering] = useState(false);
    const [status, setStatus] = useState<string | null>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!/^\d{5}$/.test(zipCode)) {
            setStatus("Please enter a valid 5-digit zip code");
            return;
        }
        setStatus(null);
        onZipCodeSubmit(zipCode);
    };

    const handleDiscovery = async () => {
        if (!/^\d{5}$/.test(zipCode)) return;

        setIsDiscovering(true);
        setStatus("Finding businesses in " + zipCode + "...");

        try {
            const res = await fetch('/api/research/businesses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ zipCode })
            });

            if (!res.ok) throw new Error("Discovery failed");

            const data = await res.json();
            setStatus(`Discovery complete. Found ${data.count} new/updated businesses.`);
            onDiscoveryComplete?.(zipCode);
        } catch (err: any) {
            setStatus("Error: " + err.message);
        } finally {
            setIsDiscovering(false);
        }
    };

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <Store className="w-5 h-5 text-indigo-500" />
                Business Discovery
            </h2>
            <form onSubmit={handleSubmit} className="flex flex-col md:flex-row gap-4">
                <input
                    type="text"
                    placeholder="Enter Zip Code (e.g. 07110)"
                    value={zipCode}
                    onChange={(e) => setZipCode(e.target.value)}
                    className="flex-1 bg-gray-50 border border-gray-300 rounded-lg px-4 py-2 text-gray-900 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all"
                    maxLength={5}
                />
                <button
                    type="submit"
                    className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-2 rounded-lg flex items-center gap-2 transition-all shadow-md"
                >
                    <Search className="w-4 h-4" />
                    Look Up
                </button>
                <button
                    type="button"
                    onClick={handleDiscovery}
                    disabled={isDiscovering || !/^\d{5}$/.test(zipCode)}
                    className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 text-gray-700 font-semibold px-5 py-2 rounded-lg flex items-center gap-2 transition-all border border-gray-300"
                >
                    {isDiscovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
                    {isDiscovering ? "Scanning..." : "Scan Businesses"}
                </button>
            </form>
            {status && (
                <p className={`mt-4 text-sm ${status.includes('Error') ? 'text-red-500' : 'text-indigo-600'}`}>
                    {status}
                </p>
            )}
        </div>
    );
}
