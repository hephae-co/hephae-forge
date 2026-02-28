import { AgentModels } from "../config";
import { FunctionTool, LlmAgent } from "@google/adk";
import { z } from "zod";
import { CompetitorPrice, MenuItem } from '@/lib/types';
import { callMarketTruthTool } from '../mcpClient';

// Mock Cache for Zip Codes (in-memory for this MVP)
const zipCodeCache = new Map<string, CompetitorPrice[]>();

const BenchmarkTool = new FunctionTool({
    name: 'fetch_competitor_benchmarks',
    description: 'Provide a location and an array of item names to fetch local competitor pricing and macroeconomic data.',
    parameters: z.object({
        location: z.string().describe("The city and state of the restaurant"),
        items: z.array(z.string())
    }),
    execute: async ({ location, items }) => {
        const competitors: CompetitorPrice[] = [];
        for (const itemName of items) {
            const variance = (Math.random() * 4) - 1; // -1 to +3 dollars difference
            const mockBasePrice = 12.00;
            competitors.push({
                competitor_name: "Competitor near " + location,
                item_match: itemName,
                price: parseFloat((mockBasePrice + variance).toFixed(2)),
                source_url: `https://google.com/maps/search/${encodeURIComponent(location)}+restaurant`,
                distance_miles: 1.2
            });
        }

        let macroeconomic_context = {};
        try {
            let region = "Northeast";
            const locLc = location.toLowerCase();
            if (locLc.match(/fl|tx|miami|austin|south|carolina|georgia|alabama/)) region = "South";
            else if (locLc.match(/il|chicago|midwest|ohio|michigan/)) region = "Midwest";
            else if (locLc.match(/ca|yountville|west|california|oregon|washington|nv/)) region = "West";

            const blsData = await callMarketTruthTool("get_bls_cpi_data", { region_code: region });
            const fredData = await callMarketTruthTool("get_fred_economic_indicators", { series_id: "UNRATE" }); // Pull Unemployment Rate

            macroeconomic_context = {
                inflation_cpi: blsData,
                unemployment_trend: fredData,
                analysis_hint: "Determine if local consumers can absorb a menu price increase."
            }
        } catch (e) {
            console.error("[Benchmarker] MCP Fetch Error", e);
        }

        return { competitors, macroeconomic_context };
    }
});

export const benchmarkerAgent = new LlmAgent({
    name: 'BenchmarkerAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `
    You are The Benchmarker. You will pull the 'parsedMenuItems' JSON array from the session state.
    Step 1: Extract all 'item_name' values from the parsedMenuItems.
    Step 2: Use the provided location context to call the 'fetch_competitor_benchmarks' tool with the geographic location and the item names.
    Step 3: Return the raw JSON object { competitors, macroeconomic_context } returned by the tool.
    
    CRITICAL: Output ONLY a strict JSON object matching the tool's return format. Do not add any text or conversational filler.
    `,
    tools: [BenchmarkTool],
    outputKey: 'competitorBenchmarks'
});
