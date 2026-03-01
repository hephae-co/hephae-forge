/**
 * writeAgentResult — single write path for all analysis agent outputs.
 *
 * Writes to two destinations:
 *   1. Firestore businesses/{slug}.latestOutputs.{agentName} — current state for fast app reads
 *   2. BigQuery hephae.analyses — permanent append-only history
 *
 * BQ write is fire-and-forget. Failures are logged to console but never block the API response.
 * Failed writes are NOT retried here — add a dead-letter mechanism if reliability becomes critical.
 *
 * RULE: raw_data must never contain binary blobs (base64 images, HTML).
 *       Strip menuScreenshotBase64 and any Buffer before calling this function.
 */

import { Timestamp } from 'firebase-admin/firestore';
import { db } from '@/lib/firebase';
import { bq, DATASET } from './bigquery';

export interface AgentResultOptions {
    businessSlug: string;
    businessName: string;
    zipCode?: string;
    agentName: string;          // e.g. 'seo_auditor', 'margin_surgeon'
    agentVersion: string;       // from AgentVersions in config.ts
    triggeredBy: 'user' | 'weekly_job' | 'api_v1';
    score?: number;             // 0-100, omit if agent doesn't produce a score
    summary?: string;
    reportUrl?: string;         // GCS public URL to HTML report
    kpis?: Record<string, string | number | boolean | null>; // 1-2 fields for Firestore dashboard display
    rawData: unknown;           // full agent output — blobs must be stripped before passing
}

// Type-specific promoted BQ columns extracted from rawData
interface PromotedKpis {
    total_leakage?: number;
    menu_item_count?: number;
    seo_technical_score?: number;
    seo_content_score?: number;
    seo_ux_score?: number;
    seo_performance_score?: number;
    seo_authority_score?: number;
    peak_slot_score?: number;
    competitor_count?: number;
    avg_threat_level?: number;
}

function extractPromotedKpis(agentName: string, rawData: unknown): PromotedKpis {
    const d = rawData as any;
    if (!d) return {};

    switch (agentName) {
        case 'margin_surgeon':
            return {
                total_leakage: typeof d.total_leakage === 'number' ? d.total_leakage : undefined,
                menu_item_count: Array.isArray(d.menu_items) ? d.menu_items.length : undefined,
            };
        case 'seo_auditor': {
            const sections: any[] = Array.isArray(d.sections) ? d.sections : [];
            const get = (id: string) => sections.find((s: any) => s.id === id)?.score ?? undefined;
            return {
                seo_technical_score: get('technical'),
                seo_content_score: get('content'),
                seo_ux_score: get('ux'),
                seo_performance_score: get('performance'),
                seo_authority_score: get('authority'),
            };
        }
        case 'traffic_forecaster': {
            const slots: any[] = Array.isArray(d.forecast)
                ? d.forecast.flatMap((day: any) => day.slots ?? [])
                : [];
            const peak = slots.length > 0 ? Math.max(...slots.map((s: any) => s.score ?? 0)) : undefined;
            return { peak_slot_score: peak };
        }
        case 'competitive_analyzer':
            return {
                competitor_count: Array.isArray(d.competitor_analysis) ? d.competitor_analysis.length : undefined,
                avg_threat_level: Array.isArray(d.competitor_analysis) && d.competitor_analysis.length > 0
                    ? d.competitor_analysis.reduce((sum: number, c: any) => sum + (c.threat_level ?? 0), 0) / d.competitor_analysis.length
                    : undefined,
            };
        default:
            return {};
    }
}

export async function writeAgentResult(opts: AgentResultOptions): Promise<void> {
    const {
        businessSlug, businessName, zipCode, agentName, agentVersion,
        triggeredBy, score, summary, reportUrl, kpis, rawData,
    } = opts;

    const runAt = new Date();
    const analysisId = `${agentName}-${runAt.getTime()}`;

    // --- 1. Firestore upsert (current state) ---
    try {
        await db.doc(`businesses/${businessSlug}`).set({
            updatedAt: Timestamp.fromDate(runAt),
            ...(zipCode ? { zipCode } : {}),
            [`latestOutputs.${agentName}`]: {
                score: score ?? null,
                summary: summary ?? null,
                reportUrl: reportUrl ?? null,
                agentVersion,
                runAt: Timestamp.fromDate(runAt),
                ...(kpis ?? {}),
            },
        }, { merge: true });
    } catch (err) {
        console.error(`[DB] Firestore write failed for ${businessSlug}/${agentName}:`, err);
    }

    // --- 2. BigQuery append (permanent history) — fire and forget ---
    const promoted = extractPromotedKpis(agentName, rawData);

    const row = {
        analysis_id: analysisId,
        business_slug: businessSlug,
        business_name: businessName,
        zip_code: zipCode ?? null,
        agent_name: agentName,
        agent_version: agentVersion,
        run_at: runAt.toISOString(),
        triggered_by: triggeredBy,
        score: score ?? null,
        summary: summary ?? null,
        report_url: reportUrl ?? null,
        // Promoted KPI columns
        total_leakage: promoted.total_leakage ?? null,
        menu_item_count: promoted.menu_item_count ?? null,
        seo_technical_score: promoted.seo_technical_score ?? null,
        seo_content_score: promoted.seo_content_score ?? null,
        seo_ux_score: promoted.seo_ux_score ?? null,
        seo_performance_score: promoted.seo_performance_score ?? null,
        seo_authority_score: promoted.seo_authority_score ?? null,
        peak_slot_score: promoted.peak_slot_score ?? null,
        competitor_count: promoted.competitor_count ?? null,
        avg_threat_level: promoted.avg_threat_level ?? null,
        // Full output — blobs must be stripped by caller
        raw_data: JSON.stringify(rawData),
    };

    bq.dataset(DATASET).table('analyses').insert([row], { skipInvalidRows: false })
        .catch(err => {
            console.error(`[DB] BQ analyses write failed for ${analysisId}:`, err?.errors ?? err);
        });
}
