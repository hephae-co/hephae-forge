"""
Pydantic v2 models for the web app.

Core shared models are imported from hephae_common.models.
This file re-exports them and adds web-specific types (ChatResponse, blog, social posts, etc.).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Re-export all shared models so existing `from backend.types import X` keeps working
from hephae_common.models import (  # noqa: F401
    Coordinates,
    SocialLinks,
    BaseIdentity,
    Competitor,
    NewsItem,
    ValidationReport,
    SocialPlatformMetrics,
    SocialProfileSummary,
    SocialProfileMetrics,
    AIOverview,
    EnrichedProfile,
    BusinessIdentity,
    MenuItem,
    MenuAnalysisItem,
    SurgicalReport,
    Recommendation,
    Methodology,
    AuditSection,
    SeoReport,
    ForecastSlot,
    ForecastDay,
    ForecastResponse,
    CompetitiveReport,
    V1Response,
)


# ── Web-specific types below ──────────────────────────────────────────────


class CompetitorPrice(BaseModel):
    competitor_name: str
    item_match: str
    price: float
    source_url: str
    distance_miles: Optional[float] = None


class CommodityTrend(BaseModel):
    ingredient: str
    inflation_rate_12mo: float
    trend_description: str


class QuickScanResult(BaseModel):
    url: str
    overall_score: float = Field(alias="overallScore", default=0)
    summary: str = ""
    categories: list[dict] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    role: str = "model"
    text: str = ""
    trigger_capability_handoff: Optional[bool] = Field(None, alias="triggerCapabilityHandoff")
    located_business: Optional[BaseIdentity] = Field(None, alias="locatedBusiness")

    model_config = {"populate_by_name": True}


class MarketingReport(BaseModel):
    summary: str = ""
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True, "extra": "allow"}


class SocialAuditReport(BaseModel):
    overall_score: float = Field(alias="overallScore", default=0)
    summary: str = ""
    platforms: list[dict] = Field(default_factory=list)
    strategic_recommendations: list[dict] = Field(
        default_factory=list, alias="strategicRecommendations"
    )
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True, "extra": "allow"}


class SocialPostContent(BaseModel):
    caption: Optional[str] = None
    post: Optional[str] = None
    tweet: Optional[str] = None


class SocialPostsResponse(BaseModel):
    instagram: SocialPostContent = Field(default_factory=SocialPostContent)
    facebook: SocialPostContent = Field(default_factory=SocialPostContent)
    twitter: SocialPostContent = Field(default_factory=SocialPostContent)


class BlogPostResponse(BaseModel):
    title: str = ""
    html_content: str = Field("", alias="htmlContent")
    report_url: Optional[str] = Field(None, alias="reportUrl")
    hero_image_url: Optional[str] = Field(None, alias="heroImageUrl")
    word_count: int = Field(0, alias="wordCount")
    data_sources: list[str] = Field(default_factory=list, alias="dataSources")

    model_config = {"populate_by_name": True}
