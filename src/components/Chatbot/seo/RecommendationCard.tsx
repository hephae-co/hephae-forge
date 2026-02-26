import React from 'react';
import { Recommendation } from '@/lib/types';
import { AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { SEVERITY_COLORS } from './constants';

interface RecommendationCardProps {
  item: Recommendation;
}

const RecommendationCard: React.FC<RecommendationCardProps> = ({ item }) => {
  const getIcon = () => {
    switch (item.severity) {
      case 'Critical': return <AlertCircle className="w-5 h-5 text-red-600" />;
      case 'Warning': return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
      case 'Info': return <Info className="w-5 h-5 text-blue-600" />;
      default: return <CheckCircle2 className="w-5 h-5 text-gray-600" />;
    }
  };

  const badgeClass = SEVERITY_COLORS[item.severity] || 'bg-gray-100 text-gray-800 border-gray-200';

  return (
    <div className="bg-white rounded-lg p-4 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {getIcon()}
          <h4 className="font-semibold text-gray-900">{item.title}</h4>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full border font-medium uppercase tracking-wide ${badgeClass}`}>
          {item.severity}
        </span>
      </div>
      <p className="text-gray-600 text-sm mb-3">{item.description}</p>
      <div className="bg-slate-50 p-3 rounded text-sm text-slate-700 border border-slate-100">
        <span className="font-semibold text-slate-900 mr-1">Fix:</span>
        {item.action}
      </div>
    </div>
  );
};

export default RecommendationCard;
