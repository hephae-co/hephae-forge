import { NextRequest, NextResponse } from "next/server";
import { LocatorAgent } from '@/agents/discovery/locator';
import { discoveryParallelAgent } from '@/agents/discovery/discoverySubAgents';
import { Runner, InMemorySessionService } from "@google/adk";
import { db } from "@/lib/firebase";

export const maxDuration = 60; // Max execution for Serverless Environs

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { query } = body;

        if (!query || typeof query !== 'string') {
            return NextResponse.json({ error: "Missing or invalid 'query' parameter." }, { status: 400 });
        }

        console.log(`[V1/Discover] 🚀 Starting Full Headless Discovery for: "${query}"`);

        // Phase 1: Locate Business
        console.log(`[V1/Discover] Step 1: Resolving Base Identity via LocatorAgent...`);
        let baseIdentity = null;
        try {
            baseIdentity = await LocatorAgent.resolve(query);
            console.log(`[V1/Discover]     -> Found: ${baseIdentity.name} at ${baseIdentity.address}`);
        } catch (e: any) {
            return NextResponse.json({ error: `Could not locate business matching query: ${query}` }, { status: 404 });
        }

        // Phase 2: Parallel Swarm (Menu, Maps, Social, Competitors)
        console.log(`[V1/Discover] Step 2: Running Discovery Orchestrator Swarm...`);
        const sessionService = new InMemorySessionService();
        const runner = new Runner({ appName: 'hephae-hub', agent: discoveryParallelAgent, sessionService });
        const sessionId = "discovery-v1-" + Date.now();
        const userId = "api-v1-client";

        await sessionService.createSession({ appName: 'hephae-hub', sessionId, userId, state: {} });

        let eventCount = 0;
        const stream = runner.runAsync({
            sessionId, userId,
            newMessage: { role: 'user', parts: [{ text: JSON.stringify(baseIdentity) }] }
        });

        // Drain generator to complete execution
        for await (const _ of stream) { eventCount++; }

        const finalSession = await sessionService.getSession({ appName: 'hephae-hub', sessionId, userId });
        const state = finalSession?.state || {};

        console.log(`[V1/Discover]     -> Parallel Swarm completed (${eventCount} ticks). Formatting Payload...`);

        const enrichedProfile = {
            ...baseIdentity,
            ...state
        };

        // Phase 3: Firebase Persistence
        try {
            console.log(`[V1/Discover] Step 3: Pushing Enriched Profile to Firestore 'discovered_businesses'...`);
            // We use a normalized document ID to prevent massive duplication if they search the same place twice.
            const docId = baseIdentity.name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase() + '_' + baseIdentity.address.replace(/[^a-zA-Z0-9]/g, '').substring(0, 10);

            const dbRef = db.collection('discovered_businesses').doc(docId);
            await dbRef.set({
                ...enrichedProfile,
                last_discovered_at: new Date()
            }, { merge: true });

            console.log(`[V1/Discover]     -> Successfully saved to Document ID: ${docId}`);
        } catch (dbErr: any) {
            console.error("[V1/Discover] ❌ Failed to write to Firestore DB, but returning payload anyway:", dbErr.message);
        }

        return NextResponse.json({ success: true, data: enrichedProfile });

    } catch (e: any) {
        console.error("[V1/Discover] ❌ Fatal API Error:", e);
        return NextResponse.json({ error: e.message || "Internal Server Error" }, { status: 500 });
    }
}
