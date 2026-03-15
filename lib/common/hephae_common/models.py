"""
Unified Pydantic v2 models — shared across all hephae services.

These core data types flow between web and admin.
Source of truth for all business, research, and workflow state.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

# Re-export agent output schemas for backward compatibility
try:
    from hephae_db.schemas import CountyResolverOutput  # noqa: F401
except ImportError:
    # Fallback if DB package not installed during build/test
    CountyResolverOutput = Any

T = TypeVar("T")


# ── Core Identity ─────────────────────────────────────────────────────────


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


# ── Social Profile Metrics ────────────────────────────────────────────────


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


# ── AI Overview ───────────────────────────────────────────────────────────


class AIOverview(BaseModel):
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    business_type: Optional[str] = Field(None, alias="businessType")
    price_range: Optional[str] = Field(None, alias="priceRange")
    established: Optional[str] = None
    notable_mentions: list[str] = Field(default_factory=list, alias="notableMentions")
    reputation_signals: Optional[str] = Field(None, alias="reputationSignals")
    sources: list[dict] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}


# ── Enriched Profile ──────────────────────────────────────────────────────


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
    email_status: Optional[str] = Field(None, alias="emailStatus")
    contact_form_url: Optional[str] = Field(None, alias="contactFormUrl")
    contact_form_status: Optional[str] = Field(None, alias="contactFormStatus")
    hours: Optional[str] = None
    google_maps_url: Optional[str] = Field(None, alias="googleMapsUrl")
    competitors: Optional[list[Competitor]] = None
    news: Optional[list[NewsItem]] = None
    social_profile_metrics: Optional[SocialProfileMetrics] = Field(None, alias="socialProfileMetrics")
    ai_overview: Optional[AIOverview] = Field(None, alias="aiOverview")
    validation_report: Optional[ValidationReport] = Field(None, alias="validationReport")
    report_url: Optional[str] = Field(None, alias="reportUrl")
    debug_error: Optional[str] = Field(None, alias="_debugError")


# ── Business Identity (branding subset) ───────────────────────────────────


class BusinessIdentity(BaseModel):
    primary_color: str = Field(alias="primaryColor", default="")
    secondary_color: str = Field(alias="secondaryColor", default="")
    logo_url: Optional[str] = Field(None, alias="logoUrl")
    persona: str = ""
    name: str = ""
    menu_screenshot_base64: Optional[str] = Field(None, alias="menuScreenshotBase64")

    model_config = {"populate_by_name": True}


# ── Margin Analysis ──────────────────────────────────────────────────────


class MenuItem(BaseModel):
    item_name: str
    current_price: float
    category: str
    description: Optional[str] = None


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


# ── SEO Auditor ──────────────────────────────────────────────────────────


class Recommendation(BaseModel):
    severity: str
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


# ── Traffic Forecaster ───────────────────────────────────────────────────


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


# ── Competitive Analysis ─────────────────────────────────────────────────


class CompetitiveReport(BaseModel):
    market_summary: str = Field(alias="market_summary", default="")
    competitors: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    report_url: Optional[str] = Field(None, alias="reportUrl")

    model_config = {"populate_by_name": True}


# ── V1 API Envelope ──────────────────────────────────────────────────────


class V1Response(BaseModel, Generic[T]):
    success: bool = True
    data: T


# ── Web-specific types ────────────────────────────────────────────────────


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
    strategic_recommendations: list[dict] = Field(default_factory=list, alias="strategicRecommendations")
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


# ── Workflow Types ────────────────────────────────────────────────────────


class WorkflowPhase(str, Enum):
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    ANALYSIS = "analysis"
    EVALUATION = "evaluation"
    APPROVAL = "approval"
    OUTREACH = "outreach"
    COMPLETED = "completed"
    FAILED = "failed"


class BusinessPhase(str, Enum):
    PENDING = "pending"
    ENRICHING = "enriching"
    ANALYZING = "analyzing"
    ANALYSIS_DONE = "analysis_done"
    EVALUATING = "evaluating"
    EVALUATION_DONE = "evaluation_done"
    APPROVED = "approved"
    REJECTED = "rejected"
    OUTREACHING = "outreaching"
    OUTREACH_DONE = "outreach_done"
    OUTREACH_FAILED = "outreach_failed"


class EvaluationResult(BaseModel):
    score: float = 0
    isHallucinated: bool = False
    issues: list[str] = Field(default_factory=list)


class BusinessInsights(BaseModel):
    summary: str = ""
    keyFindings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generatedAt: str = ""


class BusinessWorkflowState(BaseModel):
    slug: str | None = None
    name: str | None = None
    address: str = ""
    officialUrl: str | None = None
    sourceZipCode: str | None = None
    businessType: str | None = None
    phase: BusinessPhase = BusinessPhase.PENDING
    capabilitiesCompleted: list[str] = Field(default_factory=list)
    capabilitiesFailed: list[str] = Field(default_factory=list)
    evaluations: dict[str, EvaluationResult] = Field(default_factory=dict)
    qualityPassed: bool = False
    enrichedProfile: dict[str, Any] | None = None
    insights: BusinessInsights | None = None
    outreachError: str | None = None
    lastError: str | None = None


class WorkflowProgress(BaseModel):
    totalBusinesses: int = 0
    qualificationQualified: int | None = None
    qualificationParked: int | None = None
    qualificationDisqualified: int | None = None
    analysisComplete: int = 0
    evaluationComplete: int = 0
    qualityPassed: int = 0
    qualityFailed: int = 0
    approved: int = 0
    outreachComplete: int = 0
    insightsComplete: int | None = None
    zipCodesScanned: int | None = None
    zipCodesTotal: int | None = None


class WorkflowDocument(BaseModel):
    id: str | None = None
    zipCode: str = ""
    businessType: str | None = None
    county: str | None = None
    zipCodes: list[str] | None = None
    resolvedFrom: Literal["single", "county"] | None = None
    phase: WorkflowPhase = WorkflowPhase.DISCOVERY
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    businesses: list[BusinessWorkflowState] = Field(default_factory=list)
    progress: WorkflowProgress = Field(default_factory=WorkflowProgress)
    lastError: str | None = None
    retryCount: int = 0


class ProgressEvent(BaseModel):
    type: str
    workflowId: str
    phase: WorkflowPhase
    message: str
    businessSlug: str | None = None
    progress: WorkflowProgress
    timestamp: str = ""


# ── Zip Code Research Types ───────────────────────────────────────────────


class ZipCodeReportSection(BaseModel):
    title: str = ""
    content: str = ""
    key_facts: list[str] = Field(default_factory=list)


class ZipCodeReportSections(BaseModel):
    geography: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    demographics: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    census_housing: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    business_landscape: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    economic_indicators: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    consumer_market: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    infrastructure: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    trending: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    events: ZipCodeReportSection | None = None
    seasonal_weather: ZipCodeReportSection | None = None


class ZipCodeReportSource(BaseModel):
    short_id: str = ""
    title: str = ""
    url: str = ""
    domain: str = ""


class ZipCodeReport(BaseModel):
    summary: str = ""
    zip_code: str = ""
    sections: ZipCodeReportSections = Field(default_factory=ZipCodeReportSections)
    source_count: int = 0
    sources: list[ZipCodeReportSource] = Field(default_factory=list)
    researched_at: str = ""


class TrendsTerm(BaseModel):
    term: str = ""
    rank: int = 0
    score: float = 0
    week: str = ""


class RisingTerm(BaseModel):
    term: str = ""
    percent_gain: float = 0
    rank: int = 0
    score: float = 0
    week: str = ""


class TrendsData(BaseModel):
    topTerms: list[TrendsTerm] = Field(default_factory=list)
    risingTerms: list[RisingTerm] = Field(default_factory=list)


class ZipCodeResearchDocument(BaseModel):
    id: str = ""
    zipCode: str = ""
    report: ZipCodeReport = Field(default_factory=ZipCodeReport)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class ZipCodeRunSummary(BaseModel):
    id: str = ""
    zipCode: str = ""
    sectionCount: int = 0
    summarySnippet: str = ""
    createdAt: datetime = Field(default_factory=datetime.utcnow)


# ── Area Research Types ───────────────────────────────────────────────────


class AreaResearchPhase(str, Enum):
    RESOLVING = "resolving"
    RESEARCHING = "researching"
    INDUSTRY_INTEL = "industry_intel"
    LOCAL_SECTOR_ANALYSIS = "local_sector_analysis"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class AreaResearchProgress(BaseModel):
    totalZipCodes: int = 0
    completedZipCodes: int = 0
    failedZipCodes: int = 0
    currentZipCode: str | None = None


class IndustryNewsItem(BaseModel):
    headline: str = ""
    summary: str = ""
    relevance: str = ""
    source: str | None = None


class PriceTrend(BaseModel):
    item: str = ""
    trend: Literal["rising", "stable", "declining"] = "stable"
    detail: str = ""


class RegulatoryUpdate(BaseModel):
    title: str = ""
    summary: str = ""
    impact: Literal["low", "medium", "high"] = "low"


class IndustryNewsData(BaseModel):
    recentNews: list[IndustryNewsItem] = Field(default_factory=list)
    priceTrends: list[PriceTrend] = Field(default_factory=list)
    regulatoryUpdates: list[RegulatoryUpdate] = Field(default_factory=list)


class FdaEnforcement(BaseModel):
    recalling_firm: str = ""
    reason_for_recall: str = ""
    classification: str = ""
    report_date: str = ""
    product_description: str = ""


class FdaData(BaseModel):
    enforcements: list[FdaEnforcement] = Field(default_factory=list)
    totalRecalls: int = 0
    recentRecallCount: int = 0
    topReasons: list[str] = Field(default_factory=list)


class BlsCpiDataPoint(BaseModel):
    year: int = 0
    month: int = 0
    period: str = ""
    indexValue: float = 0
    yoyPctChange: float | None = None


class BlsCpiSeries(BaseModel):
    seriesId: str = ""
    label: str = ""
    data: list[BlsCpiDataPoint] = Field(default_factory=list)


class BlsCpiData(BaseModel):
    series: list[BlsCpiSeries] = Field(default_factory=list)
    latestMonth: str = ""
    highlights: list[str] = Field(default_factory=list)


class UsdaCommodityPrice(BaseModel):
    commodity: str = ""
    year: int = 0
    period: str = ""
    value: float = 0
    unit: str = ""
    state: str = ""


class UsdaPriceData(BaseModel):
    commodities: list[UsdaCommodityPrice] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class IndustryIntelligence(BaseModel):
    industryAnalysis: dict[str, Any] | None = None
    industryNews: IndustryNewsData | None = None
    industryTrends: dict[str, Any] | None = None
    fdaData: FdaData | None = None
    blsCpiData: BlsCpiData | None = None
    usdaPriceData: UsdaPriceData | None = None
    localCatalysts: dict[str, Any] | None = None
    demographicData: dict[str, Any] | None = None


class LocalSectorInsights(BaseModel):
    trends: list[dict[str, Any]] = Field(default_factory=list)


class MarketOpportunity(BaseModel):
    score: float = 0
    narrative: str = ""
    keyFactors: list[str] = Field(default_factory=list)


class DemographicFit(BaseModel):
    score: float = 0
    narrative: str = ""
    keyMetrics: dict[str, Any] = Field(default_factory=dict)


class CompetitiveLandscape(BaseModel):
    score: float = 0
    narrative: str = ""
    existingBusinessCount: int = 0
    saturationLevel: Literal["low", "moderate", "high", "saturated"] = "low"
    gaps: list[str] = Field(default_factory=list)


class TrendingInsights(BaseModel):
    narrative: str = ""
    risingSearches: list[str] = Field(default_factory=list)
    decliningSearches: list[str] = Field(default_factory=list)
    seasonalPatterns: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    category: str = ""
    severity: Literal["low", "medium", "high"] = "low"
    description: str = ""


class ZipCodeRecommendation(BaseModel):
    zipCode: str = ""
    reason: str = ""
    score: float = 0


class AvoidZipCode(BaseModel):
    zipCode: str = ""
    reason: str = ""


class AreaResearchSummary(BaseModel):
    marketOpportunity: MarketOpportunity = Field(default_factory=MarketOpportunity)
    demographicFit: DemographicFit = Field(default_factory=DemographicFit)
    competitiveLandscape: CompetitiveLandscape = Field(default_factory=CompetitiveLandscape)
    trendingInsights: TrendingInsights = Field(default_factory=TrendingInsights)
    industryIntelligence: dict[str, Any] | None = None
    eventImpact: dict[str, Any] | None = None
    seasonalPatterns: dict[str, Any] | None = None
    regulatoryAndSafety: dict[str, Any] | None = None
    pricingEnvironment: dict[str, Any] | None = None
    risks: dict[str, Any] = Field(default_factory=lambda: {"items": []})
    recommendations: dict[str, Any] = Field(default_factory=lambda: {"topZipCodes": [], "actionItems": [], "avoidZipCodes": []})
    generatedAt: str = ""


class AreaResearchDocument(BaseModel):
    id: str = ""
    area: str = ""
    businessType: str = ""
    areaKey: str | None = None
    resolvedCountyName: str | None = None
    resolvedState: str | None = None
    zipCodes: list[str] = Field(default_factory=list)
    completedZipCodes: list[str] = Field(default_factory=list)
    failedZipCodes: list[str] = Field(default_factory=list)
    phase: AreaResearchPhase = AreaResearchPhase.RESOLVING
    summary: AreaResearchSummary | None = None
    industryIntel: IndustryIntelligence | None = None
    localSectorInsights: LocalSectorInsights | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    lastError: str | None = None


class AreaResearchProgressEvent(BaseModel):
    type: str = ""
    areaId: str = ""
    phase: AreaResearchPhase = AreaResearchPhase.RESOLVING
    message: str = ""
    progress: AreaResearchProgress = Field(default_factory=AreaResearchProgress)
    timestamp: str = ""


# ── Sector Research Types ─────────────────────────────────────────────────


class SectorResearchPhase(str, Enum):
    ANALYZING = "analyzing"
    LOCAL_TRENDS = "local_trends"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class SectorResearchProgress(BaseModel):
    phase: SectorResearchPhase = SectorResearchPhase.ANALYZING
    zipCodesAnalyzed: int = 0
    totalZipCodes: int = 0


class IndustryAnalysis(BaseModel):
    overview: str = ""
    marketSize: str = ""
    growthRate: str = ""
    challenges: list[dict[str, Any]] = Field(default_factory=list)
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    trends: list[dict[str, Any]] = Field(default_factory=list)
    consumerBehavior: list[dict[str, Any]] = Field(default_factory=list)
    technologyAdoption: list[dict[str, Any]] = Field(default_factory=list)
    regulatoryEnvironment: str = ""
    benchmarks: dict[str, Any] = Field(default_factory=dict)


class SectorSynthesis(BaseModel):
    narrative: str = ""
    sectorHealthScore: float = 0
    localFitScore: float = 0
    topInsights: list[str] = Field(default_factory=list)
    strategicRecommendations: list[str] = Field(default_factory=list)


class SectorResearchSummary(BaseModel):
    industryAnalysis: IndustryAnalysis = Field(default_factory=IndustryAnalysis)
    localTrends: list[dict[str, Any]] = Field(default_factory=list)
    synthesis: SectorSynthesis = Field(default_factory=SectorSynthesis)
    generatedAt: str = ""


class SectorResearchDocument(BaseModel):
    id: str = ""
    sector: str = ""
    zipCodes: list[str] = Field(default_factory=list)
    areaName: str | None = None
    phase: SectorResearchPhase = SectorResearchPhase.ANALYZING
    summary: SectorResearchSummary | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    lastError: str | None = None


# ── Content Types ─────────────────────────────────────────────────────────


class ContentType(str, Enum):
    SOCIAL = "social"
    BLOG = "blog"


class ContentPlatform(str, Enum):
    X = "x"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    BLOG = "blog"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    FAILED = "failed"


class ContentSourceType(str, Enum):
    ZIPCODE_RESEARCH = "zipcode_research"
    AREA_RESEARCH = "area_research"
    COMBINED_CONTEXT = "combined_context"


class ContentPost(BaseModel):
    id: str = ""
    type: ContentType = ContentType.SOCIAL
    platform: ContentPlatform = ContentPlatform.X
    status: ContentStatus = ContentStatus.DRAFT
    sourceType: ContentSourceType = ContentSourceType.ZIPCODE_RESEARCH
    sourceId: str = ""
    sourceLabel: str = ""
    content: str = ""
    title: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    publishedAt: datetime | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    platformPostId: str | None = None
    error: str | None = None


# ── Misc Types ────────────────────────────────────────────────────────────


class CombinedContextData(BaseModel):
    summary: str = ""
    keySignals: list[str] = Field(default_factory=list)
    demographicHighlights: list[str] = Field(default_factory=list)
    marketGaps: list[str] = Field(default_factory=list)
    trendingTerms: list[str] = Field(default_factory=list)


class CombinedContext(BaseModel):
    id: str = ""
    sourceRunIds: list[str] = Field(default_factory=list)
    sourceZipCodes: list[str] = Field(default_factory=list)
    context: CombinedContextData = Field(default_factory=CombinedContextData)
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class CapabilityDefinition(BaseModel):
    name: str
    displayName: str
    apiVersion: Literal["capabilities", "v1"]
    endpointSlug: str
    firestoreOutputKey: str
    enabled: bool = True


class DiscoveredBusiness(BaseModel):
    name: str
    address: str = ""
    category: str = ""
    website: str = ""
    docId: str = ""


class FixtureType(str, Enum):
    GROUNDING = "grounding"
    FAILURE_CASE = "failure_case"


class FixtureIdentity(BaseModel):
    name: str = ""
    address: str = ""
    email: str | None = None
    socialLinks: dict[str, str] | None = None
    docId: str = ""


class TestFixture(BaseModel):
    id: str = ""
    fixtureType: FixtureType = FixtureType.GROUNDING
    sourceWorkflowId: str = ""
    sourceZipCode: str | None = None
    businessType: str | None = None
    savedAt: datetime = Field(default_factory=datetime.utcnow)
    notes: str | None = None
    businessState: BusinessWorkflowState | None = None
    identity: FixtureIdentity = Field(default_factory=FixtureIdentity)
    latestOutputs: dict[str, Any] = Field(default_factory=dict)
