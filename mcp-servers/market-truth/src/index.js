import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, } from "@modelcontextprotocol/sdk/types.js";
import * as admin from "firebase-admin";
import * as dotenv from "dotenv";
import path from "path";
// Load environment variables
dotenv.config({ path: path.resolve(process.cwd(), "../../.env.local") });
// Initialize Firebase Admin for caching
// Requires FIREBASE_ADMIN_PRIVATE_KEY, FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL in .env.local
try {
    if (!admin.apps.length) {
        // If the private key is formatted with actual literal '\n' characters, replace them
        const privateKey = process.env.FIREBASE_ADMIN_PRIVATE_KEY?.replace(/\\n/g, '\n');
        admin.initializeApp({
            credential: admin.credential.cert({
                projectId: process.env.FIREBASE_PROJECT_ID || "",
                clientEmail: process.env.FIREBASE_CLIENT_EMAIL || "",
                privateKey: privateKey || "",
            }),
        });
        console.error("Firebase Admin initialized successfully in MCP Server.");
    }
}
catch (error) {
    console.error("Failed to initialize Firebase Admin:", error);
}
const db = admin.firestore();
// Define Tools
const getUsdaWholesalePricesTool = {
    name: "get_usda_wholesale_prices",
    description: "Fetches current 'Northeast Regional' wholesale reports from USDA (ESMIS). Use this to determine exact underlying Cost of Goods Sold (COGS) for restaurant menu margins.",
    inputSchema: {
        type: "object",
        properties: {
            commodity_type: {
                type: "string",
                description: "The type of commodity to check (e.g., 'eggs', 'dairy', 'beef', 'poultry')",
                enum: ["eggs", "dairy", "beef", "poultry"]
            },
        },
        required: ["commodity_type"],
    },
};
const getBlsCpiDataTool = {
    name: "get_bls_cpi_data",
    description: "Accesses the Consumer Price Index for local inflation trends from the BLS Public Data API. Use this to justify whether a restaurant can safely raise prices based on regional inflation.",
    inputSchema: {
        type: "object",
        properties: {
            region_code: {
                type: "string",
                description: "The region code to check (e.g., 'Northeast', 'Midwest', 'South', 'West')",
                enum: ["Northeast", "Midwest", "South", "West"]
            },
        },
        required: ["region_code"],
    },
};
const getFredEconomicIndicatorsTool = {
    name: "get_fred_economic_indicators",
    description: "Retrieves regional economic health indicators for the Northeast from the FRED API. Use this to gauge local consumer spending power.",
    inputSchema: {
        type: "object",
        properties: {
            series_id: {
                type: "string",
                description: "The specific FRED series ID (e.g., 'UNRATE' for Unemployment, 'MEHOINUSA672N' for Median Household Income)",
            },
        },
        required: ["series_id"],
    },
};
// Start Server
const server = new Server({
    name: "market-truth-mcp",
    version: "1.0.0",
}, {
    capabilities: {
        tools: {},
    },
});
// Register Tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
        tools: [
            getUsdaWholesalePricesTool,
            getBlsCpiDataTool,
            getFredEconomicIndicatorsTool
        ],
    };
});
// Tool Handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    try {
        if (name === "get_usda_wholesale_prices") {
            const { commodity_type } = args;
            // TODO: Implement actual USDA logic and Firestore 7-day Cache
            return {
                content: [
                    {
                        type: "text",
                        text: JSON.stringify({
                            commodity: commodity_type,
                            region: "Northeast",
                            pricePerUnit: commodity_type === "eggs" ? "$1.45/dozen" : "$4.30/lb",
                            trend30Day: "+2.4%",
                            source: "USDA ESMIS (Mocked for Scaffolding)",
                            cached: true
                        }, null, 2),
                    },
                ],
            };
        }
        else if (name === "get_bls_cpi_data") {
            const { region_code } = args;
            // TODO: Implement actual BLS logic and Firestore 30-day Cache
            return {
                content: [
                    {
                        type: "text",
                        text: JSON.stringify({
                            region: region_code,
                            cpiYoY: "3.2%",
                            foodAwayFromHomeYoY: "4.1%",
                            source: "BLS Public Data API (Mocked)",
                            cached: true
                        }, null, 2),
                    }
                ]
            };
        }
        else if (name === "get_fred_economic_indicators") {
            const { series_id } = args;
            // TODO: Implement FRED logic and Firestore 30-day Cache
            return {
                content: [
                    {
                        type: "text",
                        text: JSON.stringify({
                            series_id: series_id,
                            currentValue: "4.1",
                            observationDate: "2026-01-01",
                            source: "FRED (Mocked)",
                            cached: true
                        }, null, 2),
                    }
                ]
            };
        }
        throw new Error(`Unknown tool: ${name}`);
    }
    catch (error) {
        if (error instanceof Error) {
            return {
                content: [{ type: "text", text: `Error: ${error.message}` }],
                isError: true,
            };
        }
        return {
            content: [{ type: "text", text: "Unknown error occurred" }],
            isError: true,
        };
    }
});
// Connect Transport
async function main() {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Market Truth MCP Server running on stdio");
}
main().catch((error) => {
    console.error("Fatal error in main():", error);
    process.exit(1);
});
//# sourceMappingURL=index.js.map