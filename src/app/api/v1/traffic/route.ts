import { NextRequest, NextResponse } from "next/server";
import { ForecasterAgent } from '@/agents/traffic-forecaster/forecaster';
import { generateAndDraftMarketingContent } from "@/agents/marketing-swarm/orchestrator";

export const maxDuration = 60;

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const enrichedProfile = body.identity;

        if (!enrichedProfile || !enrichedProfile.name) {
            return NextResponse.json({ error: "Missing Target EnrichedProfile (identity) for Traffic Forecaster" }, { status: 400 });
        }

        console.log(`[V1/Traffic] 🚀 Triggering Foot Traffic Capability for ${enrichedProfile.name}...`);
        const forecastData = await ForecasterAgent.forecast(enrichedProfile);

        // Fire and forget marketing generation
        generateAndDraftMarketingContent({ identity: enrichedProfile, forecast: forecastData }, 'Foot Traffic Heatmap').catch(console.error);

        return NextResponse.json({ success: true, data: forecastData });

    } catch (error: any) {
        console.error("[V1/Traffic] Failed:", error);
        return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
    }
}
