import { NextRequest, NextResponse } from "next/server";
import { discoveryParallelAgent } from "@/lib/agents/core/discoverySubAgents";
import { BaseIdentity, EnrichedProfile } from "@/lib/agents/core/types";
import { Runner, InMemorySessionService } from "@google/adk";

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const identity: BaseIdentity = body.identity;

        if (!identity || !identity.officialUrl) {
            return NextResponse.json({ error: "Missing BaseIdentity" }, { status: 400 });
        }

        console.log(`[API/Discover] Spawning ADK Orchestrator for: ${identity.name}`);
        const sessionService = new InMemorySessionService();
        const runner = new Runner({
            appName: 'hephae-hub',
            agent: discoveryParallelAgent,
            sessionService
        });

        const sessionId = "discovery-" + Date.now();
        const userId = "hub-user";

        await sessionService.createSession({
            appName: 'hephae-hub',
            userId,
            sessionId,
            state: {}
        });

        const prompt = `
            Please discover the menu, social links, and Google Maps URL for:
            Name: ${identity.name}
            Address: ${identity.address}
            URL: ${identity.officialUrl}
        `;

        const stream = runner.runAsync({
            userId,
            sessionId,
            newMessage: { role: 'user', parts: [{ text: prompt }] }
        });

        // Drain the generator to await completion of all sub-agents
        for await (const event of stream) { }

        const finalSession = await sessionService.getSession({ appName: 'hephae-hub', userId, sessionId });
        const state = finalSession?.state || {};

        console.log("[API/Discover] ADK Pipeline Finished. State keys:", Object.keys(state));

        // Safely parse social links if Gemini included markdown
        let parsedSocials = {};
        if (typeof state.socialLinks === 'string') {
            try {
                const cleanStr = state.socialLinks.replace(/```json/g, '').replace(/```/g, '').trim();
                parsedSocials = JSON.parse(cleanStr);
            } catch (e) {
                console.warn("[API/Discover] Failed to parse social links JSON:", e);
            }
        } else if (typeof state.socialLinks === 'object') {
            parsedSocials = state.socialLinks as any;
        }

        const enrichedProfile: EnrichedProfile = {
            ...identity,
            menuScreenshotBase64: state.menuScreenshotBase64 as string | undefined,
            socialLinks: parsedSocials,
            googleMapsUrl: state.googleMapsUrl as string | undefined
        };

        return NextResponse.json(enrichedProfile);

    } catch (error) {
        console.error("[API/Discover] Orchestration Failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
