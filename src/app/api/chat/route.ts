import { NextRequest, NextResponse } from "next/server";
import { GoogleGenerativeAI, SchemaType } from "@google/generative-ai";
import { LocatorAgent } from "@/lib/agents/core/locator";

export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { messages } = body;

        if (!messages || !Array.isArray(messages)) {
            return NextResponse.json({ error: "Invalid messages array" }, { status: 400 });
        }

        if (!process.env.GEMINI_API_KEY) {
            return NextResponse.json({ error: "Missing GEMINI_API_KEY" }, { status: 500 });
        }

        const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

        // Using function calling to give Gemini the ability to search for businesses
        const model = genAI.getGenerativeModel({
            model: "gemini-2.5-flash",
            systemInstruction: "You are Hephae, an intelligent assistant for business owners. Your primary capability is locating businesses and triggering deep-dives like Margin Analysis or Foot Traffic. If the user mentions a business, immediately use the `locate_business` tool to find its coordinates and URL. Be concise.",
            tools: [
                {
                    functionDeclarations: [
                        {
                            name: "locate_business",
                            description: "Resolves a conversational query for a business into canonical identity details like Address, Coordinates, and official URL. Always call this when the user asks to analyze a specific place or name.",
                            parameters: {
                                type: SchemaType.OBJECT,
                                properties: {
                                    query: {
                                        type: SchemaType.STRING,
                                        description: "The search query (e.g. 'Bosphorus Nutley')",
                                    },
                                },
                                required: ["query"],
                            },
                        }
                    ],
                },
            ],
        }, { baseUrl: "https://generativelanguage.googleapis.com" });

        let history = messages.slice(0, -1).map((m: any) => ({
            role: m.role === 'user' ? 'user' : 'model',
            parts: [{ text: m.text }]
        }));

        // Gemini SDK requires the first message in history to be from the user
        while (history.length > 0 && history[0].role === 'model') {
            history.shift();
        }

        const chat = model.startChat({ history });

        const latestMessage = messages[messages.length - 1].text;
        const result = await chat.sendMessage(latestMessage);

        const response = result.response;
        const functionCalls = response.functionCalls();

        // If the model decides to call the tool!
        if (functionCalls && functionCalls.length > 0) {
            const call = functionCalls[0];
            if (call.name === "locate_business") {
                const queryArgs = call.args as { query: string };
                console.log(`[API/Chat] Model called locate_business with args:`, queryArgs);

                try {
                    const identity = await LocatorAgent.resolve(queryArgs.query);
                    return NextResponse.json({
                        role: "model",
                        text: `I found **${identity.name}** at ${identity.address}. What would you like to do next?`,
                        triggerCapabilityHandoff: true,
                        locatedBusiness: identity
                    });
                } catch (e: any) {
                    return NextResponse.json({
                        role: "model",
                        text: `I couldn't locate "${queryArgs.query}". Could you provide a bit more detail?`,
                    });
                }
            }
        }

        // Otherwise just standard conversation
        return NextResponse.json({
            role: "model",
            text: response.text(),
        });

    } catch (error: any) {
        console.error("[API/Chat] Failed:", error);
        return NextResponse.json({ error: error.message || "Internal Server Error" }, { status: 500 });
    }
}
