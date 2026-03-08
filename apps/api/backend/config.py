"""
Unified API configuration.

Merges web AgentVersions + admin Settings into a single config module.
Model tiers and thinking presets come from hephae_common.
"""

import os

from pydantic_settings import BaseSettings

# Re-export shared config
from hephae_common.model_config import (  # noqa: F401
    AgentModels,
    ThinkingPresets,
    MODEL_FALLBACK_MAP,
    StorageConfig,
)


class Settings(BaseSettings):
    """Unified settings — superset of web + admin env vars."""

    # Core
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PORT: int = int(os.getenv("PORT", "8080"))

    # Firebase / GCP
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "hephae-co")
    BIGQUERY_PROJECT_ID: str = os.getenv("BIGQUERY_PROJECT_ID", "hephae-co-dev")
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")

    # Auth
    FORGE_API_SECRET: str = os.getenv("FORGE_API_SECRET", "")
    FORGE_V1_API_KEY: str = os.getenv("FORGE_V1_API_KEY", "")
    CRON_SECRET: str = os.getenv("CRON_SECRET", "hephae_cron_secret")

    # Email
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    # Government data APIs
    BLS_API_KEY: str = os.getenv("BLS_API_KEY", "")
    USDA_NASS_API_KEY: str = os.getenv("USDA_NASS_API_KEY", "")

    # Social platform credentials
    X_API_KEY: str = os.getenv("X_API_KEY", "")
    X_API_SECRET: str = os.getenv("X_API_SECRET", "")
    X_ACCESS_TOKEN: str = os.getenv("X_ACCESS_TOKEN", "")
    X_ACCESS_SECRET: str = os.getenv("X_ACCESS_SECRET", "")
    FACEBOOK_PAGE_TOKEN: str = os.getenv("FACEBOOK_PAGE_TOKEN", "")
    FACEBOOK_PAGE_ID: str = os.getenv("FACEBOOK_PAGE_ID", "")
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    # CORS
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    # Batch evaluation
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    BATCH_EVAL_ENABLED: bool = os.getenv("BATCH_EVAL_ENABLED", "true").lower() == "true"
    BATCH_EVAL_GCS_BUCKET: str = os.getenv("BATCH_EVAL_GCS_BUCKET", "hephae-batch-evaluations")
    BATCH_EVAL_FALLBACK_TIMEOUT: int = int(os.getenv("BATCH_EVAL_FALLBACK_TIMEOUT", "300"))

    # Tools
    CRAWL4AI_URL: str = os.getenv("CRAWL4AI_URL", "")


settings = Settings()


class AgentVersions:
    """Agent version registry — merged web + admin versions."""

    # Discovery pipeline
    DISCOVERY_PIPELINE = "5.0.0"
    SITE_CRAWLER = "1.1.0"
    CONTACT_DISCOVERY = "1.0.0"
    CONTACT_AGENT = "2.0.0"  # MAJOR: added emailStatus, contactFormUrl, contactFormStatus fields
    QUALITY_GATE_AGENT = "1.0.1"  # PATCH: added banks and dollar stores to exclusion examples
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

    # Marketing / Social
    MARKETING_SWARM = "1.0.0"
    SOCIAL_MEDIA_AUDITOR = "1.0.0"
    SOCIAL_POST_GENERATOR = "3.0.0"  # MAJOR: CDN report links + social card images, reports via cdn.hephae.co
    BLOG_WRITER = "1.0.0"

    # Research agents
    LOCAL_CATALYST = "1.0.0"
    DEMOGRAPHIC_EXPERT = "1.0.0"

    # Discovery Stage 4
    NEWS_DISCOVERY = "1.0.0"
    DISCOVERY_REVIEWER = "1.0.0"


class OptimizerVersions:
    PROMPT_OPTIMIZER = "1.0.0"
    AI_COST_OPTIMIZER = "1.0.0"
    CLOUD_COST_OPTIMIZER = "1.0.0"
    PERFORMANCE_OPTIMIZER = "1.0.0"
