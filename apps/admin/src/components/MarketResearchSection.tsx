'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Brain } from 'lucide-react';
import ResearchInput from '@/components/ResearchInput';
import ZipCodeResearchBrowser from '@/components/ZipCodeResearchBrowser';
import AreaResearchBrowser from '@/components/AreaResearchBrowser';
import CombinedContextList from '@/components/CombinedContextList';

export default function MarketResearchSection() {
  const [expanded, setExpanded] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-bold text-gray-900">Market Research</h2>
        </div>
        {expanded ? (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronRight className="w-5 h-5 text-gray-400" />
        )}
      </button>
      {expanded && (
        <div className="px-6 pb-6 space-y-8 border-t border-gray-100 pt-6 animate-in fade-in slide-in-from-top-2 duration-300">
          <ResearchInput onResearchComplete={() => setRefreshKey(k => k + 1)} />
          <ZipCodeResearchBrowser refreshKey={refreshKey} />
          <AreaResearchBrowser />
          <CombinedContextList />
        </div>
      )}
    </div>
  );
}
