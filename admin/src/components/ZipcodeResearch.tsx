'use client';

import { useState, useEffect, useCallback } from 'react';
import { Globe, ChevronDown, ChevronRight, Loader2, BookOpen, RefreshCw, MapPin, Users, Home, Building2, TrendingUp, ShoppingCart, Train, Flame } from 'lucide-react';

interface ReportSection {
    title: string;
    content: string;
    key_facts: string[];
}

interface ResearchReport {
    summary: string;
    zip_code: string;
    sections: Record<string, ReportSection>;
    sources?: { short_id: string; title: string; url: string; domain: string }[];
    source_count?: number;
}

interface ZipcodeResearchProps {
    zipCode: string;
}

const SECTION_ICONS: Record<string, React.ReactNode> = {
    geography: <MapPin className="w-4 h-4" />,
    demographics: <Users className="w-4 h-4" />,
    census_housing: <Home className="w-4 h-4" />,
    business_landscape: <Building2 className="w-4 h-4" />,
    economic_indicators: <TrendingUp className="w-4 h-4" />,
    consumer_market: <ShoppingCart className="w-4 h-4" />,
    infrastructure: <Train className="w-4 h-4" />,
    trending: <Flame className="w-4 h-4" />,
};

export default function ZipcodeResearch({ zipCode }: ZipcodeResearchProps) {
    const [report, setReport] = useState<ResearchReport | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isChecking, setIsChecking] = useState(true);
    const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);

    const checkCache = useCallback(async () => {
        setIsChecking(true);
        setError(null);
        try {
            const res = await fetch(`/api/zipcode-research/${zipCode}`);
            if (!res.ok) throw new Error('Failed to check cache');
            const data = await res.json();
            if (data.success && data.report) {
                setReport(data.report);
            } else {
                setReport(null);
            }
        } catch {
            setReport(null);
        } finally {
            setIsChecking(false);
        }
    }, [zipCode]);

    useEffect(() => {
        setReport(null);
        setExpandedSections(new Set());
        checkCache();
    }, [zipCode, checkCache]);

    const runResearch = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/zipcode-research/${zipCode}`, {
                method: 'POST',
            });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Research failed');
            }
            const data = await res.json();
            if (data.success && data.report) {
                setReport(data.report);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setIsLoading(false);
        }
    };

    const toggleSection = (key: string) => {
        setExpandedSections(prev => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    const expandAll = () => {
        if (report?.sections) {
            setExpandedSections(new Set(Object.keys(report.sections)));
        }
    };

    const collapseAll = () => setExpandedSections(new Set());

    if (isChecking) {
        return (
            <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
                <div className="flex items-center gap-3 text-gray-400">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="text-sm">Checking for existing research on {zipCode}...</span>
                </div>
            </div>
        );
    }

    if (!report) {
        return (
            <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                            <Globe className="w-5 h-5 text-indigo-500" />
                            Area Research for {zipCode}
                        </h3>
                        <p className="text-sm text-gray-500 mt-1">
                            Run a deep research pipeline to analyze demographics, economy, businesses, and more.
                        </p>
                    </div>
                    <button
                        onClick={runResearch}
                        disabled={isLoading}
                        className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg flex items-center gap-2 transition-all shadow-md whitespace-nowrap"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Researching...
                            </>
                        ) : (
                            <>
                                <BookOpen className="w-4 h-4" />
                                Run Deep Research
                            </>
                        )}
                    </button>
                </div>
                {isLoading && (
                    <div className="mt-4 p-4 bg-indigo-50 border border-indigo-100 rounded-lg">
                        <p className="text-sm text-indigo-700">
                            The research pipeline is running. This involves multiple Google searches and AI evaluation passes. It typically takes 30-60 seconds.
                        </p>
                        <div className="mt-3 flex gap-2">
                            {['Searching', 'Evaluating', 'Refining', 'Trends', 'Composing'].map((step, i) => (
                                <span key={step} className="text-xs bg-indigo-100 text-indigo-600 px-2 py-1 rounded-full border border-indigo-200">
                                    {step}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
                {error && (
                    <p className="mt-4 text-sm text-red-500">{error}</p>
                )}
            </div>
        );
    }

    const sectionEntries = Object.entries(report.sections);
    const sourceCount = report.source_count || report.sources?.length || 0;

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6 shadow-sm">
            {/* Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-5">
                <div>
                    <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                        <Globe className="w-5 h-5 text-indigo-500" />
                        Area Research: {report.zip_code}
                    </h3>
                    <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs bg-green-50 text-green-600 px-2 py-0.5 rounded-full border border-green-200">
                            {sectionEntries.length} sections
                        </span>
                        {sourceCount > 0 && (
                            <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full border border-blue-200">
                                {sourceCount} sources
                            </span>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={expandedSections.size === sectionEntries.length ? collapseAll : expandAll}
                        className="text-xs text-gray-500 hover:text-gray-700 px-3 py-1.5 rounded border border-gray-200 hover:border-gray-300 transition-colors"
                    >
                        {expandedSections.size === sectionEntries.length ? 'Collapse All' : 'Expand All'}
                    </button>
                    <button
                        onClick={runResearch}
                        disabled={isLoading}
                        className="text-xs text-indigo-500 hover:text-indigo-600 px-3 py-1.5 rounded border border-indigo-200 hover:border-indigo-300 transition-colors flex items-center gap-1"
                    >
                        <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
                        Re-research
                    </button>
                </div>
            </div>

            {/* Summary card */}
            {report.summary && (
                <div className="p-4 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-lg mb-5">
                    <p className="text-sm text-gray-700 leading-relaxed">{report.summary}</p>
                </div>
            )}

            {/* Sections */}
            <div className="space-y-2">
                {sectionEntries.map(([key, section]) => {
                    const isExpanded = expandedSections.has(key);
                    const icon = SECTION_ICONS[key] || <BookOpen className="w-4 h-4" />;

                    return (
                        <div key={key} className="border border-gray-200 rounded-lg overflow-hidden">
                            <button
                                onClick={() => toggleSection(key)}
                                className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                            >
                                <span className="text-indigo-500">{icon}</span>
                                <span className="flex-1 font-semibold text-sm text-gray-800">{section.title}</span>
                                {section.key_facts?.length > 0 && (
                                    <span className="text-xs text-gray-400 mr-2">
                                        {section.key_facts.length} facts
                                    </span>
                                )}
                                {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-gray-400" />
                                ) : (
                                    <ChevronRight className="w-4 h-4 text-gray-400" />
                                )}
                            </button>

                            {isExpanded && (
                                <div className="px-4 pb-4 border-t border-gray-100">
                                    <p className="text-sm text-gray-600 leading-relaxed mt-3 whitespace-pre-wrap">
                                        {section.content}
                                    </p>
                                    {section.key_facts?.length > 0 && (
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            {section.key_facts.map((fact, i) => (
                                                <span
                                                    key={i}
                                                    className="text-xs bg-gray-50 text-gray-600 px-2.5 py-1 rounded-full border border-gray-200"
                                                >
                                                    {fact}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Sources */}
            {report.sources && report.sources.length > 0 && (
                <details className="mt-4">
                    <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 transition-colors">
                        View {report.sources.length} sources
                    </summary>
                    <div className="mt-2 grid gap-1">
                        {report.sources.map((src) => (
                            <a
                                key={src.short_id}
                                href={src.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-indigo-500 hover:text-indigo-600 hover:underline truncate block"
                            >
                                [{src.short_id}] {src.title || src.domain}
                            </a>
                        ))}
                    </div>
                </details>
            )}

            {error && (
                <p className="mt-4 text-sm text-red-500">{error}</p>
            )}
        </div>
    );
}
