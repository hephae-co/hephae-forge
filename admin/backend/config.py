"""
Admin app configuration.

Model tiers, thinking presets, and fallback maps are imported from hephae_common.
This file adds admin-specific config: Settings, social credentials, etc.
"""

import os
from pydantic_settings import BaseSettings

# Re-export shared config so existing imports don't break
from hephae_common.model_config import (  # noqa: F401
    AgentModels,
    ThinkingPresets,
    MODEL_FALLBACK_MAP,
    StorageConfig,
)


class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    FORGE_URL: str = os.getenv("FORGE_URL", os.getenv("MARGIN_SURGEON_URL", "http://localhost:3000"))
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "hephae-co")
    BIGQUERY_PROJECT_ID: str = os.getenv("BIGQUERY_PROJECT_ID", "hephae-co-dev")
    CRON_SECRET: str = os.getenv("CRON_SECRET", "hephae_cron_secret")
    PORT: int = int(os.getenv("PORT", "8000"))
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

    # Forge API auth
    FORGE_API_SECRET: str = os.getenv("FORGE_API_SECRET", "")
    FORGE_V1_API_KEY: str = os.getenv("FORGE_V1_API_KEY", "")

    # Batch evaluation settings
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    VERTEX_AI_LOCATION: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
    BATCH_EVAL_ENABLED: bool = os.getenv("BATCH_EVAL_ENABLED", "true").lower() == "true"
    BATCH_EVAL_GCS_BUCKET: str = os.getenv("BATCH_EVAL_GCS_BUCKET", "hephae-batch-evaluations")
    BATCH_EVAL_FALLBACK_TIMEOUT: int = int(os.getenv("BATCH_EVAL_FALLBACK_TIMEOUT", "300"))


settings = Settings()
