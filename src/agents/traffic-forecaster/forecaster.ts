import { AgentModels } from "../config";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { BaseIdentity } from '@/agents/types';
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
                model: AgentModels.DEFAULT_FAST_MODEL,
                tools: [{ googleSearch: {} } as any]
            });
            const result = await model.generateContent(`Execute this search and summarize the top facts related to: ${query}`);
            return { result: result.response.text() };
        } catch (e: any) {
            return { error: "Search failed." };
        }
    }
});

// NWS weather tool — free, no API key, US-only
const getWeatherForecastTool = new FunctionTool({
    name: 'getWeatherForecast',
    description: 'Get a 3-day structured weather forecast from the National Weather Service (NWS) API using latitude/longitude coordinates. Use this for US locations whenever coordinates are available.',
    parameters: z.object({
        latitude: z.number().describe('Latitude of the location'),
        longitude: z.number().describe('Longitude of the location')
    }),
    execute: async ({ latitude, longitude }) => {
        try {
            // Step 1: Get grid endpoint from NWS points API
            const pointsRes = await fetch(
                `https://api.weather.gov/points/${latitude.toFixed(4)},${longitude.toFixed(4)}`,
                { headers: { 'User-Agent': 'HephaeHub/1.0 (hephae.co)' } }
            );
            if (!pointsRes.ok) {
                return { error: `NWS points lookup failed: ${pointsRes.status}` };
            }
            const pointsData = await pointsRes.json();
            const forecastUrl = pointsData?.properties?.forecast;
            if (!forecastUrl) {
                return { error: 'NWS did not return a forecast URL for these coordinates.' };
            }

            // Step 2: Fetch the actual forecast
            const forecastRes = await fetch(forecastUrl, {
                headers: { 'User-Agent': 'HephaeHub/1.0 (hephae.co)' }
            });
            if (!forecastRes.ok) {
                return { error: `NWS forecast fetch failed: ${forecastRes.status}` };
            }
            const forecastData = await forecastRes.json();
            const periods: any[] = forecastData?.properties?.periods || [];

            // Group into days (NWS returns daytime/nighttime periods)
            const days: Record<string, any> = {};
            for (const period of periods.slice(0, 6)) {
                const date = period.startTime?.split('T')[0];
                if (!date) continue;
                if (!days[date]) days[date] = { date, dayOfWeek: period.name, daytime: null, nighttime: null };
                if (period.isDaytime) {
                    days[date].daytime = {
                        shortForecast: period.shortForecast,
                        temperature: period.temperature,
                        temperatureUnit: period.temperatureUnit,
                        precipitationChance: period.probabilityOfPrecipitation?.value ?? null,
                        windSpeed: period.windSpeed,
                        windDirection: period.windDirection,
                    };
                } else {
                    days[date].nighttime = {
                        shortForecast: period.shortForecast,
                        temperature: period.temperature,
                        temperatureUnit: period.temperatureUnit,
                        precipitationChance: period.probabilityOfPrecipitation?.value ?? null,
                    };
                }
            }

            const forecast = Object.values(days).slice(0, 3).map((day: any) => ({
                date: day.date,
                dayOfWeek: day.dayOfWeek,
                high: day.daytime?.temperature ?? null,
                low: day.nighttime?.temperature ?? null,
                temperatureUnit: day.daytime?.temperatureUnit ?? 'F',
                shortForecast: day.daytime?.shortForecast ?? day.nighttime?.shortForecast ?? 'Unknown',
                precipitationChance: day.daytime?.precipitationChance ?? day.nighttime?.precipitationChance ?? null,
                windSpeed: day.daytime?.windSpeed ?? null,
                windDirection: day.daytime?.windDirection ?? null,
            }));

            return { source: 'NWS (National Weather Service)', forecast };
        } catch (e: any) {
            return { error: `NWS fetch failed: ${e.message}` };
        }
    }
});

const poiGatherer = new LlmAgent({
    name: 'PoiGatherer',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `You are a Location Intelligence Agent. Use Google Search to find Surrounding POIs near the provided business.
    Find: 1. Business Category, 2. Opening Hours (7 days), 3. 5 specific nearby locations (2 Competitors, 2 Event Venues, 3 Traffic Drivers).
    Output exactly the intelligence report as clean markdown text.`,
    tools: [GoogleSearchTool],
    outputKey: 'poiDetails'
});

const weatherGatherer = new LlmAgent({
    name: 'WeatherGatherer',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `You are a Weather Intelligence Agent. Your task is to get a precise 3-day weather forecast for the provided location.

    **STRATEGY:**
    1. If the prompt contains numeric coordinates (latitude and longitude that are not 0,0), call the 'getWeatherForecast' tool with those exact coordinates. This gives you structured NWS data.
    2. Only fall back to 'googleSearch' if: the coordinates are missing or 0,0, or getWeatherForecast returns an error.

    **OUTPUT:** A day-by-day summary for TODAY, TOMORROW, and the DAY AFTER TOMORROW. Include High/Low Temps (°F), precipitation chance (%), wind, and short forecast description. Output as clean markdown text.`,
    tools: [getWeatherForecastTool, GoogleSearchTool],
    outputKey: 'weatherData'
});

const eventsGatherer = new LlmAgent({
    name: 'EventsGatherer',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `You are an Events Intelligence Agent. Use Google Search to find major local events in the provided location for the next 3 days.
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

        const lat = identity.coordinates?.lat ?? 0;
        const lng = identity.coordinates?.lng ?? 0;
        const prompt = `Business: ${identity.name}\nLocation: ${locationQuery}\nLatitude: ${lat}\nLongitude: ${lng}\nToday: ${dateString}\n\nPlease gather intelligence context.`;

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
            model: AgentModels.DEFAULT_FAST_MODEL,
            systemInstruction: "You are an expert Local Foot Traffic Forecaster generating strict JSON based on Intelligence Data.",
        });

        const analystPrompt = `
      **CURRENT DATE**: ${dateString}

      Your task is to generate exactly a 3-day foot traffic forecast based STRICTLY on the gathered intelligence below for ${identity.name}. Never return more than 3 days in the array.

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
