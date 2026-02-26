import { FunctionTool, LlmAgent } from "@google/adk";
import { z } from "zod";
import { MenuItem, CompetitorPrice, CommodityTrend, MenuAnalysisItem } from "../types";

export class CalculationEngine {
    static calculateLeakage(
        item: MenuItem,
        competitors: CompetitorPrice[],
        commodities: CommodityTrend[]
    ): MenuAnalysisItem {

        // 1. Calculate Neighborhood Median
        const exactMatches = competitors.filter(c => c.item_match === item.item_name);
        const medianPrice = exactMatches.length > 0
            ? exactMatches.map(c => c.price).sort((a, b) => a - b)[Math.floor(exactMatches.length / 2)]
            : item.current_price; // Fallback if no competitor data

        // 2. Calculate Commodity Trend Impact
        let maxInflation = 0;
        for (const c of commodities) {
            if (item.item_name.toLowerCase().includes(c.ingredient.toLowerCase()) ||
                (c.ingredient === "Eggs" && item.category.toLowerCase().includes("breakfast"))) {
                if (c.inflation_rate_12mo > maxInflation) maxInflation = c.inflation_rate_12mo;
            }
        }

        // Inflation Factor: If inflation is 20%, factor is 1.20
        const commodityFactor = 1 + (maxInflation / 100);
        const inflationaryPrice = item.current_price * commodityFactor;

        // 3. Formula: Max(Price * Commodity_Trend, Neighborhood_Median)
        const targetBase = Math.max(inflationaryPrice, medianPrice);

        // We add a small "Surgical Margin" (e.g., 5%) for safety/profit
        const recommendedPrice = parseFloat((targetBase * 1.05).toFixed(2));

        const leakage = Math.max(0, recommendedPrice - item.current_price);

        const rationale = `Competitors average $${medianPrice}. Key ingredients inflated by ${maxInflation}%.`;

        return {
            ...item,
            competitor_benchmark: medianPrice,
            commodity_factor: maxInflation,
            recommended_price: recommendedPrice,
            price_leakage: parseFloat(leakage.toFixed(2)),
            confidence_score: exactMatches.length > 0 ? 90 : 50, // Higher confidence if competitors found
            rationale
        };
    }
}

const PerformSurgeryTool = new FunctionTool({
    name: 'perform_margin_surgery',
    description: 'Provide items, competitors, and commodities to calculate the absolute optimal price and identify revenue leakage for the restaurants menu.',
    parameters: z.object({
        items: z.array(z.any()), // MenuItem[]
        competitors: z.array(z.any()), // CompetitorPrice[]
        commodities: z.array(z.any()) // CommodityTrend[]
    }),
    execute: async ({ items, competitors, commodities }) => {
        return items.map(item => CalculationEngine.calculateLeakage(item, competitors, commodities));
    }
});

export const surgeonAgent = new LlmAgent({
    name: 'SurgeonAgent',
    model: 'gemini-2.5-flash',
    instruction: `
    You are The Surgeon. You will pull three JSON arrays from the session state: 'parsedMenuItems', 'competitorBenchmarks', and 'commodityTrends'.
    Step 1: Call the 'perform_margin_surgery' tool with these three arrays precisely.
    Step 2: Return the raw JSON array of MenuAnalysisItems returned by the tool.
    
    CRITICAL: Output ONLY a strict JSON array matching the tool's return format. Do not add any text, markdown blocks, or conversational filler.
    `,
    tools: [PerformSurgeryTool],
    outputKey: 'menuAnalysis'
});
