"""
Pydantic v2 models — mirrors src/agents/types.ts + src/lib/types.ts.
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Core identity types (from src/agents/types.ts)
# ---------------------------------------------------------------------------


class Coordinates(BaseModel):
    lat: float
    lng: float


class SocialLinks(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    yelp: Optional[str] = None
    tiktok: Optional[str] = None
    grubhub: Optional[str] = None
    doordash: Optional[str] = None
    ubereats: Optional[str] = None
    seamless: Optional[str] = None
    toasttab: Optional[str] = None


class BaseIdentity(BaseModel):
    name: str
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    official_url: str = Field(alias="officialUrl", default="")

    model_config = {"populate_by_name": True}


class Competitor(BaseModel):
    name: str
    url: str
    reason: Optional[str] = None


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    date: Optional[str] = None
    snippet: Optional[str] = None


class ValidationReport(BaseModel):
    total_urls_checked: int = Field(alias="totalUrlsChecked", default=0)
    valid: int = 0
    invalid: int = 0
    corrected: int = 0

    model_config = {"populate_by_name": True}


class SocialPlatformMetrics(BaseModel):
    url: Optional[str] = None
    username: Optional[str] = None
    page_name: Optional[str] = Field(None, alias="pageName")
    follower_count: Optional[int] = Field(None, alias="followerCount")
    following_count: Optional[int] = Field(None, alias="followingCount")
    post_count: Optional[int] = Field(None, alias="postCount")
    video_count: Optional[int] = Field(None, alias="videoCount")
    like_count: Optional[int] = Field(None, alias="likeCount")
    rating: Optional[float] = None
    review_count: Optional[int] = Field(None, alias="reviewCount")
    price_range: Optional[str] = Field(None, alias="priceRange")
    categories: Optional[list[str]] = None
    bio: Optional[str] = None
    is_verified: Optional[bool] = Field(None, alias="isVerified")
    claimed_by_owner: Optional[bool] = Field(None, alias="claimedByOwner")
    last_post_recency: Optional[str] = Field(None, alias="lastPostRecency")
    engagement_indicator: Optional[str] = Field(None, alias="engagementIndicator")
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class SocialProfileSummary(BaseModel):
    total_followers: int = Field(alias="totalFollowers", default=0)
    strongest_platform: str = Field(alias="strongestPlatform", default="")
    weakest_platform: str = Field(alias="weakestPlatform", default="")
    overall_presence_score: float = Field(alias="overallPresenceScore", default=0)
    posting_frequency: str = Field(alias="postingFrequency", default="unknown")
    recommendation: str = ""

    model_config = {"populate_by_name": True}


class SocialProfileMetrics(BaseModel):
    instagram: Optional[SocialPlatformMetrics] = None
    facebook: Optional[SocialPlatformMetrics] = None
    twitter: Optional[SocialPlatformMetrics] = None
    tiktok: Optional[SocialPlatformMetrics] = None
    yelp: Optional[SocialPlatformMetrics] = None
    summary: Optional[SocialProfileSummary] = None


class EnrichedProfile(BaseIdentity):
    primary_color: Optional[str] = Field(None, alias="primaryColor")
    secondary_color: Optional[str] = Field(None, alias="secondaryColor")
    logo_url: Optional[str] = Field(None, alias="logoUrl")
    favicon: Optional[str] = None
    persona: Optional[str] = None
    menu_url: Optional[str] = Field(None, alias="menuUrl")
    menu_screenshot_base64: Optional[str] = Field(None, alias="menuScreenshotBase64")
    menu_screenshot_url: Optional[str] = Field(None, alias="menuScreenshotUrl")
    menu_html_url: Optional[str] = Field(None, alias="menuHtmlUrl")
    social_links: Optional[SocialLinks] = Field(None, alias="socialLinks")
    phone: Optional[str] = None
    email: Optional[str] = None
    hours: Optional[str] = None
    google_maps_url: Optional[str] = Field(None, alias="googleMapsUrl")
    competitors: Optional[list[Competitor]] = None
    news: Optional[list[NewsItem]] = None
    social_profile_metrics: Optional[SocialProfileMetrics] = Field(None, alias="socialProfileMetrics")
    validation_report: Optional[ValidationReport] = Field(None, alias="validationReport")
    report_url: Optional[str] = Field(None, alias="reportUrl")
    debug_error: Optional[str] = Field(None, alias="_debugError")


# ---------------------------------------------------------------------------
# Business identity (from src/lib/types.ts)
# ---------------------------------------------------------------------------


class BusinessIdentity(BaseModel):
    primary_color: str = Field(alias="primaryColor", default="")
    secondary_color: str = Field(alias="secondaryColor", default="")
    logo_url: Optional[str] = Field(None, alias="logoUrl")
    persona: str = ""
    name: str = ""
    menu_screenshot_base64: Optional[str] = Field(None, alias="menuScreenshotBase64")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Margin analysis types
# ---------------------------------------------------------------------------


class MenuItem(BaseModel):
    item_name: str
    current_price: float
    category: str
    description: Optional[str] = None


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


class MenuAnalysisItem(MenuItem):
    competitor_benchmark: float
    commodity_factor: float
    recommended_price: float
    price_leakage: float
    confidence_score: float
    rationale: str


class SurgicalReport(BaseModel):
    identity: BusinessIdentity
    menu_items: list[MenuAnalysisItem]
    strategic_advice: list[str]
    overall_score: float
    generated_at: str
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# SEO Auditor types
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    severity: str  # 'Critical' | 'Warning' | 'Info'
    title: str
    description: str
    action: str


class Methodology(BaseModel):
    reasoning_steps: list[str] = Field(alias="reasoningSteps", default_factory=list)
    tools_used: list[str] = Field(alias="toolsUsed", default_factory=list)
    search_queries: Optional[list[str]] = Field(None, alias="searchQueries")
    sources_used: Optional[list[dict]] = Field(None, alias="sourcesUsed")

    model_config = {"populate_by_name": True}


class AuditSection(BaseModel):
    id: str
    title: str
    score: float
    description: Optional[str] = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    methodology: Optional[Methodology] = None
    is_analyzed: Optional[bool] = Field(None, alias="isAnalyzed")

    model_config = {"populate_by_name": True}


class SeoReport(BaseModel):
    overall_score: float = Field(alias="overallScore", default=0)
    summary: str = ""
    url: str = ""
    sections: list[AuditSection] = Field(default_factory=list)
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True}


class QuickScanResult(BaseModel):
    url: str
    overall_score: float = Field(alias="overallScore", default=0)
    summary: str = ""
    categories: list[dict] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Traffic Forecaster types
# ---------------------------------------------------------------------------


class ForecastSlot(BaseModel):
    time: str
    score: float
    label: Optional[str] = None
    weather: Optional[str] = None


class ForecastDay(BaseModel):
    date: str
    day_of_week: str = Field(alias="dayOfWeek", default="")
    slots: list[ForecastSlot] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ForecastResponse(BaseModel):
    business_name: str = Field(alias="businessName", default="")
    forecast: list[ForecastDay] = Field(default_factory=list)
    summary: Optional[str] = None
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Chat types
# ---------------------------------------------------------------------------


class ChatResponse(BaseModel):
    role: str = "model"
    text: str = ""
    trigger_capability_handoff: Optional[bool] = Field(None, alias="triggerCapabilityHandoff")
    located_business: Optional[BaseIdentity] = Field(None, alias="locatedBusiness")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Competitive Analysis types
# ---------------------------------------------------------------------------


class CompetitiveReport(BaseModel):
    market_summary: str = Field(alias="market_summary", default="")
    competitors: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Marketing Swarm types
# ---------------------------------------------------------------------------


class MarketingReport(BaseModel):
    summary: str = ""
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True, "extra": "allow"}


# ---------------------------------------------------------------------------
# Social Post Generator types
# ---------------------------------------------------------------------------


class SocialPostContent(BaseModel):
    caption: Optional[str] = None  # Instagram
    post: Optional[str] = None  # Facebook


class SocialPostsResponse(BaseModel):
    instagram: SocialPostContent = Field(default_factory=SocialPostContent)
    facebook: SocialPostContent = Field(default_factory=SocialPostContent)


# ---------------------------------------------------------------------------
# V1 API envelope
# ---------------------------------------------------------------------------


class V1Response(BaseModel, Generic[T]):
    success: bool = True
    data: T
