import { NextRequest, NextResponse } from "next/server";
import { Runner, InMemorySessionService } from "@google/adk";
import { visionIntakeAgent } from '@/agents/margin-analyzer/visionIntake';
import { benchmarkerAgent } from '@/agents/margin-analyzer/benchmarker';
import { commodityWatchdogAgent } from '@/agents/margin-analyzer/commodityWatchdog';
import { surgeonAgent } from '@/agents/margin-analyzer/surgeon';
import { advisorAgent } from '@/agents/margin-analyzer/advisor';
import { MenuItem, MenuAnalysisItem, SurgicalReport } from "@/lib/types";
import { EnrichedProfile } from '@/agents/types';
import { generateAndDraftMarketingContent } from '@/agents/marketing-swarm/orchestrator';

export const maxDuration = 60; // 60 seconds (requires Vercel/Cloud Run config)

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const enrichedProfile: EnrichedProfile = body.identity;
        // In V1 API, we'll default advancedMode to false for speed unless explicitly requested
        const advancedMode = body.advancedMode || false;

        if (!enrichedProfile || !enrichedProfile.menuScreenshotBase64) {
            return NextResponse.json({ error: "Missing EnrichedProfile or menuScreenshotBase64. Ensure you run discovery first." }, { status: 400 });
        }

        console.log(`[V1/Analyze] 🚀 Triggering Margin Surgery Capability for ${enrichedProfile.name}...`);

        const finalIdentity = enrichedProfile as EnrichedProfile & { primaryColor: string, secondaryColor: string, persona: string };
        if (!finalIdentity.primaryColor) finalIdentity.primaryColor = "#0f172a";
        if (!finalIdentity.secondaryColor) finalIdentity.secondaryColor = "#334155";
        if (!finalIdentity.persona) finalIdentity.persona = "Local Business";

        const sessionService = new InMemorySessionService();
        const sessionId = "margin-v1-" + Date.now();
        const userId = "api-v1-client";

        await sessionService.createSession({ appName: 'hephae-hub', sessionId, userId, state: { advancedMode } });

        // 1. Vision Intake
        console.log("[V1/Analyze] Step 1: Vision Intake...");
        const visionRunner = new Runner({ appName: 'hephae-hub', agent: visionIntakeAgent, sessionService });
        let menuItemsPrompt = "";
        let menuItems: MenuItem[] = [];

        const vStream = visionRunner.runAsync({
            userId, sessionId,
            newMessage: { role: 'user', parts: [{ text: JSON.stringify(finalIdentity) }] }
        });
        for await (const rawEvent of vStream) {
            const event = rawEvent as any;
            if (event.content?.parts) {
                for (const part of event.content.parts) {
                    if (part.functionResponse && part.functionResponse.name === 'process_menu_items') {
                        menuItems = part.functionResponse.response;
                    }
                }
            }
            if (event.actions?.stateDelta?.menuItems && menuItems.length === 0) {
                menuItemsPrompt = typeof event.actions.stateDelta.menuItems === 'string'
                    ? event.actions.stateDelta.menuItems : JSON.stringify(event.actions.stateDelta.menuItems);
            }
        }
        if (menuItems.length === 0 && menuItemsPrompt) {
            menuItemsPrompt = menuItemsPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();
            try { menuItems = JSON.parse(menuItemsPrompt); } catch (e) {
                return NextResponse.json({ error: "Failed to parse menu items from vision agent." }, { status: 500 });
            }
        } else if (menuItems.length > 0) {
            menuItemsPrompt = JSON.stringify(menuItems);
        } else {
            return NextResponse.json({ error: "No menu items could be extracted." }, { status: 500 });
        }

        let benchmarkPrompt = "";
        let commodityPrompt = "";

        if (advancedMode) {
            // 2. Benchmarker
            console.log("[V1/Analyze] Step 2: Benchmarker (Advanced Mode)...");
            const benchmarkRunner = new Runner({ appName: 'hephae-hub', agent: benchmarkerAgent, sessionService });

            const bStream = benchmarkRunner.runAsync({
                userId, sessionId,
                newMessage: { role: 'user', parts: [{ text: `Here are the mapped menu items:\n${menuItemsPrompt}\n\nFor Target Identity:\n${JSON.stringify(finalIdentity)}` }] }
            });
            for await (const rawEvent of bStream) {
                const event = rawEvent as any;
                if (event.actions?.stateDelta?.benchmarkData) {
                    benchmarkPrompt = typeof event.actions.stateDelta.benchmarkData === 'string'
                        ? event.actions.stateDelta.benchmarkData : JSON.stringify(event.actions.stateDelta.benchmarkData);
                }
            }
            benchmarkPrompt = benchmarkPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();

            // 3. Commodity Watchdog
            console.log("[V1/Analyze] Step 3: Commodity Watchdog (Advanced Mode)...");
            const commodityRunner = new Runner({ appName: 'hephae-hub', agent: commodityWatchdogAgent, sessionService });

            const cStream = commodityRunner.runAsync({
                userId, sessionId,
                newMessage: { role: 'user', parts: [{ text: `Here are the parsed menu items:\n${menuItemsPrompt}` }] }
            });
            for await (const rawEvent of cStream) {
                const event = rawEvent as any;
                if (event.actions?.stateDelta?.commodityTrends) {
                    commodityPrompt = typeof event.actions.stateDelta.commodityTrends === 'string'
                        ? event.actions.stateDelta.commodityTrends : JSON.stringify(event.actions.stateDelta.commodityTrends);
                }
            }
            commodityPrompt = commodityPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();

        } else {
            console.log("[V1/Analyze] Fast Mode: Bypassing Benchmarker and Watchdog LLMs.");
            benchmarkPrompt = JSON.stringify({
                competitors: menuItems.map(item => ({
                    competitor_name: "Local Average (Estimate)",
                    item_match: item.item_name,
                    price: parseFloat(((item.current_price || 0) * 1.05).toFixed(2)),
                    source_url: "",
                    distance_miles: 1.0
                })),
                macroeconomic_context: { analysis_hint: "Standard estimation mode enabled. Assume moderate inflation." }
            });

            commodityPrompt = JSON.stringify([
                { ingredient: "GENERAL", inflation_rate_12mo: 3.2, trend_description: "Standard national food-at-home inflation estimate." }
            ]);
        }

        // 4. Surgeon
        console.log("[V1/Analyze] Step 4: The Surgeon...");
        const surgeonRunner = new Runner({ appName: 'hephae-hub', agent: surgeonAgent, sessionService });
        let surgeonPrompt = "";
        let menuAnalysis: MenuAnalysisItem[] = [];

        const sStream = surgeonRunner.runAsync({
            userId, sessionId,
            newMessage: { role: 'user', parts: [{ text: `Here are the arrays:\nMenuItems: ${menuItemsPrompt}\nBenchmarks: ${benchmarkPrompt}\nCommodities: ${commodityPrompt}` }] }
        });
        for await (const rawEvent of sStream) {
            const event = rawEvent as any;
            if (event.content?.parts) {
                for (const part of event.content.parts) {
                    if (part.functionResponse && part.functionResponse.name === 'perform_margin_surgery') {
                        menuAnalysis = part.functionResponse.response;
                    }
                }
            }
            if (event.actions?.stateDelta?.menuAnalysis && menuAnalysis.length === 0) {
                surgeonPrompt = typeof event.actions.stateDelta.menuAnalysis === 'string'
                    ? event.actions.stateDelta.menuAnalysis : JSON.stringify(event.actions.stateDelta.menuAnalysis);
            }
        }
        if (menuAnalysis.length === 0 && surgeonPrompt) {
            surgeonPrompt = surgeonPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();
            try {
                let parsed = JSON.parse(surgeonPrompt);
                if (Array.isArray(parsed)) {
                    menuAnalysis = parsed;
                } else if (parsed && typeof parsed === 'object') {
                    for (const key in parsed) {
                        if (Array.isArray(parsed[key])) {
                            menuAnalysis = parsed[key];
                            break;
                        }
                    }
                }
            } catch (e: any) {
                console.warn("Surgeon parse fail:", e.message);
                console.warn("Raw Surgeon Output:", surgeonPrompt);
            }
        }

        // 5. Advisor
        console.log("[V1/Analyze] Step 5: The Advisor...");
        const advisorRunner = new Runner({ appName: 'hephae-hub', agent: advisorAgent, sessionService });
        let strategicAdvice: string[] = [];

        const aStream = advisorRunner.runAsync({
            userId, sessionId,
            newMessage: { role: 'user', parts: [{ text: `Here is the menuAnalysis from the Surgeon:\n${surgeonPrompt}` }] }
        });
        for await (const rawEvent of aStream) {
            const event = rawEvent as any;
            if (event.actions?.stateDelta?.strategicAdvice) {
                const rawAdv = typeof event.actions.stateDelta.strategicAdvice === 'string'
                    ? event.actions.stateDelta.strategicAdvice : JSON.stringify(event.actions.stateDelta.strategicAdvice);
                try { strategicAdvice = JSON.parse(rawAdv.replace(/```json/gi, "").replace(/```/g, "").trim()); } catch (e) { }
            }
        }

        console.log("[V1/Analyze] ADK Margin Surgery Finished.");

        const totalLeakage = menuAnalysis.reduce((sum, item) => sum + item.price_leakage, 0);
        const totalRevenue = menuAnalysis.reduce((sum, item) => sum + item.current_price, 0);
        const score = Math.max(0, Math.min(100, Math.round(100 - (totalLeakage / (totalRevenue || 1) * 20))));

        const report: SurgicalReport = {
            identity: finalIdentity,
            menu_items: menuAnalysis,
            strategic_advice: strategicAdvice,
            overall_score: score,
            generated_at: new Date().toISOString()
        };

        // Fire and forget the marketing pipeline
        generateAndDraftMarketingContent({ identity: enrichedProfile, analyzer: report }, 'Margin Surgeon').catch(console.error);

        return NextResponse.json({ success: true, data: report });

    } catch (error) {
        console.error("V1 Orchestration Failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
