'use client';

import React from 'react';

export function Card({ children, className = '', onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div className={`bg-white rounded-2xl shadow-sm shadow-purple-900/5 ${className}`} onClick={onClick}>
      {children}
    </div>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{children}</p>;
}
