/**
 * Top-level Agentic Model Configuration
 * 
 * This file centralizes the model strings used by the Hephae Hub ADK agents.
 * Centralizing these values allows us to systematically swap underlying models
 * depending on cost, performance needs, and new agentic capabilities without
 * rewriting individual agent definitions.
 */

export const AgentModels = {
    // Core Reasoning Model: fast, cheap, standard logic (Forecaster, Profiler, Surgeon, Marketing)
    DEFAULT_FAST_MODEL: 'gemini-2.5-flash',

    // Deep Analytical Model: complex data parsing, deep SEO logic
    DEEP_ANALYST_MODEL: 'gemini-2.5-pro',

    // Visual Creative Model: explicitly tuned for generating image and infographic prompts
    CREATIVE_VISION_MODEL: 'gemini-3-pro-image-preview',
} as const;
