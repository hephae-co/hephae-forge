import { AgentModels } from "../config";
import { GoogleGenerativeAI } from "@google/generative-ai";
import { BaseIdentity } from '@/agents/types';

export class LocatorAgent {
    static async resolve(query: string): Promise<BaseIdentity> {
        if (!process.env.GEMINI_API_KEY) {
            throw new Error("Missing GEMINI_API_KEY");
        }

        console.log(`[LocatorAgent] Resolving identity for: "${query}"...`);

        const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
        const model = genAI.getGenerativeModel(
            {
                model: AgentModels.DEFAULT_FAST_MODEL,
                tools: [{
                    // @ts-ignore
                    googleSearch: {}
                }]
            },
            { baseUrl: "https://generativelanguage.googleapis.com" }
        );

        const prompt = `Use Google Search to find the official identity details for the business matching the query: "${query}".
Return ONLY a valid JSON object with the following keys:
- "name": Official name of the business
- "address": Full physical address, or City/State if exact address is unknown
- "officialUrl": The official website URL (or Facebook/Yelp if none exists)
- "lat": numerical latitude
- "lng": numerical longitude
Do not include any markdown, explanations, or quotes outside the JSON.`;

        const result = await model.generateContent(prompt);
        const responseText = result.response.text();

        let data;
        try {
            const cleanJson = responseText.replace(/```json/g, "").replace(/```/g, "").trim();
            data = JSON.parse(cleanJson);
        } catch (e) {
            console.error("[LocatorAgent] Failed to parse JSON. Raw response:", responseText);
            throw new Error("LocatorAgent failed to extract structured data from Gemini.");
        }

        let resolvedUrl = data.officialUrl;
        if (!resolvedUrl.startsWith('http')) {
            resolvedUrl = 'https://' + resolvedUrl;
        }

        console.log(`[LocatorAgent] Found: ${data.name} at ${resolvedUrl} (${data.address}) [${data.lat}, ${data.lng}]`);

        return {
            name: data.name,
            address: data.address,
            officialUrl: resolvedUrl,
            coordinates: {
                lat: data.lat || 0,
                lng: data.lng || 0
            }
        };
    }
}
