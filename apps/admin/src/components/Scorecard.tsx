import { RunSummary, TestResult } from '@/lib/tester/storage';
import { AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

export default function Scorecard({ run }: { run: RunSummary }) {
    return (
        <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-8 transition-all hover:shadow-md hover:border-gray-300">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h3 className="text-xl font-bold text-gray-900">Test Run: {new Date(run.timestamp).toLocaleString()}</h3>
                    <p className="text-sm text-gray-500">ID: {run.runId}</p>
                </div>
                <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">
                        {Math.round((run.passedTests / run.totalTests) * 100)}% Health
                    </p>
                    <p className="text-sm text-gray-500">{run.passedTests} Passed / {run.failedTests} Failed</p>
                </div>
            </div>

            {run.systemResults && run.systemResults.length > 0 && (
                <div className="mb-6">
                    <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Technical System Checks</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {run.systemResults.map((sys, idx) => (
                            <div key={idx} className="bg-gray-50 border border-gray-200 p-3 rounded-lg flex items-center gap-3">
                                {sys.status === 'pass' ? <CheckCircle2 className="text-green-500 w-5 h-5 flex-shrink-0" /> : <XCircle className="text-red-500 w-5 h-5 flex-shrink-0" />}
                                <div className="min-w-0">
                                    <p className="text-sm font-medium text-gray-800 truncate">{sys.testName}</p>
                                    <p className="text-xs text-gray-500 truncate">{sys.message}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Capability Evaluations</h4>
            <div className="space-y-4">
                {run.results.map((res: TestResult, idx: number) => {
                    const passed = res.score >= 80 && !res.isHallucinated;
                    return (
                        <div key={idx} className="bg-gray-50 rounded-lg p-4 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center border border-gray-200 hover:border-gray-300 transition-colors">
                            <div className="flex gap-3 items-start">
                                {passed ? <CheckCircle2 className="text-green-500 w-6 h-6 mt-1" /> : <XCircle className="text-red-500 w-6 h-6 mt-1" />}
                                <div>
                                    <h4 className="font-semibold text-gray-900">{res.businessName} <span className="text-xs uppercase bg-indigo-100 px-2 py-1 rounded ml-2 font-mono tracking-tighter text-indigo-600">{res.capability}</span></h4>
                                    {!passed && res.issues?.length > 0 && (
                                        <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded border border-red-200">
                                            <ul className="list-disc list-inside">
                                                {res.issues.map((i, iIdx) => <li key={iIdx}>{i}</li>)}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div className="text-right whitespace-nowrap">
                                <p className={`text-lg font-bold ${passed ? 'text-gray-900' : 'text-red-500'}`}>{res.score}/100</p>
                                <p className="text-xs text-gray-400">{res.responseTimeMs}ms</p>
                                {res.isHallucinated && (
                                    <span className="inline-flex items-center gap-1 text-xs text-orange-600 mt-1 bg-orange-50 px-2 py-1 rounded border border-orange-200">
                                        <AlertCircle className="w-3 h-3" /> Hallucinated
                                    </span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
