/**
 * writeInteraction — records outreach events and inbound responses.
 *
 * Writes to:
 *   1. BigQuery hephae.interactions — permanent event log
 *   2. Firestore businesses/{slug}.crm — current CRM state update
 *
 * IMPORTANT: Only 'contact_form' and 'email_replied' are reliable responded signals.
 * 'email_opened' and 'report_link_clicked' are logged but do NOT flip crm.status.
 */

import { Timestamp } from 'firebase-admin/firestore';
import { db } from '@/lib/firebase';
import { bq, DATASET } from './bigquery';

export type InteractionEventType =
    | 'report_sent'           // outbound — initial report email
    | 'follow_up_sent'        // outbound — 2nd or 3rd touch
    | 'email_opened'          // inbound signal — NOT a reliable responded indicator
    | 'report_link_clicked'   // inbound signal — NOT a reliable responded indicator
    | 'contact_form'          // inbound — genuine response signal
    | 'email_replied';        // inbound — genuine response signal

const GENUINE_RESPONSE_EVENTS: InteractionEventType[] = ['contact_form', 'email_replied'];

export interface WriteInteractionOptions {
    businessSlug: string;
    zipCode?: string;
    eventType: InteractionEventType;
    contactEmail?: string;
    subject?: string;
    reportUrl?: string;
    outreachNumber?: number;  // 1, 2, or 3 — only for outbound events
}

export async function writeInteraction(opts: WriteInteractionOptions): Promise<void> {
    const { businessSlug, zipCode, eventType, contactEmail, subject, reportUrl, outreachNumber } = opts;
    const occurredAt = new Date();
    const interactionId = `${eventType}-${businessSlug}-${occurredAt.getTime()}`;
    const isGenuineResponse = GENUINE_RESPONSE_EVENTS.includes(eventType);

    // --- 1. Firestore CRM state update ---
    try {
        const isOutbound = eventType === 'report_sent' || eventType === 'follow_up_sent';
        const firestoreUpdate: Record<string, unknown> = {
            updatedAt: Timestamp.fromDate(occurredAt),
        };

        if (isOutbound && outreachNumber !== undefined) {
            firestoreUpdate['crm.outreachCount'] = outreachNumber;
            firestoreUpdate['crm.status'] = 'outreached';
            firestoreUpdate['crm.lastOutreachAt'] = Timestamp.fromDate(occurredAt);
            if (reportUrl) firestoreUpdate['crm.lastReportShared'] = reportUrl;
        }

        if (isGenuineResponse) {
            firestoreUpdate['crm.status'] = 'responded';
            firestoreUpdate['crm.respondedAt'] = Timestamp.fromDate(occurredAt);
        }

        await db.doc(`businesses/${businessSlug}`).set(firestoreUpdate, { merge: true });
    } catch (err) {
        console.error(`[DB] Firestore writeInteraction failed for ${businessSlug}:`, err);
    }

    // --- 2. BigQuery append (all events, including non-response signals) ---
    const row = {
        interaction_id: interactionId,
        occurred_at: occurredAt.toISOString(),
        business_slug: businessSlug,
        zip_code: zipCode ?? null,
        event_type: eventType,
        outreach_number: outreachNumber ?? null,
        contact_email: contactEmail ?? null,
        subject: subject ?? null,
        report_url: reportUrl ?? null,
        responded: isGenuineResponse,
    };

    bq.dataset(DATASET).table('interactions').insert([row], { skipInvalidRows: false })
        .catch(err => {
            console.error(`[DB] BQ interactions write failed for ${interactionId}:`, err?.errors ?? err);
        });
}

export async function archiveBusiness(
    businessSlug: string,
    reason: 'no_response' | 'not_interested' | 'converted'
): Promise<void> {
    try {
        await db.doc(`businesses/${businessSlug}`).set({
            'crm.status': 'archived',
            'crm.archivedAt': Timestamp.now(),
            'crm.archiveReason': reason,
            updatedAt: Timestamp.now(),
        }, { merge: true });
    } catch (err) {
        console.error(`[DB] archiveBusiness failed for ${businessSlug}:`, err);
    }
}
