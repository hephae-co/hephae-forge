import { NextRequest, NextResponse } from "next/server";
import { discoveryParallelAgent } from '@/agents/discovery/discoverySubAgents';
import { BaseIdentity, EnrichedProfile } from '@/agents/types';
import { Runner, InMemorySessionService } from "@google/adk";
import { GoogleGenerativeAI } from "@google/generative-ai";

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
            Please discover the menu, social links, Google Maps URL, and exactly 3 local competitors for:
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

        // Safely parse competitors if Gemini included markdown
        let parsedCompetitors = [];
        if (typeof state.competitors === 'string') {
            try {
                const cleanStr = state.competitors.replace(/```json/g, '').replace(/```/g, '').trim();
                parsedCompetitors = JSON.parse(cleanStr);
            } catch (e) {
                console.warn("[API/Discover] Failed to parse competitors JSON explicitly, running intelligent extraction...");
                try {
                    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
                    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash", generationConfig: { responseMimeType: "application/json" } });
                    const res = await model.generateContent(`Extract exactly 3 restaurant competitors from the following text into a JSON array of objects with strictly these keys: "name", "url", "reason". TEXT: ${state.competitors}`);
                    parsedCompetitors = JSON.parse(res.response.text());
                } catch (extractErr) {
                    console.error("[API/Discover] Forced extraction failed", extractErr);
                }
            }
        } else if (Array.isArray(state.competitors)) {
            parsedCompetitors = state.competitors;
        }

        const enrichedProfile: EnrichedProfile = {
            ...identity,
            menuScreenshotBase64: state.menuScreenshotBase64 as string | undefined,
            socialLinks: parsedSocials,
            googleMapsUrl: state.googleMapsUrl as string | undefined,
            competitors: parsedCompetitors.length > 0 ? parsedCompetitors : undefined
        };

        return NextResponse.json(enrichedProfile);

    } catch (error) {
        console.error("[API/Discover] Orchestration Failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
