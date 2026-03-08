import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Lock, ArrowRight, Loader2, Calendar, ExternalLink } from 'lucide-react';

interface EmailWallProps {
    isOpen: boolean;
    onSubmit: (email: string) => Promise<void>;
}

export function EmailWall({ isOpen, onSubmit }: EmailWallProps) {
    const [email, setEmail] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email || !email.includes('@')) {
            setError("Please enter a valid email address.");
            return;
        }

        setError('');
        setIsSubmitting(true);
        try {
            await onSubmit(email);
        } catch (err) {
            setError("Something went wrong. Please try again.");
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
                                <Lock className="w-8 h-8 text-white" />
                            </div>

                            <h2 className="text-2xl font-bold text-white mb-2">
                                Unlock AI Insights
                            </h2>
                            <p className="text-slate-300 text-sm mb-8 leading-relaxed">
                                Hephae is actively compiling your surgical report. Enter your email to securely unlock the dashboard and save your analysis.
                            </p>

                            <form onSubmit={handleSubmit} className="space-y-4 text-left">
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
                                        disabled={isSubmitting}
                                    />
                                </div>

                                {error && (
                                    <p className="text-red-400 text-sm px-1">{error}</p>
                                )}

                                <button
                                    type="submit"
                                    disabled={isSubmitting}
                                    className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-blue-500/25 transition-all flex items-center justify-center gap-2 group disabled:opacity-70 disabled:cursor-not-allowed"
                                >
                                    {isSubmitting ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : (
                                        <>
                                            Unlock Dashboard
                                            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                                        </>
                                    )}
                                </button>
                            </form>

                            <p className="text-slate-500 text-xs mt-6">
                                We'll never share your email with third parties.
                            </p>

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
