import { AgentModels } from "../config";
import { BaseIdentity, EnrichedProfile } from '@/agents/types';
import { chromium } from 'playwright';
import { FunctionTool, LlmAgent, ParallelAgent } from '@google/adk';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { z } from 'zod';

// --- TOOLS ---

const googleSearchParams = z.object({
    query: z.string().describe("The search query to execute")
});

// Since we are running the discovery agents concurrently using ADK's ParallelAgent,
// we define a deterministic scrape Menu tool that will be triggered by the Menu Agent.
const ScrapeMenuTool = new FunctionTool({
    name: 'scrape_menu',
    description: 'Use this tool to navigate to a restaurant website and extract a full-page screenshot of its menu in base64 format.',
    parameters: z.object({
        officialUrl: z.string().describe("The official URL of the restaurant")
    }),
    execute: async ({ officialUrl }) => {
        let browser;
        try {
            console.log(`[ScrapeMenuTool] Crawling ${officialUrl}...`);
            browser = await chromium.launch();
            const context = await browser.newContext({ ignoreHTTPSErrors: true });
            const page = await context.newPage();

            await page.goto(officialUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

            console.log("[ScrapeMenuTool] Looking for menu link...");
            const menuHref = await page.evaluate<string | null>(`(() => {
                const anchors = Array.from(document.querySelectorAll('a'));
                const menuLink = anchors.find(a =>
                    (a.innerText && a.innerText.toLowerCase().includes('menu')) ||
                    (a.href && a.href.toLowerCase().includes('menu'))
                );
                return menuLink ? menuLink.href : null;
            })()`);

            if (menuHref) {
                console.log("[ScrapeMenuTool] Found menu link:", menuHref);
                let finalMenuUrl = menuHref;
                if (menuHref.startsWith('/')) {
                    const baseUrl = new URL(officialUrl);
                    finalMenuUrl = `${baseUrl.origin}${menuHref}`;
                }
                await page.goto(finalMenuUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
            } else {
                console.log("[ScrapeMenuTool] No menu link found, assuming homepage is the menu.");
            }

            await page.waitForTimeout(2000); // Allow dynamic rendering
            const buffer = await page.screenshot({ fullPage: true, type: 'jpeg', quality: 60 });
            console.log("[ScrapeMenuTool] Menu screenshot captured.");
            return { screenshotBase64: buffer.toString('base64') };

        } catch (error: any) {
            console.error("[ScrapeMenuTool] Failed:", error.message);
            return { error: error.message };
        } finally {
            if (browser) await browser.close();
        }
    }
});

// Since the ADK TS package doesn't natively expose the Python Google Search tool,
// we build a deterministic internal query tool that uses pure Gemini Grounding.
const GoogleSearchTool = new FunctionTool({
    name: 'googleSearch',
    description: 'Search Google for a query to find factual information, URLs, or real-world entities.',
    parameters: googleSearchParams,
    execute: async ({ query }) => {
        try {
            console.log(`[GoogleSearchTool] Executing grounded query: ${query}`);
            const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
            const model = genAI.getGenerativeModel({
                model: AgentModels.DEFAULT_FAST_MODEL,
                tools: [{
                    // @ts-ignore
                    googleSearch: {}
                }]
            });
            const result = await model.generateContent(`Execute this search and summarize the top facts and URLs precisely related to: ${query}`);
            return { result: result.response.text() };
        } catch (e: any) {
            console.error("[GoogleSearchTool] Failed:", e);
            return { error: "Search failed." };
        }
    }
});

// --- SUB-AGENTS ---

export const menuDiscoveryAgent = new LlmAgent({
    name: 'MenuDiscoveryAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `You are an AI Web Scraper. You will be given a business URL. You MUST call the 'scrape_menu' tool with the exact URL provided.
    
    CRITICAL: When the tool returns the base64 screenshot, YOU MUST OUTPUT ONLY THE RAW BASE64 STRING.
    DO NOT PREFACE YOUR ANSWER. DO NOT SAY "Here is the base64". JUST OUTPUT THE BASE64 AND NOTHING ELSE.`,
    tools: [ScrapeMenuTool],
    outputKey: 'menuScreenshotBase64'
});

export const socialDiscoveryAgent = new LlmAgent({
    name: 'SocialDiscoveryAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `
    Find the exact, official social media profile URLs for the business provided.
    You must use Google Search to verify these links.
    
    Return ONLY a valid JSON object with the following keys. If a profile is not found, omit the key or return null.
    CRITICAL: Do not write any markdown blocks or conversational text. ONLY raw JSON!
    {
        "instagram": "https://instagram.com/...",
        "facebook": "https://facebook.com/...",
        "twitter": "https://twitter.com/..."
    }
    `,
    tools: [GoogleSearchTool], // Allows grounding
    outputKey: 'socialLinks'
});

export const mapsDiscoveryAgent = new LlmAgent({
    name: 'MapsDiscoveryAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `
    Find the exact, official Google Maps Place URL for the business provided.
    You must use Google Search.
    
    CRITICAL: Return ONLY the raw URL string. If not found, return an empty string. DO NOT explain yourself. DO NOT say "Here is the URL". JUST THE URL.
    `,
    tools: [GoogleSearchTool], // Allows grounding
    outputKey: 'googleMapsUrl'
});

export const competitorDiscoveryAgent = new LlmAgent({
    name: 'CompetitorDiscoveryAgent',
    model: AgentModels.DEEP_ANALYST_MODEL,
    instruction: `
    Find exactly 3 direct local competitors for the business provided. 
    They should be in the same geographic area serving similar cuisine or services.
    You must use Google Search to verify their existence and retrieve their data.
    
    SYSTEM COMMAND: YOU MUST RETURN ONLY A RAW JSON ARRAY. DO NOT WRITE ANY TEXT OUTSIDE THE ARRAY.
    Example output format:
    [
        {
            "name": "Competitor Name",
            "url": "https://competitor.com",
            "reason": "Why they are a competitor"
        }
    ]
    `,
    outputKey: 'competitors'
});

// --- ORCHESTRATOR ---

export const discoveryParallelAgent = new ParallelAgent({
    name: 'DiscoveryOrchestrator',
    description: 'Runs multiple specialized discovery agents concurrently.',
    subAgents: [menuDiscoveryAgent, socialDiscoveryAgent, mapsDiscoveryAgent, competitorDiscoveryAgent]
});
