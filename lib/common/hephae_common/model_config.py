"""
Shared model configuration for all hephae apps.

Centralizes model strings, thinking presets, and fallback maps.
Both web/ and admin/ import from here.
"""

import os

from google.genai.types import GenerateContentConfig, ThinkingConfig


class AgentModels:
    """Model tier definitions for agent selection."""

    # Primary: default for all agents (+ thinking presets for complex analysis)
    PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"

    # Synthesis: higher-quality model for final synthesis stage
    SYNTHESIS_MODEL = "gemini-3-flash-preview"

    # Fallback: auto-fallback on 429/503/529 (sparingly)
    FALLBACK_MODEL = "gemini-3-flash-preview"

    # Visual Creative Model: image generation prompts
    CREATIVE_VISION_MODEL = "gemini-3.1-flash-image-preview"

    # Claude synthesis model — dual-synthesis stage in pulse orchestrator
    CLAUDE_SYNTHESIS_MODEL = "anthropic/claude-haiku-4-5-20251001"

    # Deprecated aliases — backward compat
    DEFAULT_FAST_MODEL = PRIMARY_MODEL
    DEEP_ANALYST_MODEL = PRIMARY_MODEL
    FALLBACK_LITE_MODEL = FALLBACK_MODEL
    ENHANCED_MODEL = PRIMARY_MODEL
    ENHANCED_FALLBACK = FALLBACK_MODEL
    PRIMARY_FALLBACK = FALLBACK_MODEL


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
    DEEP = GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=8192)
    )


# Fallback model mapping: primary model -> stable fallback
MODEL_FALLBACK_MAP: dict[str, str] = {
    AgentModels.PRIMARY_MODEL: AgentModels.FALLBACK_MODEL,
}


class StorageConfig:
    BUCKET = os.getenv("GCS_BUCKET", "")
    BASE_URL = os.getenv("GCS_BASE_URL", "")

    # CDN bucket — public assets served via CDN
    CDN_BUCKET = os.getenv("GCS_CDN_BUCKET", "")
    CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")
