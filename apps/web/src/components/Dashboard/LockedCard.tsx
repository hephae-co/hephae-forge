'use client';

import React from 'react';
import { ArrowRight } from 'lucide-react';
import { Card } from './Card';

export function LockedCard({
  title,
  icon: Icon,
  action,
  onAction,
  className = '',
}: {
  title: string;
  icon: React.ElementType;
  action: string;
  onAction?: () => void;
  className?: string;
}) {
  return (
    <Card className={`flex flex-col items-center justify-center gap-3 min-h-[160px] opacity-60 hover:opacity-80 transition-opacity ${className}`}>
      <div className="w-12 h-12 rounded-full bg-purple-50 flex items-center justify-center">
        <Icon className="w-5 h-5 text-purple-400" />
      </div>
      <div className="text-center px-4">
        <p className="text-sm font-semibold text-slate-700">{title}</p>
        <p className="text-xs text-slate-400 mt-0.5">No data yet</p>
      </div>
      <button
        onClick={onAction}
        className="text-xs font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 px-4 py-2 rounded-lg transition-colors flex items-center gap-1.5"
      >
        {action} <ArrowRight className="w-3 h-3" />
      </button>
    </Card>
  );
}
