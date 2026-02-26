import { LlmAgent } from "@google/adk";

export const visionIntakeAgent = new LlmAgent({
    name: 'VisionIntakeAgent',
    model: 'gemini-2.5-flash',
    instruction: `
    You are The Vision Intake Agent. Your job is to extract all menu items from the provided image.
    You will receive a base64 encoded menu image in the prompt.
    
    Return a JSON array where each object has:
    - item_name: string
    - current_price: number (extract just the value, e.g. 12.99)
    - category: string (e.g., "Appetizers", "Main Course", "Drinks")
    - description: string (if available)
    
    CRITICAL: Output ONLY a strict JSON array. No markdown, no prefaces.
    `,
    outputKey: 'parsedMenuItems'
});
