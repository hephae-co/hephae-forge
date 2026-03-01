import { NextRequest, NextResponse } from "next/server";
import { Runner, InMemorySessionService } from "@google/adk";
import { visionIntakeAgent } from '@/agents/margin-analyzer/visionIntake';
import { benchmarkerAgent } from '@/agents/margin-analyzer/benchmarker';
import { commodityWatchdogAgent } from '@/agents/margin-analyzer/commodityWatchdog';
import { surgeonAgent } from '@/agents/margin-analyzer/surgeon';
import { advisorAgent } from '@/agents/margin-analyzer/advisor';
import { MenuItem, MenuAnalysisItem, SurgicalReport } from "@/lib/types";
import { EnrichedProfile } from '@/agents/types';
import { LocatorAgent } from '@/agents/discovery/locator';
import { ProfilerAgent } from '@/agents/business-profiler/profiler';
import { generateAndDraftMarketingContent } from '@/agents/marketing-swarm/orchestrator';
import { generateSlug, uploadReport } from '@/lib/reportStorage';
import { buildMarginReport } from '@/lib/reportTemplates';
import { writeAgentResult } from '@/lib/db';
import { AgentVersions } from '@/agents/config';

export const maxDuration = 60;

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { url, enrichedProfile, advancedMode } = body;

        let identity: EnrichedProfile;

        // FAST PATH: We already ran the Parallel Discovery Subagents
        if (enrichedProfile && enrichedProfile.menuScreenshotBase64) {
            console.log(`[API/Analyze] Fast Path: Bypassing Profiler for ${enrichedProfile.name}`);
            identity = enrichedProfile;

            // Ensure colors/persona are populated for the Surgeon UI if the Parallel agent didn't fetch them
            if (!identity.primaryColor) identity.primaryColor = "#0f172a";
            if (!identity.secondaryColor) identity.secondaryColor = "#334155";
            if (!identity.persona) identity.persona = "Local Business";

        } else {
            // SLOW PATH: Legacy sequential flow
            console.log(`[API/Analyze] Slow Path: Analyzing identity and crawling menu for: ${url}`);
            const baseIdentity = await LocatorAgent.resolve(url);
            identity = await ProfilerAgent.profile(baseIdentity);
        }

        const finalIdentity = identity as EnrichedProfile & { primaryColor: string, secondaryColor: string, persona: string };

        if (!finalIdentity.menuScreenshotBase64) {
            return NextResponse.json({ error: "Failed to crawl menu from website. Please ensure the site has a visible 'Menu' link." }, { status: 422 });
        }

        console.log(`[API/Analyze] Commencing explicit margin surgery via ADK Agents...`);
        const sessionService = new InMemorySessionService();
        const sessionId = "surgery-" + Date.now();
        const userId = "hub-user";

        await sessionService.createSession({ appName: 'hephae-hub', userId, sessionId, state: {} });

        // 1. Vision Intake
        console.log("[API/Analyze] Step 1: Vision Intake...");
        const visionRunner = new Runner({ appName: 'hephae-hub', agent: visionIntakeAgent, sessionService });
        let menuItemsPrompt = "";
        let menuItems: MenuItem[] = [];

        const visionStream = visionRunner.runAsync({
            userId, sessionId,
            newMessage: {
                role: 'user', parts: [
                    { text: "Extract all menu items from this image." },
                    { inlineData: { data: finalIdentity.menuScreenshotBase64.replace(/^data:image\/\w+;base64,/, ""), mimeType: "image/jpeg" } }
                ]
            }
        });

        for await (const rawEvent of visionStream) {
            const event = rawEvent as any;
            if (event.actions?.stateDelta?.parsedMenuItems) {
                menuItemsPrompt = typeof event.actions.stateDelta.parsedMenuItems === 'string'
                    ? event.actions.stateDelta.parsedMenuItems
                    : JSON.stringify(event.actions.stateDelta.parsedMenuItems);
            }
        }

        try {
            console.log("[API/Analyze] Raw Vision Output:", menuItemsPrompt);
            menuItemsPrompt = menuItemsPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();
            menuItems = JSON.parse(menuItemsPrompt);
        } catch (e) { console.warn("Vision parse failed"); }
        if (menuItems.length === 0) return NextResponse.json({ error: "Failed to parse menu items from crawled screenshot.", rawOutput: menuItemsPrompt }, { status: 422 });

        let benchmarkPrompt = "[]";
        let commodityPrompt = "[]";

        if (advancedMode) {
            // 2. Benchmarker
            console.log("[API/Analyze] Step 2: Benchmarker (Advanced Mode)...");
            const benchmarkRunner = new Runner({ appName: 'hephae-hub', agent: benchmarkerAgent, sessionService });

            const bStream = benchmarkRunner.runAsync({
                userId, sessionId,
                newMessage: { role: 'user', parts: [{ text: `Here are the parsed menu items for ${finalIdentity.name} in ${finalIdentity.address || "their local area"}:\n${menuItemsPrompt}` }] }
            });
            for await (const rawEvent of bStream) {
                const event = rawEvent as any;
                if (event.actions?.stateDelta?.competitorBenchmarks) {
                    benchmarkPrompt = typeof event.actions.stateDelta.competitorBenchmarks === 'string'
                        ? event.actions.stateDelta.competitorBenchmarks : JSON.stringify(event.actions.stateDelta.competitorBenchmarks);
                }
            }
            benchmarkPrompt = benchmarkPrompt.replace(/```json/gi, "").replace(/```/g, "").trim();

            // 3. Commodity Watchdog
            console.log("[API/Analyze] Step 3: Commodity Watchdog (Advanced Mode)...");
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
            console.log("[API/Analyze] Fast Mode: Bypassing Benchmarker and Watchdog LLMs.");
            // Provide lightweight dummy fallback data to keep the Surgeon Agent grounded
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
        console.log("[API/Analyze] Step 4: The Surgeon...");
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
        console.log("[API/Analyze] Step 5: The Advisor...");
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

        console.log("[API/Analyze] ADK Margin Surgery Finished.");

        // Score Calculation based on parsed adk payload
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
        generateAndDraftMarketingContent(report, 'Margin Surgery').catch(console.error);

        const slug = generateSlug(finalIdentity.name);

        // Upload HTML report to GCS
        const reportUrl = await uploadReport({
            slug,
            type: 'margin',
            htmlContent: buildMarginReport(report),
            identity: finalIdentity,
            summary: `$${totalLeakage.toLocaleString()} profit leakage detected. Score: ${score}/100`,
        });

        // Strip binary blobs before writing to DB
        const { menuScreenshotBase64: _stripped, ...safeIdentity } = finalIdentity;
        const safeReport = { ...report, identity: safeIdentity };

        writeAgentResult({
            businessSlug: slug,
            businessName: finalIdentity.name,
            agentName: 'margin_surgeon',
            agentVersion: AgentVersions.MARGIN_SURGEON,
            triggeredBy: 'user',
            score,
            summary: `$${totalLeakage.toLocaleString()} profit leakage. Score: ${score}/100`,
            reportUrl: reportUrl || undefined,
            kpis: { totalLeakage },
            rawData: safeReport,
        }).catch(err => console.error('[API/Analyze] writeAgentResult failed:', err));

        return NextResponse.json({ ...report, reportUrl: reportUrl || undefined });

    } catch (error) {
        console.error("Orchestration Failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
