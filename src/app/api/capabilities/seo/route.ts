import { NextResponse } from 'next/server';
import { SeoAuditorAgent } from '@/agents/seo-auditor/seoAuditor';
import { generateAndDraftMarketingContent } from '@/agents/marketing-swarm/orchestrator';

export const maxDuration = 60;

import { BaseIdentity } from '@/agents/types';
import { Runner, InMemorySessionService } from '@google/adk';

export async function POST(req: Request) {
    try {
        const { identity } = await req.json() as { identity: BaseIdentity };

        if (!identity.officialUrl) {
            return NextResponse.json({ error: "No URL available for SEO Audit." }, { status: 400 });
        }

        console.log(`[SEO API] Launching SeoAuditorAgent for ${identity.officialUrl}...`);

        const sessionService = new InMemorySessionService();
        const runner = new Runner({
            appName: 'hephae-hub',
            agent: SeoAuditorAgent,
            sessionService
        });

        const sessionId = "seo-" + Date.now();
        const userId = "hub-user";

        await sessionService.createSession({
            appName: 'hephae-hub',
            userId,
            sessionId,
            state: {}
        });

        const stream = runner.runAsync({
            userId,
            sessionId,
            newMessage: {
                role: 'user',
                parts: [{ text: `Execute a full SEO Deep Dive on ${identity.officialUrl}. Evaluate technical SEO, content quality, user experience, performance, and backlinks.` }]
            }
        });

        let finalModelText = "";

        // Drain the generator and capture output text
        for await (const event of stream) {
            if ((event as any).type === 'agentMessage' && (event as any).message?.role === 'model' && (event as any).message.parts[0]?.text) {
                finalModelText = (event as any).message.parts[0].text;
            }
        }

        const finalSession = await sessionService.getSession({ appName: 'hephae-hub', userId, sessionId });
        const state = finalSession?.state || {};

        let reportData = state;

        if (finalModelText) {
            const rawText = finalModelText.replace(/```json/gi, '').replace(/```/g, '').trim();
            try {
                const parsed = JSON.parse(rawText);
                reportData = parsed;
                console.log(`[SEO API] Successfully parsed report with ${parsed.sections?.length} sections`);
            } catch (e) {
                console.warn("Could not parse direct JSON from SeoAuditorAgent output.", e);
            }
        }

        // Add the target URL to the response
        const finalReport = {
            ...reportData,
            url: identity.officialUrl
        };

        // Fire and forget marketing generation
        generateAndDraftMarketingContent({ identity, seo: finalReport }, 'SEO Deep Audit').catch(console.error);

        return NextResponse.json(finalReport);
    } catch (e: any) {
        console.error("[SEO API Error]:", e);
        return NextResponse.json({ error: e.message }, { status: 500 });
    }
}
