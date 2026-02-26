import { FunctionTool, LlmAgent } from "@google/adk";
import { z } from "zod";
import { CommodityTrend } from "../types";

const CheckCommoditiesTool = new FunctionTool({
    name: 'check_commodity_inflation',
    description: 'Provide an array of menu categories to check the latest commodity inflation trends.',
    parameters: z.object({
        categories: z.array(z.string())
    }),
    execute: async ({ categories }) => {
        const db: Record<string, CommodityTrend> = {
            "Eggs": { ingredient: "Eggs", inflation_rate_12mo: 45.0, trend_description: "Skyrocketing due to avian flu aftermath" },
            "Dairy": { ingredient: "Dairy", inflation_rate_12mo: 8.5, trend_description: "Steady increase in feed costs" },
            "Meat": { ingredient: "Beef/Pork", inflation_rate_12mo: 12.0, trend_description: "Supply chain constraints" },
            "Coffee": { ingredient: "Coffee", inflation_rate_12mo: 18.0, trend_description: "Climate impact on Brazil harvest" },
            "Grains": { ingredient: "Flour/Bread", inflation_rate_12mo: 5.0, trend_description: "Stabilizing" }
        };

        const trends: CommodityTrend[] = [];

        if (categories.some(c => c.toLowerCase().includes("breakfast"))) {
            trends.push(db["Eggs"], db["Coffee"], db["Dairy"]);
        }
        if (categories.some(c => c.toLowerCase().includes("burger") || c.toLowerCase().includes("steak"))) {
            trends.push(db["Meat"]);
        }

        return Array.from(new Set(trends));
    }
});

export const commodityWatchdogAgent = new LlmAgent({
    name: 'CommodityWatchdogAgent',
    model: 'gemini-2.5-flash',
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
