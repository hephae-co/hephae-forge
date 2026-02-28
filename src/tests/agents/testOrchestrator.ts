import { LlmAgent, Runner, InMemorySessionService } from "@google/adk";
import { z } from "zod";

export const testEvaluatorAgent = new LlmAgent({
    name: 'TestEvaluatorAgent',
    model: 'gemini-2.5-flash',
    instruction: `
    You are an expert AI Quality Assurance Judge. Your job is to evaluate the outputs of Hephae Hub's sub-agents across 5 distinct geographic regions. 

    You will receive a JSON payload containing the agent's name, the target restaurant, the raw agent output, and the evaluation criteria.

    You must grade the agent's performance strictly on a scale of 0 to 100 based on the criteria.
    You must also provide a short, specific 1-sentence justification for why you gave that score.
    
    If the agent hallucinated impossible facts, ignored the region, or failed the core objective, deduct massive points.
    
    CRITICAL: You MUST return ONLY a valid JSON object with the keys "score" (0-100), "justification" (string), and "pass" (boolean).
    `,
    outputKey: 'evaluation'
});

// Helper function to run the evaluation
export async function evaluateAgentOutput(
    agentName: string,
    restaurantName: string,
    location: string,
    rawOutput: any,
    criteria: string
) {
    console.log(`\n⏳ [Evaluator] Grading ${agentName} for ${restaurantName}...`);

    const evaluationRequest = {
        target_agent: agentName,
        target_restaurant: { name: restaurantName, location: location },
        evaluation_criteria: criteria,
        raw_agent_output: rawOutput
    };

    const sessionService = new InMemorySessionService();
    const runner = new Runner({ appName: 'evaluator', agent: testEvaluatorAgent, sessionService });
    const sessionId = "eval-" + Date.now() + Math.random().toString(36).substring(7);

    await sessionService.createSession({ appName: 'evaluator', sessionId, userId: 'sys', state: {} });

    try {
        const stream = runner.runAsync({
            sessionId, userId: 'sys',
            newMessage: { role: 'user', parts: [{ text: JSON.stringify(evaluationRequest, null, 2) }] }
        });

        for await (const event of stream) { }

        const finalSession = await sessionService.getSession({ appName: 'evaluator', sessionId, userId: 'sys' });
        const state = finalSession?.state || {};

        if (state.evaluation) {
            try {
                const evalStr = String(state.evaluation);
                const parsed = JSON.parse(evalStr.replace(/```json/gi, '').replace(/```/g, '').trim());
                if (parsed.score !== undefined) return parsed;
            } catch (err) {
                console.error("Failed to parse evaluation JSON", err);
            }
        }
    } catch (e) {
        console.error("Evaluator failed:", e);
    }

    return { score: 0, justification: "Evaluator failed to generate a score.", pass: false };
}
