import { NextRequest, NextResponse } from "next/server";
import { discoveryParallelAgent } from '@/agents/discovery/discoverySubAgents';
import { BaseIdentity, EnrichedProfile } from '@/agents/types';
import { Runner, InMemorySessionService } from "@google/adk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { generateSlug, uploadReport, uploadMenuScreenshot } from '@/lib/reportStorage';
import { buildProfileReport } from '@/lib/reportTemplates';
import { writeDiscovery } from '@/lib/db';
import { AgentVersions } from '@/agents/config';

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const identity: BaseIdentity = body.identity;

        if (!identity || !identity.officialUrl) {
            return NextResponse.json({ error: "Missing BaseIdentity" }, { status: 400 });
        }

        console.log(`[API/Discover] Spawning ADK Orchestrator for: ${identity.name}`);
        const sessionService = new InMemorySessionService();
        const runner = new Runner({
            appName: 'hephae-hub',
            agent: discoveryParallelAgent,
            sessionService
        });

        const sessionId = "discovery-" + Date.now();
        const userId = "hub-user";

        await sessionService.createSession({
            appName: 'hephae-hub',
            userId,
            sessionId,
            state: {}
        });

        const prompt = `
            Please discover the menu, social links, Google Maps URL, brand theme assets, and exactly 3 local competitors for:
            Name: ${identity.name}
            Address: ${identity.address}
            URL: ${identity.officialUrl}
        `;

        const stream = runner.runAsync({
            userId,
            sessionId,
            newMessage: { role: 'user', parts: [{ text: prompt }] }
        });

        for await (const event of stream) { }

        const finalSession = await sessionService.getSession({ appName: 'hephae-hub', userId, sessionId });
        const state = finalSession?.state || {};

        console.log("[API/Discover] ADK Pipeline Finished. State keys:", Object.keys(state));

        // Parse social links
        let parsedSocials: any = {};
        if (typeof state.socialLinks === 'string') {
            try {
                parsedSocials = JSON.parse(state.socialLinks.replace(/```json/g, '').replace(/```/g, '').trim());
            } catch (e) {
                console.warn("[API/Discover] Failed to parse social links JSON:", e);
            }
        } else if (typeof state.socialLinks === 'object') {
            parsedSocials = state.socialLinks as any;
        }

        // Parse competitors
        let parsedCompetitors: any[] = [];
        if (typeof state.competitors === 'string') {
            try {
                parsedCompetitors = JSON.parse(state.competitors.replace(/```json/g, '').replace(/```/g, '').trim());
            } catch (e) {
                console.warn("[API/Discover] Failed to parse competitors JSON, attempting extraction...");
                try {
                    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
                    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash", generationConfig: { responseMimeType: "application/json" } });
                    const res = await model.generateContent(`Extract exactly 3 restaurant competitors from the following text into a JSON array with keys: "name", "url", "reason". TEXT: ${state.competitors}`);
                    parsedCompetitors = JSON.parse(res.response.text());
                } catch (extractErr) {
                    console.error("[API/Discover] Forced extraction failed", extractErr);
                }
            }
        } else if (Array.isArray(state.competitors)) {
            parsedCompetitors = state.competitors;
        }

        // Extract and clean menu base64 — will be uploaded to GCS, not stored in DB
        let menuBase64 = state.menuScreenshotBase64 as string | undefined;
        if (menuBase64) {
            try {
                const parsed = JSON.parse(menuBase64);
                if (parsed.screenshotBase64) menuBase64 = parsed.screenshotBase64;
            } catch {
                const base64Match = menuBase64.match(/[A-Za-z0-9+/]{200,}={0,2}/);
                if (base64Match) menuBase64 = base64Match[0];
            }
        }

        // Parse theme data
        let parsedTheme: any = {};
        if (typeof state.themeData === 'string') {
            try {
                parsedTheme = JSON.parse(state.themeData.replace(/```json\n?|\n?```/g, '').trim());
            } catch (e) {
                console.warn("[API/Discover] Failed to parse themeData JSON:", e);
            }
        } else if (typeof state.themeData === 'object' && state.themeData !== null) {
            parsedTheme = state.themeData as any;
        }

        const slug = generateSlug(identity.name);

        // Upload menu screenshot to GCS — never store base64 in DB
        let menuImageUrl: string | undefined;
        if (menuBase64) {
            const url = await uploadMenuScreenshot(slug, menuBase64);
            if (url) menuImageUrl = url;
        }

        const enrichedProfile: EnrichedProfile = {
            ...identity,
            // Send base64 back to UI for immediate display, but DB only gets the GCS URL
            menuScreenshotBase64: menuBase64,
            socialLinks: {
                instagram: parsedSocials.instagram || undefined,
                facebook: parsedSocials.facebook || undefined,
                twitter: parsedSocials.twitter || undefined,
            },
            phone: parsedSocials.phone || undefined,
            email: parsedSocials.email || undefined,
            hours: parsedSocials.hours || undefined,
            googleMapsUrl: state.googleMapsUrl as string | undefined,
            competitors: parsedCompetitors.length > 0 ? parsedCompetitors : undefined,
            favicon: parsedTheme.favicon || undefined,
            logoUrl: parsedTheme.logoUrl || undefined,
            primaryColor: parsedTheme.primaryColor || undefined,
            secondaryColor: parsedTheme.secondaryColor || undefined,
            persona: parsedTheme.persona || undefined,
        };

        // Upload HTML report to GCS
        const reportUrl = await uploadReport({
            slug,
            type: 'profile',
            htmlContent: buildProfileReport({ ...enrichedProfile, menuScreenshotBase64: undefined }),
            identity: enrichedProfile,
            summary: `Business profile for ${enrichedProfile.name}`,
        });

        // Write to Firestore + BQ — no blobs
        writeDiscovery({
            profile: enrichedProfile,
            menuImageUrl,
            triggeredBy: 'user',
        }).catch(err => console.error('[API/Discover] writeDiscovery failed:', err));

        return NextResponse.json({ ...enrichedProfile, reportUrl: reportUrl || undefined });

    } catch (error) {
        console.error("[API/Discover] Orchestration Failed:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
