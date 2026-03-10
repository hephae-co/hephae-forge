import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, X, Loader2, Check, Calendar, Mail, ChevronDown } from 'lucide-react';

const CAPABILITIES = [
  { id: 'seo', label: 'Google Presence Check', description: 'Track search ranking changes weekly', color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  { id: 'margin', label: 'Price Optimization', description: 'Monitor food cost fluctuations', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  { id: 'traffic', label: 'Foot Traffic Forecast', description: 'Weekly foot traffic patterns', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  { id: 'competitive', label: 'Competitor Tracking', description: 'Track competitor movements', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  { id: 'social', label: 'Social Media Health', description: 'Monitor social presence health', color: 'text-sky-400', bg: 'bg-sky-500/10', border: 'border-sky-500/20' },
];

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

interface HeartbeatSetupProps {
  isOpen: boolean;
  onClose: () => void;
  businessName: string;
  businessSlug: string;
  userEmail: string;
  onCreated: (heartbeatId: string) => void;
}

export function HeartbeatSetup({ isOpen, onClose, businessName, businessSlug, userEmail, onCreated }: HeartbeatSetupProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(['seo', 'margin', 'traffic', 'competitive']));
  const [dayOfWeek, setDayOfWeek] = useState(1); // Monday
  const [showDayPicker, setShowDayPicker] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const toggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (selected.size === 0) {
      setError('Select at least one capability to monitor.');
      return;
    }
    setError('');
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/heartbeat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          businessSlug,
          businessName,
          capabilities: Array.from(selected),
          dayOfWeek,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to create heartbeat');
      }
      const data = await res.json();
      onCreated(data.id);
      onClose();
    } catch (e: any) {
      setError(e.message || 'Something went wrong');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
        >
          <motion.div
            initial={{ scale: 0.9, y: 20, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="w-full max-w-md bg-slate-900 border border-white/10 p-6 rounded-3xl shadow-2xl relative overflow-hidden"
          >
            {/* Background glow */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10">
              {/* Header */}
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/20">
                    <Activity className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white">Set Up Heartbeat</h2>
                    <p className="text-slate-400 text-xs">Weekly monitoring for {businessName}</p>
                  </div>
                </div>
                <button onClick={onClose} className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors">
                  <X className="w-4 h-4 text-slate-400" />
                </button>
              </div>

              <p className="text-slate-300 text-sm mb-5 leading-relaxed">
                We&apos;ll re-run your selected analyses every week and email you <span className="text-emerald-400 font-medium">only when something changes</span>.
              </p>

              {/* Capability checkboxes */}
              <div className="space-y-2 mb-5">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Capabilities to watch</p>
                {CAPABILITIES.map(cap => {
                  const isSelected = selected.has(cap.id);
                  return (
                    <button
                      key={cap.id}
                      onClick={() => toggle(cap.id)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                        isSelected
                          ? `${cap.bg} ${cap.border} border-opacity-100`
                          : 'bg-white/[0.02] border-white/5 hover:border-white/10'
                      }`}
                    >
                      <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                        isSelected ? 'border-emerald-400 bg-emerald-400' : 'border-slate-600'
                      }`}>
                        {isSelected && <Check className="w-3 h-3 text-slate-900" strokeWidth={3} />}
                      </div>
                      <div className="min-w-0">
                        <p className={`text-sm font-medium ${isSelected ? 'text-white' : 'text-slate-300'}`}>{cap.label}</p>
                        <p className="text-xs text-slate-500">{cap.description}</p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Day picker */}
              <div className="flex items-center gap-3 mb-4">
                <Calendar className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span className="text-sm text-slate-300">Deliver every:</span>
                <div className="relative">
                  <button
                    onClick={() => setShowDayPicker(v => !v)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 hover:border-white/20 transition-colors text-sm text-white font-medium"
                  >
                    {DAYS[dayOfWeek]}
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                  {showDayPicker && (
                    <>
                      <div className="fixed inset-0 z-10" onClick={() => setShowDayPicker(false)} />
                      <div className="absolute top-full mt-1 left-0 bg-slate-800 border border-white/10 rounded-xl shadow-xl z-20 py-1 min-w-[140px]">
                        {DAYS.map((day, i) => (
                          <button
                            key={day}
                            onClick={() => { setDayOfWeek(i); setShowDayPicker(false); }}
                            className={`w-full text-left px-3 py-1.5 text-sm hover:bg-white/5 transition-colors ${i === dayOfWeek ? 'text-emerald-400 font-medium' : 'text-slate-300'}`}
                          >
                            {day}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Email display */}
              <div className="flex items-center gap-3 mb-5">
                <Mail className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span className="text-sm text-slate-300">Send to:</span>
                <span className="text-sm text-white font-medium">{userEmail}</span>
              </div>

              {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={isSubmitting || selected.size === 0}
                className="w-full py-3 px-4 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-500/25 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Activity className="w-4 h-4" />
                    Start Heartbeat
                  </>
                )}
              </button>
              <p className="text-center text-xs text-slate-500 mt-2">
                Your first digest arrives next {DAYS[dayOfWeek]}.
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
