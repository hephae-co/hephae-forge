import { CreativeDirectorAgent } from '../../agents/marketing-swarm/creativeDirector';
import { PlatformRouterAgent } from '../../agents/marketing-swarm/platformRouter';
import { InstagramCopywriterAgent } from '../../agents/marketing-swarm/copywriters';
import { Runner, InMemorySessionService } from '@google/adk';

async function runAdkAgent(agent: any, input: string) {
    const sessionService = new InMemorySessionService();
    const runner = new Runner({ appName: 'hephae-marketing', agent, sessionService });
    const sessionId = "marketing-" + Date.now();

    await sessionService.createSession({ appName: 'hephae-marketing', sessionId, userId: 'sys', state: {} });

    const stream = runner.runAsync({
        sessionId, userId: 'sys',
        newMessage: { role: 'user', parts: [{ text: input }] }
    });

    let textBuffer = "";
    for await (const rawEvent of stream) {
        const event = rawEvent as any;
        if (event.content?.parts) {
            for (const part of event.content.parts) {
                if (part.text) textBuffer += part.text;
            }
        }
    }
    return textBuffer;
}

async function runMarketingSwarmTest() {
    console.log("🚀 Initializing Agentic Marketing Swarm E2E Test...\n");

    const mockReport = {
        identity: {
            name: "The Bosphorus Mediterranean Cuisine",
            socialLinks: { instagram: "@bosphorus_nj", facebook: "TheBosphorusNJ" },
            persona: "Authentic Turkish Dining"
        },
        menu_items: [
            { item_name: "Chicken Kebab Plate", current_price: 18.50, competitor_benchmark: 18.00, price_leakage: 0 },
            { item_name: "Shepherd Salad", current_price: 9.00, competitor_benchmark: 14.50, price_leakage: 5.50 } // Massive leakage!
        ],
        overall_score: 72
    };

    console.log("1. Executing CreativeDirectorAgent (The Strategist)...");
    const directorRaw = await runAdkAgent(CreativeDirectorAgent, JSON.stringify(mockReport));
    const directorPayload = JSON.parse(directorRaw.replace(/```json|```/gi, '').trim());
    console.log("   -> Sassy Hook:", directorPayload.hook);
    console.log("   -> Data Point:", directorPayload.data_point);

    console.log("\n2. Executing PlatformRouterAgent (The Distributor)...");
    const routerRaw = await runAdkAgent(PlatformRouterAgent, JSON.stringify(directorPayload));
    const routerPayload = JSON.parse(routerRaw.replace(/```json|```/gi, '').trim());
    console.log("   -> Selected Platform:", routerPayload.platform);
    console.log("   -> Routing Reasoning:", routerPayload.reasoning);

    if (routerPayload.platform === "Instagram") {
        console.log("\n3. Executing InstagramCopywriterAgent (The Writer)...");
        const copywriterInput = JSON.stringify({
            ...directorPayload,
            restaurant_name: mockReport.identity.name,
            social_handle: mockReport.identity.socialLinks.instagram
        });
        const captionRaw = await runAdkAgent(InstagramCopywriterAgent, copywriterInput);
        const captionPayload = JSON.parse(captionRaw.replace(/```json|```/gi, '').trim());

        console.log("\n================ GENERATED INSTAGRAM POST ================\n");
        console.log(captionPayload.caption);
        console.log("\n==========================================================\n");
    }

    console.log("✅ Marketing Swarm E2E Complete.");
}

runMarketingSwarmTest().catch(console.error);
