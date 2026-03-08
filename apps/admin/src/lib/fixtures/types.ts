import { BusinessWorkflowState } from '@/lib/workflow/types';

export type FixtureType = 'grounding' | 'failure_case';

export interface FixtureIdentity {
    name: string;
    address: string;
    email?: string | null;
    socialLinks?: Record<string, string> | null;
    docId: string;
}

export interface TestFixture {
    id: string;
    fixtureType: FixtureType;
    sourceWorkflowId: string;
    sourceZipCode?: string | null;
    businessType?: string | null;
    savedAt: string;
    notes?: string | null;
    businessState?: BusinessWorkflowState | null;
    identity: FixtureIdentity;
    latestOutputs?: Record<string, any>;
}
