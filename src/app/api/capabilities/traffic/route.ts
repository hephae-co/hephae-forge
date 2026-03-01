import { NextRequest, NextResponse } from "next/server";
import { ForecasterAgent } from '@/agents/traffic-forecaster/forecaster';
import { generateAndDraftMarketingContent } from "@/agents/marketing-swarm/orchestrator";
import { generateSlug, uploadReport } from '@/lib/reportStorage';
import { buildTrafficReport } from '@/lib/reportTemplates';
import { writeAgentResult } from '@/lib/db';
import { AgentVersions } from '@/agents/config';

export const maxDuration = 60; // 60 seconds (requires Vercel/Cloud Run config but good practice)

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { identity } = body;

        if (!identity || !identity.name) {
            return NextResponse.json({ error: "Missing Target Identity for Traffic Forecaster" }, { status: 400 });
        }

        const forecastData = await ForecasterAgent.forecast(identity);

        // Fire and forget marketing generation
        generateAndDraftMarketingContent({ identity, forecast: forecastData }, 'Foot Traffic Heatmap').catch(console.error);

        const slug = generateSlug(identity.name);

        const reportUrl = await uploadReport({
            slug,
            type: 'traffic',
            htmlContent: buildTrafficReport(forecastData),
            identity,
            summary: forecastData.summary,
        });

        writeAgentResult({
            businessSlug: slug,
            businessName: identity.name,
            agentName: 'traffic_forecaster',
            agentVersion: AgentVersions.TRAFFIC_FORECASTER,
            triggeredBy: 'user',
            summary: forecastData.summary,
            reportUrl: reportUrl || undefined,
            rawData: forecastData,
        }).catch(err => console.error('[API/Traffic] writeAgentResult failed:', err));

        return NextResponse.json({ ...forecastData, reportUrl: reportUrl || undefined });

    } catch (error: any) {
        console.error("[API/Capabilities/Traffic] Failed:", error);
        return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
    }
}
