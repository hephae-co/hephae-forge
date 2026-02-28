import { NextRequest, NextResponse } from "next/server";
import { Runner, InMemorySessionService } from "@google/adk";
import { db } from "@/lib/firebase";

export const maxDuration = 300; // Let this run for a long time as it triggers the whole system

export async function GET(req: NextRequest) {
    console.log("🚀 Initializing External Developer V1 API E2E Test Suite...\n");
    let logOutput = "";

    const testQuery = "Versailles Restaurant Cuban Cuisine Miami";
    let enrichedProfilePayload: any = null;

    try {
        logOutput += `\n1. Testing POST /api/v1/discover with query: "${testQuery}"\n`;
        const protocol = req.headers.get("x-forwarded-proto") || "http";
        const host = req.headers.get("host");
        const baseUrl = `${protocol}://${host}`;

        logOutput += `   -> Triggering Unified Swarm Fetch...\n`;
        const discoverRes = await fetch(`${baseUrl}/api/v1/discover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: testQuery })
        });

        const discoverData = await discoverRes.json();

        if (discoverRes.ok && discoverData.success) {
            enrichedProfilePayload = discoverData.data;
            logOutput += `   ✅ Successfully resolved Enriched Profile for: ${enrichedProfilePayload.name}\n`;
            logOutput += `   -> Address: ${enrichedProfilePayload.address}\n`;
            logOutput += `   -> Website: ${enrichedProfilePayload.officialUrl}\n`;
            logOutput += `   -> Found ${enrichedProfilePayload.competitors?.length || 0} Competitors.\n`;
        } else {
            throw new Error(`Discover API Failed: ${JSON.stringify(discoverData)}`);
        }

        logOutput += `\n2. Verifying Firestore Persistence...\n`;
        const docId = enrichedProfilePayload.name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase() + '_' + enrichedProfilePayload.address.replace(/[^a-zA-Z0-9]/g, '').substring(0, 10);
        const dbRef = db.collection('discovered_businesses').doc(docId);
        const docSnap = await dbRef.get();
        if (docSnap.exists) {
            logOutput += `   ✅ Successfully verified Document ${docId} exists in 'discovered_businesses' collection.\n`;
        } else {
            logOutput += `   ❌ FAILED: Document ${docId} was not written to Firestore.\n`;
        }

        logOutput += `\n3. Testing Traffic Capability (POST /api/v1/traffic)...\n`;
        const trafficRes = await fetch(`${baseUrl}/api/v1/traffic`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identity: enrichedProfilePayload })
        });
        const trafficData = await trafficRes.json();
        if (trafficRes.ok && trafficData.success && trafficData.data.forecast_data) {
            logOutput += `   ✅ Successfully generated Foot Traffic Forecast.\n`;
        } else {
            logOutput += `   ❌ FAILED Traffic: ${JSON.stringify(trafficData)}\n`;
        }

        logOutput += `\n4. Testing Margin Surgery Capability (POST /api/v1/analyze)...\n`;
        // Pass advancedMode false to speed up the test
        const analyzeRes = await fetch(`${baseUrl}/api/v1/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identity: enrichedProfilePayload, advancedMode: false })
        });
        const analyzeData = await analyzeRes.json();
        if (analyzeRes.ok && analyzeData.success && analyzeData.data.menu_items) {
            logOutput += `   ✅ Successfully generated Surgical Margin Report (Score: ${analyzeData.data.overall_score}).\n`;
        } else {
            logOutput += `   ❌ FAILED Analyze: ${JSON.stringify(analyzeData)}\n`;
        }

        logOutput += `\n5. Testing SEO Capability (POST /api/v1/seo)...\n`;
        const seoRes = await fetch(`${baseUrl}/api/v1/seo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identity: enrichedProfilePayload })
        });
        const seoData = await seoRes.json();
        if (seoRes.ok && seoData.success && seoData.data.sections) {
            logOutput += `   ✅ Successfully generated SEO Audit (Score: ${seoData.data.overall_score}).\n`;
        } else {
            logOutput += `   ❌ FAILED SEO: ${JSON.stringify(seoData)}\n`;
        }

        logOutput += `\n6. Testing Competitive Capability (POST /api/v1/competitive)...\n`;
        const compRes = await fetch(`${baseUrl}/api/v1/competitive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ identity: enrichedProfilePayload })
        });
        const compData = await compRes.json();
        if (compRes.ok && compData.success && compData.data.rival_positioning) {
            logOutput += `   ✅ Successfully generated Competitive Strategy Dashboard.\n`;
        } else {
            logOutput += `   ❌ FAILED Competitive: ${JSON.stringify(compData)}\n`;
        }

        logOutput += `\n🎉 EXTERNAL V1 API E2E SUITE PASSED SUCCESSFULLY 🎉\n`;

        return NextResponse.json({ success: true, logOutput });

    } catch (e: any) {
        console.error("Test Suite Failed:", e);
        logOutput += `\n❌ FATAL ERROR IN TEST SUITE: ${e.message}\n`;
        return NextResponse.json({ success: false, logOutput, error: e.message }, { status: 500 });
    }
}
