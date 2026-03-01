import { BigQuery } from '@google-cloud/bigquery';

// Singleton BigQuery client — reused across all API route invocations
const g = global as typeof globalThis & { _bqClient?: BigQuery };

if (!g._bqClient) {
    g._bqClient = new BigQuery({ projectId: 'hephae-co-dev' });
}

export const bq = g._bqClient;
export const DATASET = 'hephae';
