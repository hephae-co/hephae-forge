"""
Top-level Agentic Model Configuration

Centralizes model strings used by Hephae Hub ADK agents.
Mirror of src/agents/config.ts — keep in sync.
"""

from google.genai.types import GenerateContentConfig, ThinkingConfig


class AgentModels:
    # Primary: cheapest, fastest — default for all agents
    PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"

    # Enhanced: complex structured output (SEO auditor, SQL generation)
    ENHANCED_MODEL = "gemini-3.0-flash-preview"

    # Fallbacks for 429 / model-unavailable errors
    PRIMARY_FALLBACK = "gemini-2.5-flash-lite"
    ENHANCED_FALLBACK = "gemini-2.5-flash"

    # Visual Creative Model: image generation prompts
    CREATIVE_VISION_MODEL = "gemini-3-pro-image-preview"

    # Deprecated aliases — backward compat
    DEFAULT_FAST_MODEL = PRIMARY_MODEL
    DEEP_ANALYST_MODEL = ENHANCED_MODEL
    FALLBACK_LITE_MODEL = PRIMARY_FALLBACK


class ThinkingPresets:
    """Pre-built GenerateContentConfig with thinking levels.

    Use: LlmAgent(generate_content_config=ThinkingPresets.HIGH)
    """

    MEDIUM = GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_level="MEDIUM")
    )
    HIGH = GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_level="HIGH")
    )


# Fallback model mapping: primary model → stable fallback
MODEL_FALLBACK_MAP: dict[str, str] = {
    AgentModels.PRIMARY_MODEL: AgentModels.PRIMARY_FALLBACK,
    AgentModels.ENHANCED_MODEL: AgentModels.ENHANCED_FALLBACK,
}


class StorageConfig:
    BUCKET = "everything-hephae"
    BASE_URL = "https://storage.googleapis.com/everything-hephae"


class AgentVersions:
    """
    Agent version registry.

    MANDATORY: Increment the version for any agent when its output schema changes
    (fields added/removed/renamed = MAJOR bump), logic changes (MINOR bump),
    or prompt-only wording changes (PATCH bump).

    These values are written to BigQuery on every agent run so historical runs
    can be distinguished from runs under a different schema.
    """

    # Discovery pipeline (v4: 4-stage with reviewer + news)
    DISCOVERY_PIPELINE = "4.0.0"
    SITE_CRAWLER = "1.1.0"
    CONTACT_DISCOVERY = "1.0.0"
    MENU_DISCOVERY = "2.1.0"
    SOCIAL_DISCOVERY = "2.0.0"
    SOCIAL_PROFILER = "1.0.0"
    MAPS_DISCOVERY = "2.0.0"
    COMPETITOR_DISCOVERY = "2.0.0"
    THEME_DISCOVERY = "2.0.0"

    # Analysis agents
    MARGIN_SURGEON = "1.0.0"
    SEO_AUDITOR = "1.0.0"
    TRAFFIC_FORECASTER = "1.0.0"
    COMPETITIVE_ANALYZER = "1.0.0"

    # Marketing
    MARKETING_SWARM = "1.0.0"

    # Discovery Stage 4 additions
    NEWS_DISCOVERY = "1.0.0"
    DISCOVERY_REVIEWER = "1.0.0"


class OptimizerVersions:
    """Optimizer agent version registry."""

    PROMPT_OPTIMIZER = "1.0.0"
    AI_COST_OPTIMIZER = "1.0.0"
    CLOUD_COST_OPTIMIZER = "1.0.0"
    PERFORMANCE_OPTIMIZER = "1.0.0"
