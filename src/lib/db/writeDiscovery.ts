/**
 * writeDiscovery — write path for discovery agent runs.
 *
 * Writes to:
 *   1. Firestore businesses/{slug} — creates/updates the business document with current identity
 *   2. BigQuery hephae.discoveries — permanent append-only record of every discovery run
 *
 * RULE: raw_data must never contain menuScreenshotBase64 or any binary blob.
 *       Pass menuImageUrl (GCS URL) instead.
 */

import { Timestamp, FieldValue } from 'firebase-admin/firestore';
import { db } from '@/lib/firebase';
import { bq, DATASET } from './bigquery';
import { EnrichedProfile } from '@/agents/types';
import { AgentVersions } from '@/agents/config';

/**
 * Strips binary blobs from an EnrichedProfile before any database write.
 * menuScreenshotBase64 must be uploaded to GCS and replaced with a URL before calling this.
 */
export function stripBlobs(profile: EnrichedProfile): Omit<EnrichedProfile, 'menuScreenshotBase64'> {
    const { menuScreenshotBase64: _stripped, ...safe } = profile;
    return safe;
}

/**
 * Parse zip code from an address string as a best-effort fallback.
 * Prefer passing zipCode explicitly when available.
 */
function parseZipCode(address?: string): string | null {
    if (!address) return null;
    const match = address.match(/\b(\d{5})(?:-\d{4})?\b/);
    return match ? match[1] : null;
}

export interface WriteDiscoveryOptions {
    profile: EnrichedProfile;
    menuImageUrl?: string;       // GCS URL to menu screenshot — replaces base64
    zipCode?: string;            // explicit zip; falls back to parsing from address
    triggeredBy: 'user' | 'weekly_job' | 'api_v1';
}

export async function writeDiscovery(opts: WriteDiscoveryOptions): Promise<void> {
    const { profile, menuImageUrl, triggeredBy } = opts;
    const runAt = new Date();
    const runId = `discovery-${runAt.getTime()}`;

    const zipCode = opts.zipCode ?? parseZipCode(profile.address) ?? undefined;

    // Never write base64 blobs to Firestore or BQ
    const safe = stripBlobs(profile);

    // --- 1. Firestore upsert ---
    try {
        await db.doc(`businesses/${profile.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`).set({
            name: profile.name,
            address: profile.address ?? null,
            officialUrl: profile.officialUrl,
            coordinates: profile.coordinates ?? null,
            ...(zipCode ? { zipCode } : {}),
            updatedAt: Timestamp.fromDate(runAt),
            createdAt: FieldValue.serverTimestamp(),   // ignored if doc already exists via merge
            identity: {
                phone: profile.phone ?? null,
                email: profile.email ?? null,
                hours: profile.hours ?? null,
                googleMapsUrl: profile.googleMapsUrl ?? null,
                socialLinks: profile.socialLinks ?? {},
                logoUrl: profile.logoUrl ?? null,
                favicon: profile.favicon ?? null,
                primaryColor: profile.primaryColor ?? null,
                secondaryColor: profile.secondaryColor ?? null,
                persona: profile.persona ?? null,
                menuImageUrl: menuImageUrl ?? null,
                competitors: profile.competitors ?? [],
            },
        }, { merge: true });
    } catch (err) {
        console.error(`[DB] Firestore writeDiscovery failed for ${profile.name}:`, err);
    }

    // --- 2. BigQuery append ---
    const row = {
        run_id: runId,
        business_slug: profile.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
        business_name: profile.name,
        official_url: profile.officialUrl,
        address: profile.address ?? null,
        city: null,   // future: parse from address
        state: null,  // future: parse from address
        zip_code: zipCode ?? null,
        lat: profile.coordinates?.lat ?? null,
        lng: profile.coordinates?.lng ?? null,
        agent_name: 'discovery_orchestrator',
        agent_version: AgentVersions.MENU_DISCOVERY,  // orchestrator version tracks the pipeline
        run_at: runAt.toISOString(),
        triggered_by: triggeredBy,
        raw_data: JSON.stringify({
            ...safe,
            menuImageUrl: menuImageUrl ?? null,
        }),
    };

    bq.dataset(DATASET).table('discoveries').insert([row], { skipInvalidRows: false })
        .catch(err => {
            console.error(`[DB] BQ discoveries write failed for ${runId}:`, err?.errors ?? err);
        });
}
