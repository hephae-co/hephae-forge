import { NextRequest, NextResponse } from "next/server";
import { Runner, InMemorySessionService } from "@google/adk";
import { CompetitorProfilerAgent, MarketPositioningAgent } from "@/agents/competitive-analysis/analyzer";
import { generateAndDraftMarketingContent } from "@/agents/marketing-swarm/orchestrator";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { identity } = body;

        if (!identity || !identity.competitors || identity.competitors.length === 0) {
            return NextResponse.json({ error: "Missing competitors array. Please run discovery first." }, { status: 400 });
        }

        const sessionService = new InMemorySessionService();
        const runner = new Runner({ appName: 'competitive-analysis', agent: CompetitorProfilerAgent, sessionService });
        const sessionId = "comp-" + Date.now();

        await sessionService.createSession({ appName: 'competitive-analysis', sessionId, userId: 'sys', state: {} });

        console.log("[API/Competitive] Step 1: Profiling Competitors...");
        const profilerPrompt = `Research these competitors: ${JSON.stringify(identity.competitors)}`;
        const profilerStream = runner.runAsync({
            sessionId, userId: 'sys',
            newMessage: { role: 'user', parts: [{ text: profilerPrompt }] }
        });

        let competitorBrief = "";
        for await (const rawEvent of profilerStream) {
            const event = rawEvent as any;
            if (event.content?.parts) {
                for (const part of event.content.parts) {
                    if (part.text) competitorBrief += part.text;
                }
            }
        }

        console.log("[API/Competitive] Step 2: Running Market Strategy...");
        const positioningRunner = new Runner({ appName: 'competitive-analysis', agent: MarketPositioningAgent, sessionService });

        const strategyPrompt = `
        TARGET RESTAURANT: ${JSON.stringify(identity)}
        
        COMPETITORS BRIEF:
        ${competitorBrief}
        
        Generate the final competitive json report.
        `;

        const strategyStream = positioningRunner.runAsync({
            sessionId, userId: 'sys',
            newMessage: { role: 'user', parts: [{ text: strategyPrompt }] }
        });

        let strategyBuffer = "";
        for await (const rawEvent of strategyStream) {
            const event = rawEvent as any;
            if (event.content?.parts) {
                for (const part of event.content.parts) {
                    if (part.text) strategyBuffer += part.text;
                }
            }
        }

        const cleanJsonStr = strategyBuffer.replace(/```json/gi, '').replace(/```/g, '').trim();
        const payload = JSON.parse(cleanJsonStr);

        console.log("[API/Competitive] Success:", payload);

        // Fire and forget marketing generation
        generateAndDraftMarketingContent({ identity, competitive: payload }, 'Competitive Strategy').catch(console.error);

        return NextResponse.json(payload);
    } catch (e: any) {
        console.error("Competitive check failed", e);
        return NextResponse.json({ error: e.message || "Failed to analyze competitors." }, { status: 500 });
    }
}
