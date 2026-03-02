"""
Top-level Agentic Model Configuration

Centralizes model strings used by Hephae Hub ADK agents.
Mirror of src/agents/config.ts — keep in sync.
"""


class AgentModels:
    # Core Reasoning Model: fast, cheap, standard logic (Forecaster, Profiler, Surgeon, Marketing)
    DEFAULT_FAST_MODEL = "gemini-2.5-flash"

    # Deep Analytical Model: complex data parsing, deep SEO logic
    DEEP_ANALYST_MODEL = "gemini-2.5-pro"

    # Visual Creative Model: explicitly tuned for generating image and infographic prompts
    CREATIVE_VISION_MODEL = "gemini-3-pro-image-preview"


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

    # Discovery pipeline (v3: 3-stage with social profiler)
    DISCOVERY_PIPELINE = "3.0.0"
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
