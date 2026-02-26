import { LocatorAgent } from './src/lib/agents/core/locator';
import { ProfilerAgent } from './src/lib/agents/core/profiler';

const queries = [
    "Bosphorus Nutley",
    "Tiktok diner Clifton",
    "BGL nutley"
];

async function runTest() {
    console.log("==========================================");
    console.log("Starting ADK Agents Test Script");
    console.log("==========================================\n");

    for (const query of queries) {
        console.log(`\n--- Evaluating Hand-off for: "${query}" ---`);
        try {
            // STEP 1: LocatorAgent identifies the real business
            const identity = await LocatorAgent.resolve(query);
            console.log(`✓ LocatorAgent succeeded:`);
            console.log(`  - Name: ${identity.name}`);
            console.log(`  - Address: ${identity.address}`);
            console.log(`  - URL: ${identity.officialUrl}`);

            // STEP 2: ProfilerAgent extracts its rich state
            const profile = await ProfilerAgent.profile(identity);
            console.log(`✓ ProfilerAgent succeeded:`);
            console.log(`  - Persona: ${profile.persona}`);
            console.log(`  - Primary Color: ${profile.primaryColor}`);
            console.log(`  - Logo URL: ${profile.logoUrl || 'None'}`);
            console.log(`  - Has Menu Screenshot: ${!!profile.menuScreenshotBase64}`);

            if (profile._debugError) {
                console.warn(`! Profiler warning: ${profile._debugError}`);
            }

        } catch (err: any) {
            console.error(`X Failed entirely on "${query}":`, err.message);
        }
    }

    console.log("\n==========================================");
    console.log("Test execution completed.");
    console.log("==========================================");
}

runTest();
