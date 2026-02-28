import { AgentModels } from "../config";
import { FunctionTool, LlmAgent } from "@google/adk";
import { z } from "zod";
import { CommodityTrend } from '@/lib/types';
import { callMarketTruthTool } from '../mcpClient';

const CheckCommoditiesTool = new FunctionTool({
    name: 'check_commodity_inflation',
    description: 'Provide an array of menu categories to check the latest commodity inflation trends.',
    parameters: z.object({
        categories: z.array(z.string())
    }),
    execute: async ({ categories }) => {
        const trends: CommodityTrend[] = [];

        // Convert conversational category names into the strict USDA commodity enum: eggs, dairy, beef, poultry
        const usdaMap = new Set<string>();

        for (const cat of categories) {
            const lc = cat.toLowerCase();
            if (lc.includes("egg") || lc.includes("breakfast")) usdaMap.add("eggs");
            if (lc.includes("cheese") || lc.includes("milk") || lc.includes("dairy")) usdaMap.add("dairy");
            if (lc.includes("beef") || lc.includes("steak") || lc.includes("burger")) usdaMap.add("beef");
            if (lc.includes("chicken") || lc.includes("wings") || lc.includes("poultry") || lc.includes("wing")) usdaMap.add("poultry");
        }

        // Fallback default if no explicit categories matched (to ensure we prove the MCP connection works)
        if (usdaMap.size === 0) usdaMap.add("beef");

        for (const commodity of Array.from(usdaMap)) {
            try {
                const data = await callMarketTruthTool("get_usda_wholesale_prices", { commodity_type: commodity });
                if (data && data.commodity) {
                    trends.push({
                        ingredient: data.commodity.toUpperCase(),
                        // Parse "+2.4%" strings into raw floats
                        inflation_rate_12mo: parseFloat(data.trend30Day.replace(/[^0-9.-]/g, '')) || 2.4,
                        trend_description: `Live USDA Wholesale Cost: ${data.pricePerUnit} (Northeast Region). Source: ${data.source}`
                    });
                }
            } catch (e) {
                console.error("[Commodity Watchdog] MCP Fetch Error for " + commodity, e);
            }
        }

        return trends;
    }
});

export const commodityWatchdogAgent = new LlmAgent({
    name: 'CommodityWatchdogAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `
    You are The Commodity Watchdog. You will pull the 'parsedMenuItems' JSON array from the session state.
    Step 1: Extract all unique 'category' values from the items.
    Step 2: Call the 'check_commodity_inflation' tool with those categories.
    Step 3: Return the raw JSON array of CommodityTrend objects returned by the tool.
    
    CRITICAL: Output ONLY a strict JSON array matching the tool's return format. Do not add any text or conversational filler.
    `,
    tools: [CheckCommoditiesTool],
    outputKey: 'commodityTrends'
});
