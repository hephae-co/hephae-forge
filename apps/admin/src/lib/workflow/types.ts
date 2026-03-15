export type WorkflowPhase = 'discovery' | 'qualification' | 'analysis' | 'evaluation' | 'approval' | 'outreach' | 'completed' | 'failed';

export type BusinessPhase =
    | 'pending'
    | 'enriching'
    | 'analyzing'
    | 'analysis_done'
    | 'evaluating'
    | 'evaluation_done'
    | 'approved'
    | 'rejected'
    | 'outreaching'
    | 'outreach_done'
    | 'outreach_failed';

export interface EvaluationResult {
    score: number;
    isHallucinated: boolean;
    issues: string[];
}

export interface BusinessInsights {
    summary: string;
    keyFindings: string[];
    recommendations: string[];
    generatedAt: string;
}

export interface BusinessWorkflowState {
    slug: string;
    name: string;
    address: string;
    officialUrl?: string | null;
    sourceZipCode?: string | null;
    businessType?: string | null;
    phase: BusinessPhase;
    capabilitiesCompleted: string[];
    capabilitiesFailed: string[];
    evaluations: Record<string, EvaluationResult>;
    qualityPassed: boolean;
    enrichedProfile?: Record<string, any> | null;
    insights?: BusinessInsights | null;
    outreachError?: string | null;
    lastError?: string | null;
}

export interface WorkflowProgress {
    totalBusinesses: number;
    qualificationQualified?: number;
    qualificationParked?: number;
    qualificationDisqualified?: number;
    analysisComplete: number;
    evaluationComplete?: number;
    qualityPassed: number;
    qualityFailed?: number;
    approved?: number;
    outreachComplete: number;
    insightsComplete?: number;
    zipCodesScanned?: number;
    zipCodesTotal?: number;
}

export interface WorkflowDocument {
    id: string;
    zipCode: string;
    businessType?: string | null;
    county?: string | null;
    zipCodes?: string[] | null;
    resolvedFrom?: 'single' | 'county' | null;
    phase: WorkflowPhase;
    createdAt: string;
    updatedAt: string;
    businesses: BusinessWorkflowState[];
    progress: WorkflowProgress;
    lastError?: string | null;
    retryCount?: number;
}

export interface ProgressEvent {
    type: string;
    workflowId: string;
    phase: WorkflowPhase;
    message: string;
    businessSlug?: string | null;
    progress: WorkflowProgress;
    timestamp: string;
}
