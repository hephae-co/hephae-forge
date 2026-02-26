import { FunctionTool, LlmAgent } from "@google/adk";
import { z } from "zod";
import { CompetitorPrice, MenuItem } from "../types";

// Mock Cache for Zip Codes (in-memory for this MVP)
const zipCodeCache = new Map<string, CompetitorPrice[]>();

const BenchmarkTool = new FunctionTool({
    name: 'fetch_competitor_benchmarks',
    description: 'Provide a zipCode and an array of item names to fetch local competitor pricing.',
    parameters: z.object({
        zipCode: z.string(),
        items: z.array(z.string())
    }),
    execute: async ({ zipCode, items }) => {
        const competitors: CompetitorPrice[] = [];
        for (const itemName of items) {
            const variance = (Math.random() * 4) - 1; // -1 to +3 dollars difference
            // We just mock the current price since the LLM will match it back up
            const mockBasePrice = 12.00;
            competitors.push({
                competitor_name: "Competitor In Zip " + zipCode,
                item_match: itemName,
                price: parseFloat((mockBasePrice + variance).toFixed(2)),
                source_url: `https://google.com/maps/search/${zipCode}+diner`,
                distance_miles: 1.2
            });
        }
        return competitors;
    }
});

export const benchmarkerAgent = new LlmAgent({
    name: 'BenchmarkerAgent',
    model: 'gemini-2.5-flash',
    instruction: `
    You are The Benchmarker. You will pull the 'parsedMenuItems' JSON array from the session state.
    Step 1: Extract all 'item_name' values from the parsedMenuItems.
    Step 2: Call the 'fetch_competitor_benchmarks' tool with a default zip code "07302" and the item names.
    Step 3: Return the raw JSON array of CompetitorPrice objects returned by the tool.
    
    CRITICAL: Output ONLY a strict JSON array matching the tool's return format. Do not add any text or conversational filler.
    `,
    tools: [BenchmarkTool],
    outputKey: 'competitorBenchmarks'
});
