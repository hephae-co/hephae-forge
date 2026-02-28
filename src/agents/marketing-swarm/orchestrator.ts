import { CreativeDirectorAgent } from "./creativeDirector";
import { PlatformRouterAgent } from "./platformRouter";
import { InstagramCopywriterAgent, BlogCopywriterAgent } from "./copywriters";
import { Runner, InMemorySessionService } from "@google/adk";
import { db } from "@/lib/firebase";

async function runAdkAgent(agent: any, input: string) {
    const sessionService = new InMemorySessionService();
    const sessionId = "marketing-" + Date.now() + Math.random().toString(36).substring(7);
    const runner = new Runner({ appName: 'hephae-marketing', agent, sessionService });

    await sessionService.createSession({ appName: 'hephae-marketing', sessionId, userId: 'sys', state: {} });

    const stream = runner.runAsync({
        sessionId, userId: 'sys',
        newMessage: { role: 'user', parts: [{ text: input }] }
    });

    let textBuffer = "";
    for await (const rawEvent of stream) {
        const event = rawEvent as any;
        if (event.content?.parts) {
            for (const part of event.content.parts) {
                if (part.text) textBuffer += part.text;
            }
        }
    }
    return textBuffer;
}

export async function generateAndDraftMarketingContent(report: any, source: string) {
    console.log(`[Marketing Swarm] 🚀 Background Generation Triggered for ${source} report.`);

    try {
        // 1. Creative Director Strategy
        console.log("[Marketing Swarm] Executing CreativeDirectorAgent...");
        const directorRaw = await runAdkAgent(CreativeDirectorAgent, JSON.stringify(report));
        const directorPayload = JSON.parse(directorRaw.replace(/```json|```/gi, '').trim());

        // 2. Routing
        console.log("[Marketing Swarm] Executing PlatformRouterAgent...");
        const routerRaw = await runAdkAgent(PlatformRouterAgent, JSON.stringify(directorPayload));
        const routerPayload = JSON.parse(routerRaw.replace(/```json|```/gi, '').trim());

        // 3. Copywriting
        let finalCopy = "";
        let platform = routerPayload.platform;

        console.log(`[Marketing Swarm] Routing to ${platform} Copywriter...`);
        if (platform === "Instagram" || platform === "Facebook") {
            const input = JSON.stringify({
                ...directorPayload,
                restaurant_name: report.identity?.name || "Unknown Business",
                social_handle: report.identity?.socialLinks?.instagram || report.identity?.socialLinks?.facebook || ""
            });
            const captionRaw = await runAdkAgent(InstagramCopywriterAgent, input);
            const captionPayload = JSON.parse(captionRaw.replace(/```json|```/gi, '').trim());
            finalCopy = captionPayload.caption;
        } else {
            // Default to Blog or Twitter style
            const input = JSON.stringify({
                ...directorPayload,
                restaurant_name: report.identity?.name || "Unknown Business",
            });
            const draftRaw = await runAdkAgent(BlogCopywriterAgent, input);
            const draftPayload = JSON.parse(draftRaw.replace(/```json|```/gi, '').trim());
            finalCopy = draftPayload.draft;
        }

        // 4. Save to Firestore for Review
        const dbRef = db.collection('marketing_drafts').doc();
        await dbRef.set({
            business_name: report.identity?.name || "Unknown",
            source_capability: source,
            platform: platform,
            strategy_hook: directorPayload.hook,
            data_point: directorPayload.data_point,
            copy: finalCopy,
            status: 'draft',
            created_at: new Date()
        });

        console.log(`[Marketing Swarm] ✅ Successfully saved Draft to Firestore (ID: ${dbRef.id})`);

    } catch (e: any) {
        console.error("[Marketing Swarm] ❌ Pipeline Failed:", e.message);
    }
}
