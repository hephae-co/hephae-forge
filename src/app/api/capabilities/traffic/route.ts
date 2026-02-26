import { NextRequest, NextResponse } from "next/server";
import { ForecasterAgent } from "@/lib/agents/core/forecaster";

export const maxDuration = 60; // 60 seconds (requires Vercel/Cloud Run config but good practice)

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { identity } = body;

        if (!identity || !identity.name) {
            return NextResponse.json({ error: "Missing Target Identity for Traffic Forecaster" }, { status: 400 });
        }

        const forecastData = await ForecasterAgent.forecast(identity);

        return NextResponse.json(forecastData);

    } catch (error: any) {
        console.error("[API/Capabilities/Traffic] Failed:", error);
        return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
    }
}
