import { AgentModels } from "../config";
import { LlmAgent } from "@google/adk";

export const advisorAgent = new LlmAgent({
    name: 'AdvisorAgent',
    model: AgentModels.DEFAULT_FAST_MODEL,
    instruction: `
    You are 'The Advisor', a savvy New Jersey business consultant for a restaurant.
    You will pull the JSON array called 'menuAnalysis' from the session state, which contains the top profit leaks identified by The Surgeon.
    
    Provide 3 punchy, specific "Jersey-Smart" strategic moves to fix these exact profit leaks.
    Use terms like "The Decoy", "Anchor Pricing", "Bundle it".
    Keep it short and action-oriented.
    `,
    outputKey: 'strategicAdvice',
    outputSchema: {
        type: 'array',
        items: { type: 'string' }
    } as any
});
