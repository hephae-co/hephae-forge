import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Loader2, Mail, ArrowRight, X, Activity, TrendingUp, Zap } from 'lucide-react';

interface SaveReportBannerProps {
  isOpen: boolean;
  onGoogleSignIn: () => Promise<void>;
  onEmailSubmit: (email: string) => Promise<void>;
  onDismiss: () => void;
}

export function SaveReportBanner({ isOpen, onGoogleSignIn, onEmailSubmit, onDismiss }: SaveReportBannerProps) {
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [showEmailFallback, setShowEmailFallback] = useState(false);
  const [email, setEmail] = useState('');
  const [isSubmittingEmail, setIsSubmittingEmail] = useState(false);
  const [error, setError] = useState('');

  // Reset state when banner opens
  useEffect(() => {
    if (isOpen) {
      setIsSigningIn(false);
      setShowEmailFallback(false);
      setEmail('');
      setIsSubmittingEmail(false);
      setError('');
    }
  }, [isOpen]);

  const handleGoogleSignIn = async () => {
    setError('');
    setIsSigningIn(true);
    try {
      await onGoogleSignIn();
    } catch {
      setError('Sign-in failed. Please try again.');
      setIsSigningIn(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address.');
      return;
    }
    setError('');
    setIsSubmittingEmail(true);
    try {
      await onEmailSubmit(email);
    } catch {
      setError('Something went wrong. Please try again.');
      setIsSubmittingEmail(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, y: 40, x: 20 }}
          animate={{ opacity: 1, y: 0, x: 0 }}
          exit={{ opacity: 0, y: 40, x: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="fixed bottom-6 right-6 z-[9999] w-[360px] max-w-[calc(100vw-2rem)]"
        >
          <div className="bg-slate-900/90 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl shadow-black/40 overflow-hidden">
            {/* Close button */}
            <button
              onClick={onDismiss}
              className="absolute top-3 right-3 z-10 p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="p-5">
              {/* Header */}
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <Shield className="w-4.5 h-4.5 text-white" />
                </div>
                <div>
                  <h3 className="text-white font-semibold text-sm">Save this report</h3>
                  <p className="text-slate-400 text-xs">Free forever. No credit card.</p>
                </div>
              </div>

              {/* Compact benefits */}
              <div className="flex gap-3 mb-4 text-xs text-slate-300">
                <span className="flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-400" /> Weekly monitoring</span>
                <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3 text-purple-400" /> Track scores</span>
                <span className="flex items-center gap-1"><Zap className="w-3 h-3 text-amber-400" /> Any device</span>
              </div>

              {/* Google Sign-In Button */}
              <button
                onClick={handleGoogleSignIn}
                disabled={isSigningIn}
                className="w-full py-2.5 px-4 bg-white hover:bg-gray-50 text-gray-800 font-medium rounded-xl shadow-lg transition-all flex items-center justify-center gap-2.5 text-sm disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {isSigningIn ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                    </svg>
                    Sign in with Google
                  </>
                )}
              </button>

              {/* Email fallback */}
              {!showEmailFallback ? (
                <button
                  onClick={() => setShowEmailFallback(true)}
                  className="w-full mt-2 py-2 px-4 bg-white/5 hover:bg-white/10 text-slate-300 text-xs rounded-xl transition-all flex items-center justify-center gap-1.5"
                >
                  <Mail className="w-3 h-3" />
                  Continue with email
                </button>
              ) : (
                <form onSubmit={handleEmailSubmit} className="mt-2 flex gap-2">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@email.com"
                    className="flex-1 px-3 py-2 bg-white/10 border border-white/10 rounded-xl text-white text-xs placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all"
                    disabled={isSubmittingEmail}
                    autoFocus
                  />
                  <button
                    type="submit"
                    disabled={isSubmittingEmail}
                    className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-medium transition-all disabled:opacity-70 disabled:cursor-not-allowed"
                  >
                    {isSubmittingEmail ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
                  </button>
                </form>
              )}

              {error && (
                <p className="text-red-400 text-xs mt-2 px-1">{error}</p>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Keep backward-compatible export name
export { SaveReportBanner as AuthWall };
