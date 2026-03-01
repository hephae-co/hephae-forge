import { storage } from './firebase';
import { StorageConfig } from '@/agents/config';
import { EnrichedProfile } from '@/agents/types';

export type ReportType = 'profile' | 'margin' | 'traffic' | 'seo' | 'competitive';

export interface SaveReportOptions {
    slug: string;
    type: ReportType;
    htmlContent: string;
    identity?: Partial<EnrichedProfile>;
    summary?: string;
}

/**
 * Converts a business name to a URL-safe slug.
 * e.g. "Bosphorus Nutley" → "bosphorus-nutley"
 */
export function generateSlug(name: string): string {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-')
        .replace(/-+/g, '-');
}

/**
 * Uploads a base64 menu screenshot to GCS and returns the public URL.
 * Replaces the old pattern of storing base64 in Firestore.
 */
export async function uploadMenuScreenshot(slug: string, base64: string): Promise<string> {
    const ts = Date.now();
    const objectPath = `${slug}/menu-${ts}.jpg`;
    const publicUrl = `${StorageConfig.BASE_URL}/${objectPath}`;

    try {
        const buffer = Buffer.from(base64.replace(/^data:image\/\w+;base64,/, ''), 'base64');
        const file = storage.file(objectPath);
        await file.save(buffer, {
            contentType: 'image/jpeg',
            metadata: { cacheControl: 'public, max-age=86400' },
        });
        await file.makePublic();
        console.log(`[ReportStorage] Uploaded menu screenshot → ${publicUrl}`);
        return publicUrl;
    } catch (err) {
        console.warn(`[ReportStorage] Failed to upload menu screenshot for ${slug}:`, err);
        return '';
    }
}

/**
 * Uploads an HTML report to GCS and returns the public URL.
 * Never touches Firestore — that is now handled by writeAgentResult / writeDiscovery.
 */
export async function uploadReport(opts: SaveReportOptions): Promise<string> {
    const { slug, type, htmlContent } = opts;
    const ts = Date.now();
    const fileName = `${type}-${ts}.html`;
    const objectPath = `${slug}/${fileName}`;
    const publicUrl = `${StorageConfig.BASE_URL}/${objectPath}`;

    try {
        const file = storage.file(objectPath);
        await file.save(htmlContent, {
            contentType: 'text/html; charset=utf-8',
            metadata: { cacheControl: 'public, max-age=3600' },
        });
        await file.makePublic();
        console.log(`[ReportStorage] Uploaded ${objectPath} → ${publicUrl}`);
        return publicUrl;
    } catch (err) {
        console.warn(`[ReportStorage] Failed to upload ${type} report for ${slug}:`, err);
        return '';
    }
}

/**
 * @deprecated Use uploadReport() + writeAgentResult() / writeDiscovery() instead.
 * Kept for any legacy callers during migration.
 */
export async function saveReport(opts: SaveReportOptions & { rawData?: unknown }): Promise<string> {
    return uploadReport(opts);
}
