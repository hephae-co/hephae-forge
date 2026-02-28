import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import path from "path";

const MCP_SERVER_PATH = path.resolve(process.cwd(), "mcp-servers/market-truth/build/index.js");

// Singleton stored on globalThis so it survives Next.js hot reloads
const g = global as typeof globalThis & {
    _mcpClient?: Client;
    _mcpTransport?: StdioClientTransport;
};

async function getOrCreateClient(): Promise<Client> {
    if (g._mcpClient) return g._mcpClient;

    const transport = new StdioClientTransport({
        command: "node",
        args: [MCP_SERVER_PATH]
    });

    const client = new Client(
        { name: "hephae-hub-client", version: "1.0.0" },
        { capabilities: {} }
    );

    await client.connect(transport);

    g._mcpClient = client;
    g._mcpTransport = transport;

    return client;
}

export async function callMarketTruthTool(toolName: string, args: Record<string, any> = {}) {
    const client = await getOrCreateClient();

    try {
        const result = await client.callTool({
            name: toolName,
            arguments: args
        });

        // Ensure we gracefully return parsed JSON if it's text
        const content = result.content as Array<any>;
        if (Array.isArray(content) && content.length > 0 && content[0].type === "text") {
            try {
                return JSON.parse(content[0].text);
            } catch (e) {
                return content[0].text;
            }
        }
        return content;

    } catch (e) {
        // Force reconnect on next call
        g._mcpClient = undefined;
        g._mcpTransport = undefined;
        throw e;
    }
}
