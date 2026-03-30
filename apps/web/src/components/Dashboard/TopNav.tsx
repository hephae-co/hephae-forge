'use client';

import { Building2, ExternalLink, Zap, LogIn, LogOut } from 'lucide-react';
import { useState } from 'react';
import type { DashBusiness } from './types';
import type { User } from 'firebase/auth';

export function TopNav({
  business,
  user,
  onSignIn,
  onSignOut,
  onRunAnalysis,
  nextAnalysisLabel,
}: {
  business: DashBusiness | null;
  user: User | null;
  onSignIn?: () => void;
  onSignOut?: () => void;
  onRunAnalysis?: () => void;
  nextAnalysisLabel?: string | null;
}) {
  const [showUserMenu, setShowUserMenu] = useState(false);

  return (
    <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl flex justify-between items-center px-6 h-16 shadow-sm shadow-purple-900/5 border-b border-purple-100/40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-700 to-violet-600 flex items-center justify-center shadow-md">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-xl font-black tracking-tighter text-purple-900">hephae</span>
        </div>
        {business && (
          <div className="hidden md:flex items-center gap-2.5 bg-purple-50/80 px-3.5 py-1.5 rounded-xl border border-purple-100">
            <Building2 className="w-4 h-4 text-purple-400 flex-shrink-0" />
            <div>
              <span className="text-sm font-bold text-slate-800">{business.name}</span>
              {business.address && (
                <span className="text-[10px] text-slate-400 ml-2">{business.address.split(',').slice(0, 2).join(',')}</span>
              )}
            </div>
            {business.officialUrl && (
              <a href={business.officialUrl} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-600 transition-colors">
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {user ? (
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(v => !v)}
              className="flex items-center gap-1.5 bg-white/90 backdrop-blur-md px-2.5 py-1.5 rounded-full shadow-sm border border-slate-200/80 hover:shadow-md transition-all"
            >
              {user.photoURL ? (
                <img src={user.photoURL} alt="" className="w-6 h-6 rounded-full" referrerPolicy="no-referrer" />
              ) : (
                <div className="w-6 h-6 rounded-full bg-purple-100 flex items-center justify-center">
                  <span className="text-[10px] font-bold text-purple-600">{user.displayName?.[0] || user.email?.[0] || '?'}</span>
                </div>
              )}
              <span className="text-xs font-medium text-slate-700 hidden md:block max-w-[100px] truncate">
                {user.displayName || user.email?.split('@')[0]}
              </span>
            </button>
            {showUserMenu && (
              <>
                <div className="fixed inset-0 z-[99]" onClick={() => setShowUserMenu(false)} />
                <div className="absolute right-0 mt-1.5 w-44 bg-white rounded-xl shadow-xl border border-slate-200 py-1 z-[100]">
                  <div className="px-3 py-1.5 border-b border-slate-100">
                    <p className="text-xs font-medium text-slate-900 truncate">{user.displayName}</p>
                    <p className="text-[10px] text-slate-500 truncate">{user.email}</p>
                  </div>
                  <button
                    onClick={() => { setShowUserMenu(false); onSignOut?.(); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" /> Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 hidden sm:inline">Free weekly business intelligence</span>
            <button onClick={onSignIn} className="px-3 py-1.5 rounded-full border border-slate-200/80 bg-white/90 backdrop-blur-md shadow-sm hover:shadow-md transition-all text-xs font-medium text-slate-600">
              <LogIn className="w-3.5 h-3.5 inline mr-1" /> Sign in
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
