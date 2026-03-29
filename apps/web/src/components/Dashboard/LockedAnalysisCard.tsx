'use client';

import React from 'react';
import { Lock, LogIn } from 'lucide-react';

export function LockedAnalysisCard({
  children,
  title,
  subtitle,
  onSignIn,
}: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  onSignIn?: () => void;
}) {
  return (
    <div className="relative rounded-2xl overflow-hidden h-full min-h-[240px] border border-slate-100 shadow-sm shadow-purple-900/5 bg-white">
      <div className="absolute inset-0 pointer-events-none select-none" style={{ filter: 'blur(5px)', opacity: 0.25 }}>
        {children}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-white/70 backdrop-blur-[3px]">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-100 to-violet-100 flex items-center justify-center shadow-sm">
          <Lock className="w-5 h-5 text-purple-600" />
        </div>
        <div className="text-center px-8">
          <p className="text-sm font-bold text-slate-800">Unlock {title}</p>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            {subtitle ?? 'Sign in and create your business profile to run this analysis'}
          </p>
        </div>
        <div className="flex flex-col items-center gap-2">
          <button
            onClick={onSignIn}
            className="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white px-6 py-2.5 rounded-xl text-xs font-bold shadow-md shadow-purple-900/20 transition-all hover:scale-[1.02] active:scale-95"
          >
            <LogIn className="w-3.5 h-3.5" /> Sign in with Google
          </button>
          <p className="text-[10px] text-slate-400">Free · No credit card required</p>
        </div>
      </div>
    </div>
  );
}
