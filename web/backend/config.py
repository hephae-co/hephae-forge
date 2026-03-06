"""
Web app configuration.

Model tiers, thinking presets, and fallback maps are imported from hephae_common.
This file adds web-specific config: AgentVersions, OptimizerVersions, StorageConfig re-export.
"""

# Re-export shared config so existing imports don't break
from hephae_common.model_config import (  # noqa: F401
    AgentModels,
    ThinkingPresets,
    MODEL_FALLBACK_MAP,
    StorageConfig,
)


class AgentVersions:
    """
    Agent version registry (web app).

    MANDATORY: Increment the version for any agent when its output schema changes
    (fields added/removed/renamed = MAJOR bump), logic changes (MINOR bump),
    or prompt-only wording changes (PATCH bump).

    These values are written to BigQuery on every agent run so historical runs
    can be distinguished from runs under a different schema.
    """

    # Discovery pipeline (v5: 8-agent fan-out + google_search social profiler)
    DISCOVERY_PIPELINE = "5.0.0"
    SITE_CRAWLER = "1.1.0"
    CONTACT_DISCOVERY = "1.0.0"
    MENU_DISCOVERY = "2.1.0"
    SOCIAL_DISCOVERY = "2.0.0"
    SOCIAL_PROFILER = "2.0.0"
    MAPS_DISCOVERY = "2.0.0"
    COMPETITOR_DISCOVERY = "2.0.0"
    THEME_DISCOVERY = "2.0.0"
    BUSINESS_OVERVIEW = "1.0.0"

    # Analysis agents
    MARGIN_SURGEON = "1.0.0"
    SEO_AUDITOR = "1.0.0"
    TRAFFIC_FORECASTER = "1.0.0"
    COMPETITIVE_ANALYZER = "1.0.0"

    # Marketing
    MARKETING_SWARM = "1.0.0"

    # Social Media Auditor
    SOCIAL_MEDIA_AUDITOR = "1.0.0"

    # Blog
    BLOG_WRITER = "1.0.0"

    # Discovery Stage 4 additions
    NEWS_DISCOVERY = "1.0.0"
    DISCOVERY_REVIEWER = "1.0.0"


class OptimizerVersions:
    """Optimizer agent version registry."""

    PROMPT_OPTIMIZER = "1.0.0"
    AI_COST_OPTIMIZER = "1.0.0"
    CLOUD_COST_OPTIMIZER = "1.0.0"
    PERFORMANCE_OPTIMIZER = "1.0.0"
