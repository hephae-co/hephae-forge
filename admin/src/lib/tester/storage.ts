export interface TestResult {
    businessName: string;
    capability: string;
    score: number;
    isHallucinated: boolean;
    issues: string[];
    responseTimeMs: number;
}

export interface SystemResult {
    testName: string;
    status: 'pass' | 'fail';
    message: string;
}

export interface RunSummary {
    runId: string;
    timestamp: string;
    totalTests: number;
    passedTests: number;
    failedTests: number;
    results: TestResult[];
    systemResults?: SystemResult[];
}
