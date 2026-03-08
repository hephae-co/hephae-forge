"""
Shared model configuration for all hephae apps.

Centralizes model strings, thinking presets, and fallback maps.
Both web/ and admin/ import from here.
"""

from google.genai.types import GenerateContentConfig, ThinkingConfig


class AgentModels:
    """Model tier definitions for agent selection."""

    # Primary: cheapest, fastest — default for all agents
    PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"

    # Enhanced: complex structured output (SEO auditor, evaluators)
    ENHANCED_MODEL = "gemini-2.5-flash"

    # Fallbacks for 429 / model-unavailable errors
    PRIMARY_FALLBACK = "gemini-2.5-flash-lite"
    ENHANCED_FALLBACK = "gemini-2.5-flash"

    # Visual Creative Model: image generation prompts
    CREATIVE_VISION_MODEL = "gemini-3-pro-image-preview"

    # Deprecated aliases — backward compat (web app only)
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


# Fallback model mapping: primary model -> stable fallback
MODEL_FALLBACK_MAP: dict[str, str] = {
    AgentModels.PRIMARY_MODEL: AgentModels.PRIMARY_FALLBACK,
    AgentModels.ENHANCED_MODEL: AgentModels.ENHANCED_FALLBACK,
}


class StorageConfig:
    BUCKET = "everything-hephae"
    BASE_URL = "https://storage.googleapis.com/everything-hephae"

    # CDN bucket — public assets served via cdn.hephae.co
    CDN_BUCKET = "hephae-co-dev-prod-cdn-assets"
    CDN_BASE_URL = "https://cdn.hephae.co"
