import { NextRequest, NextResponse } from "next/server";
import { competitorDiscoveryAgent } from "@/agents/discovery/discoverySubAgents";
import { CompetitorProfilerAgent, MarketPositioningAgent } from "@/agents/competitive-analysis/analyzer";
import { Runner, InMemorySessionService, LlmAgent } from "@google/adk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { AgentModels } from "@/agents/config";

async function runAdkAgent(agent: any, input: string) {
    const sessionService = new InMemorySessionService();
    const runner = new Runner({ appName: 'hephae-comp-test', agent, sessionService });
    const sessionId = "test-" + Date.now() + Math.random();

    await sessionService.createSession({ appName: 'hephae-comp-test', sessionId, userId: 'sys', state: {} });

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

export async function GET(req: NextRequest) {
    console.log("🚀 Initializing Competitive Analysis Swarm E2E Test...\n");
    let logOutput = "";

    try {
        const mockTarget = {
            name: "The Bosphorus Mediterranean Cuisine",
            address: "223 Franklin Ave, Nutley, NJ 07110",
            officialUrl: "https://thebosphorusnj.com"
        };

        logOutput += "1. Executing CompetitorDiscoveryAgent...\n";
        const discoveryInput = `Target: ${mockTarget.name}, Address: ${mockTarget.address}`;
        const discoveryRaw = await runAdkAgent(competitorDiscoveryAgent, discoveryInput);

        let foundCompetitors = [];
        try {
            foundCompetitors = JSON.parse(discoveryRaw.replace(/```json|```/gi, '').trim());
            logOutput += `   -> Found exactly ${foundCompetitors.length} competitors.\n`;
        } catch (e: any) {
            const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
            const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash", generationConfig: { responseMimeType: "application/json" } });
            const res = await model.generateContent(`Extract exactly 3 restaurant competitors from the following text into a JSON array of objects with strictly these keys: "name", "url", "reason". TEXT: ${discoveryRaw}`);
            foundCompetitors = JSON.parse(res.response.text());
            logOutput += `   -> (Forced Extraction) Found ${foundCompetitors.length} competitors.\n`;
        }

        if (foundCompetitors.length !== 3) {
            throw new Error(`Expected exactly 3 competitors, got ${foundCompetitors.length}`);
        }

        logOutput += "\n2. Executing CompetitorProfilerAgent (Deep Search)...\n";
        const profilerRaw = await runAdkAgent(CompetitorProfilerAgent, JSON.stringify(foundCompetitors));
        logOutput += `   -> Gathered Research Intel (${profilerRaw.length} chars).\n`;

        logOutput += "\n3. Executing MarketPositioningAgent (Strategic AI)...\n";
        const strategyRaw = await runAdkAgent(MarketPositioningAgent, JSON.stringify({
            target: mockTarget,
            intel: profilerRaw
        }));

        let jsonReport: any = null;
        try {
            jsonReport = JSON.parse(strategyRaw.replace(/```json|```/gi, '').trim());
            logOutput += `   -> Successfully generated Dashboard JSON Report.\n`;
        } catch (e: any) {
            throw new Error("MarketPositioningAgent output was not valid JSON. Output: " + strategyRaw);
        }

        // Test with LLM as an evaluator
        logOutput += "\n4. Validating Output using LLM-as-a-Judge...\n";
        const JudgeAgent = new LlmAgent({
            name: 'Judge',
            model: AgentModels.DEFAULT_FAST_MODEL,
            instruction: `You are an E2E Test Judge. Look at the provided Market Positioning Report.
             Verify that it contains:
             1. A 'market_summary' string
             2. A 'competitor_analysis' array with exactly 3 objects.
             3. Those objects must have 'name', 'key_strength', 'key_weakness', and 'threat_level' (integer 1-10).
             4. A 'strategic_advantages' array.
             
             Return ONLY valid JSON: {"passed": boolean, "reason": "why"}`
        });

        const judgeRaw = await runAdkAgent(JudgeAgent, JSON.stringify(jsonReport));
        const judgeResult = JSON.parse(judgeRaw.replace(/```json|```/gi, '').trim());

        logOutput += `   -> Judge Decision: ${judgeResult.passed ? 'PASSED ✅' : 'FAILED ❌'} (${judgeResult.reason})\n`;

        if (!judgeResult.passed) {
            throw new Error(`Judge rejected report: ${judgeResult.reason}`);
        }

        logOutput += "\n✅ Competitive Swarm E2E Complete.\n";
        return NextResponse.json({ success: true, logOutput, jsonReport });

    } catch (error: any) {
        logOutput += `\n❌ TEST SUITE FAILED: ${error.message}\n`;
        console.error(error);
        return NextResponse.json({ success: false, logOutput, error: error.message }, { status: 500 });
    }
}
