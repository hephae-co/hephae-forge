import { useEffect, useState } from 'react';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, onSnapshot, doc, updateDoc, deleteDoc } from 'firebase/firestore';
import { Instagram, Facebook, FileText, Check, X, Loader2, Sparkles, AlertTriangle } from 'lucide-react';

export default function MarketingAdmin() {
    const [drafts, setDrafts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const q = query(collection(db, 'marketing_drafts'), orderBy('created_at', 'desc'));
        const unsubscribe = onSnapshot(q, (snapshot) => {
            const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
            setDrafts(data);
            setLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const handleApprove = async (id: string) => {
        // In a real app this would call an API route to trigger the actual Instagram Graph API publishing tool (Phase 11.3)
        await updateDoc(doc(db, 'marketing_drafts', id), { status: 'published' });
        alert("Action Simulated: Post sent to Social Media API for publishing!");
    };

    const handleReject = async (id: string) => {
        await deleteDoc(doc(db, 'marketing_drafts', id));
    };

    if (loading) {
        return <div className="min-h-screen bg-slate-950 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div>;
    }

    return (
        <div className="min-h-screen bg-slate-950 p-8 text-white">
            <header className="mb-10 max-w-5xl mx-auto flex items-center gap-4">
                <div className="p-3 bg-indigo-500/20 rounded-2xl border border-indigo-500/30">
                    <Sparkles className="w-8 h-8 text-indigo-400" />
                </div>
                <div>
                    <h1 className="text-3xl font-bold font-mono">Hephae PR Hub</h1>
                    <p className="text-slate-400">Agentic Marketing Swarm Review Queue</p>
                </div>
            </header>

            <div className="max-w-5xl mx-auto space-y-6">
                {drafts.length === 0 ? (
                    <div className="text-center p-12 border border-slate-800 rounded-3xl bg-slate-900/50">
                        <p className="text-slate-500 font-mono">Queue is empty. Waiting for users to run Diagnostics...</p>
                    </div>
                ) : drafts.map(draft => (
                    <div key={draft.id} className={\`p-6 rounded-3xl border \${draft.status === 'published' ? 'border-emerald-500/30 bg-emerald-950/20 opacity-50' : 'border-indigo-500/30 bg-slate-900'} relative overflow-hidden\`}>
                <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                        {draft.platform === 'Instagram' && <Instagram size={24} className="text-pink-500" />}
                        {draft.platform === 'Facebook' && <Facebook size={24} className="text-blue-500" />}
                        {draft.platform === 'Blog' && <FileText size={24} className="text-emerald-500" />}

                        <div>
                            <h3 className="font-bold text-lg">{draft.business_name}</h3>
                            <span className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-400 font-mono">Trigger: {draft.source_capability}</span>
                        </div>
                    </div>

                    {draft.status !== 'published' && (
                        <div className="flex gap-2">
                            <button onClick={() => handleReject(draft.id)} className="p-2 hover:bg-red-500/20 rounded-full text-red-400 transition-colors">
                                <X size={20} />
                            </button>
                            <button onClick={() => handleApprove(draft.id)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-full text-white font-bold transition-colors">
                                <Check size={18} /> Approve & Publish
                            </button>
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                    <div className="space-y-4">
                        <div>
                            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Creative Director Hook</div>
                            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-300">
                                {draft.strategy_hook}
                            </div>
                        </div>
                        <div>
                            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 flex gap-1 items-center">
                                <AlertTriangle size={12} className="text-orange-500" />
                                Extracted Data Fact
                            </div>
                            <div className="p-3 rounded-xl bg-orange-950/30 border border-orange-500/20 text-sm text-orange-200 font-mono">
                                "{draft.data_point}"
                            </div>
                        </div>
                    </div>

                    <div>
                        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Generated {draft.platform} Copy</div>
                        <div className="p-4 rounded-xl bg-black border border-indigo-500/20 text-slate-200 whitespace-pre-wrap font-sans text-sm h-full leading-loose">
                            {draft.copy}
                        </div>
                    </div>
                </div>
            </div>
                ))}
        </div>
        </div >
    );
}
