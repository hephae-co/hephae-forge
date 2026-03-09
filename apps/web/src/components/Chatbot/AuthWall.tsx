import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Loader2, Calendar, ExternalLink, Mail, ArrowRight, X } from 'lucide-react';

interface AuthWallProps {
  isOpen: boolean;
  onGoogleSignIn: () => Promise<void>;
  onEmailSubmit: (email: string) => Promise<void>;
  onSkip: () => void;
}

export function AuthWall({ isOpen, onGoogleSignIn, onEmailSubmit, onSkip }: AuthWallProps) {
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [showEmailFallback, setShowEmailFallback] = useState(false);
  const [email, setEmail] = useState('');
  const [isSubmittingEmail, setIsSubmittingEmail] = useState(false);
  const [error, setError] = useState('');

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
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
        >
          <motion.div
            initial={{ scale: 0.9, y: 20, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            transition={{ delay: 0.1, duration: 0.3 }}
            className="w-full max-w-md bg-white/5 border border-white/10 p-8 rounded-3xl shadow-2xl relative overflow-hidden"
          >
            {/* Decorative background glow */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-purple-500/20 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-blue-500/20">
                <Shield className="w-8 h-8 text-white" />
              </div>

              <h2 className="text-2xl font-bold text-white mb-2">
                Save Your Report
              </h2>
              <p className="text-slate-300 text-sm mb-8 leading-relaxed">
                Sign in to save this report to your account, track changes over time, and access all your business analyses in one place.
              </p>

              <div className="space-y-3">
                {/* Google Sign-In Button */}
                <button
                  onClick={handleGoogleSignIn}
                  disabled={isSigningIn}
                  className="w-full py-3 px-4 bg-white hover:bg-gray-50 text-gray-800 font-medium rounded-xl shadow-lg transition-all flex items-center justify-center gap-3 disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  {isSigningIn ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <svg className="w-5 h-5" viewBox="0 0 24 24">
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
                    className="w-full py-3 px-4 bg-white/10 hover:bg-white/15 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2"
                  >
                    <Mail className="w-4 h-4" />
                    Continue with email only
                  </button>
                ) : (
                  <form onSubmit={handleEmailSubmit} className="space-y-3 text-left">
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <Mail className="h-5 w-5 text-slate-400" />
                      </div>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter your email address..."
                        className="w-full pl-11 pr-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                        disabled={isSubmittingEmail}
                        autoFocus
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isSubmittingEmail}
                      className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-blue-500/25 transition-all flex items-center justify-center gap-2 group disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                      {isSubmittingEmail ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          Save Report
                          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                        </>
                      )}
                    </button>
                  </form>
                )}

                {error && (
                  <p className="text-red-400 text-sm px-1">{error}</p>
                )}

                {/* Skip */}
                <button
                  onClick={onSkip}
                  className="w-full py-2 text-slate-500 hover:text-slate-300 text-sm transition-colors flex items-center justify-center gap-1"
                >
                  <X className="w-3 h-3" />
                  Continue as guest
                </button>
              </div>

              <div className="mt-6 pt-5 border-t border-white/10">
                <p className="text-slate-400 text-xs mb-3">Want to talk to a human?</p>
                <a
                  href="https://hephae.co/schedule"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-blue-400 hover:text-blue-300 transition-colors"
                >
                  <Calendar className="w-4 h-4" />
                  Schedule an intro call
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
