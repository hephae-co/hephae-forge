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

export const StorageConfig = {
    BUCKET: 'everything-hephae',
    BASE_URL: 'https://storage.googleapis.com/everything-hephae',
} as const;

/**
 * Agent version registry.
 *
 * MANDATORY: Increment the version for any agent when its output schema changes
 * (fields added/removed/renamed = MAJOR bump), logic changes (MINOR bump),
 * or prompt-only wording changes (PATCH bump).
 *
 * These values are written to BigQuery on every agent run so historical runs
 * can be distinguished from runs under a different schema.
 */
export const AgentVersions = {
    // Discovery pipeline
    MENU_DISCOVERY:        '1.0.0',
    SOCIAL_DISCOVERY:      '1.0.0',
    MAPS_DISCOVERY:        '1.0.0',
    COMPETITOR_DISCOVERY:  '1.0.0',
    THEME_DISCOVERY:       '1.0.0',

    // Analysis agents
    MARGIN_SURGEON:        '1.0.0',
    SEO_AUDITOR:           '1.0.0',
    TRAFFIC_FORECASTER:    '1.0.0',
    COMPETITIVE_ANALYZER:  '1.0.0',

    // Marketing
    MARKETING_SWARM:       '1.0.0',
} as const;
