import { GoogleGenerativeAI } from "@google/generative-ai";
import { BaseIdentity } from "./types";
import { ForecastResponse } from "@/components/Chatbot/types";
import { FunctionTool, LlmAgent, ParallelAgent, Runner, InMemorySessionService } from "@google/adk";
import { z } from "zod";

// Create a deterministic Google Search Tool for context gatherers
const GoogleSearchTool = new FunctionTool({
    name: 'googleSearch',
    description: 'Search Google for a query to find factual information, weather, or local events.',
    parameters: z.object({ query: z.string() }),
    execute: async ({ query }) => {
        try {
            const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
            const model = genAI.getGenerativeModel({
                model: "gemini-2.5-flash",
                tools: [{ googleSearch: {} } as any]
            });
            const result = await model.generateContent(`Execute this search and summarize the top facts related to: ${query}`);
            return { result: result.response.text() };
        } catch (e: any) {
            return { error: "Search failed." };
        }
    }
});

const poiGatherer = new LlmAgent({
    name: 'PoiGatherer',
    model: 'gemini-2.5-flash',
    instruction: `You are a Location Intelligence Agent. Use Google Search to find Surrounding POIs near the provided business.
    Find: 1. Business Category, 2. Opening Hours (7 days), 3. 5 specific nearby locations (2 Competitors, 2 Event Venues, 3 Traffic Drivers).
    Output exactly the intelligence report as clean markdown text.`,
    tools: [GoogleSearchTool],
    outputKey: 'poiDetails'
});

const weatherGatherer = new LlmAgent({
    name: 'WeatherGatherer',
    model: 'gemini-2.5-flash',
    instruction: `You are a Weather Intelligence Agent. Use Google Search to find the 7-day weather forecast for the provided location starting today.
    Output day-by-day summary including High/Low Temps, Precipitation, and severe weather alerts as clean markdown text.`,
    tools: [GoogleSearchTool],
    outputKey: 'weatherData'
});

const eventsGatherer = new LlmAgent({
    name: 'EventsGatherer',
    model: 'gemini-2.5-flash',
    instruction: `You are an Events Intelligence Agent. Use Google Search to find major local events in the provided location for the next 7 days.
    Output a day-by-day list of events as clean markdown text.`,
    tools: [GoogleSearchTool],
    outputKey: 'eventsData'
});

const contextGatheringPipeline = new ParallelAgent({
    name: 'ContextGatherer',
    description: 'Gathers POIs, Weather, and Events in parallel.',
    subAgents: [poiGatherer, weatherGatherer, eventsGatherer]
});

export class ForecasterAgent {
    static async forecast(identity: BaseIdentity): Promise<ForecastResponse> {
        if (!process.env.GEMINI_API_KEY) throw new Error("Missing GEMINI_API_KEY");

        console.log(`[ForecasterAgent] Gathering Intelligence via ParallelAgent for: ${identity.name}...`);

        const today = new Date();
        const dateString = today.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        const locationQuery = identity.address || `${identity.coordinates?.lat}, ${identity.coordinates?.lng}`;

        const sessionService = new InMemorySessionService();
        const runner = new Runner({ appName: 'hephae-hub', agent: contextGatheringPipeline, sessionService });

        const sessionId = "forecast-" + Date.now();
        await sessionService.createSession({ appName: 'hephae-hub', sessionId, userId: 'sys', state: {} });

        const prompt = `Business: ${identity.name}\nLocation: ${locationQuery}\nToday: ${dateString}\n\nPlease gather intelligence context.`;

        const stream = runner.runAsync({
            sessionId, userId: 'sys',
            newMessage: { role: 'user', parts: [{ text: prompt }] }
        });

        for await (const event of stream) { }

        const finalSession = await sessionService.getSession({ appName: 'hephae-hub', sessionId, userId: 'sys' });
        const state = finalSession?.state || {};

        const poiDetails = state.poiDetails || "No POI data found.";
        const weatherData = state.weatherData || "No weather data found.";
        const eventsData = state.eventsData || "No events data found.";

        // 4. Synthesis
        console.log(`[ForecasterAgent] Intelligence gathered. Synthesizing report...`);
        const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
        const synthesisModel = genAI.getGenerativeModel({
            model: "gemini-2.5-flash",
            systemInstruction: "You are an expert Local Foot Traffic Forecaster generating strict JSON based on Intelligence Data.",
        });

        const analystPrompt = `
      **CURRENT DATE**: ${dateString}
      
      Your task is to generate a 7-day foot traffic forecast based STRICTLY on the gathered intelligence below for ${identity.name}.

      ### 1. BUSINESS INTELLIGENCE
      ${poiDetails}

      ### 2. WEATHER INTELLIGENCE
      ${weatherData}

      ### 3. EVENT INTELLIGENCE
      ${eventsData}

      **ANALYSIS RULES**:
      1. **HOURS**: If the business is CLOSED, Traffic Level MUST be "Closed".
      2. **WEATHER**: If Severe Weather is detected, REDUCE traffic scores.
      3. **EVENTS & DISTANCE**: Major nearby events boost traffic scores significantly. Event Venues and Competitors must be added to nearbyPOIs.
      
      **OUTPUT**:
      Return ONLY valid JSON matching this structure perfectly. Do not include markdown \`\`\`json blocks.
      {
        "business": {
          "name": "${identity.name}",
          "address": "${identity.address || ""}",
          "coordinates": { "lat": ${identity.coordinates?.lat || 0}, "lng": ${identity.coordinates?.lng || 0} },
          "type": "String",
          "nearbyPOIs": [ 
              { "name": "String", "lat": Number, "lng": Number, "type": "String (e.g. 'Competitor', 'Event Venue', 'School')" } 
          ]
        },
        "summary": "Executive summary of the week.",
        "forecast": [
          {
            "date": "YYYY-MM-DD",
            "dayOfWeek": "String",
            "localEvents": ["String"],
            "weatherNote": "String",
            "slots": [
               { "label": "Morning", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" },
               { "label": "Lunch", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" },
               { "label": "Afternoon", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" },
               { "label": "Evening", "score": 0, "level": "Low/Medium/High/Closed", "reason": "String" }
            ]
          }
        ]
      }
    `;

        const response = await synthesisModel.generateContent({
            contents: [{ role: "user", parts: [{ text: analystPrompt }] }],
            generationConfig: {
                responseMimeType: "application/json",
                temperature: 0.2
            }
        });

        const text = response.response.text();
        try {
            return JSON.parse(text) as ForecastResponse;
        } catch (e) {
            console.error("[ForecasterAgent] Failed to parse Synthesis Output:", text);
            throw new Error("Forecaster API returned malformed JSON.");
        }
    }
}
