"""Pydantic models for agent outputs — used with ADK native structured outputs.

These models define the expected JSON output schema for each agent when using
ADK's response_schema parameter. They replace manual markdown-stripping and
JSON parsing with native Gemini structured output validation.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Discovery Agents ──────────────────────────────────────────────────────


class DiscoveredBusinessItem(BaseModel):
    """A single business discovered via Google Search or OSM."""

    name: str
    address: str = ""
    website: str = ""
    category: str = ""


class ZipcodeScannerOutput(BaseModel):
    """Output from ZipcodeScannerAgent (Google Search grounding)."""

    businesses: list[DiscoveredBusinessItem] = Field(default_factory=list)


class CountyResolverOutput(BaseModel):
    """Output from CountyResolverAgent (maps county to zip codes)."""

    zipCodes: list[str] = Field(default_factory=list)
    countyName: str = ""
    state: str = ""
    error: Optional[str] = None


# ── Research Agents ───────────────────────────────────────────────────────


class IndustryChallenge(BaseModel):
    """A challenge faced by businesses in an industry sector."""

    title: str
    description: str
    severity: Literal["low", "medium", "high"]


class IndustryOpportunity(BaseModel):
    """An opportunity for a new or existing business in a sector."""

    title: str
    description: str
    timeframe: Literal["immediate", "short_term", "long_term"]


class IndustryTrend(BaseModel):
    """A trend affecting an industry sector."""

    name: str
    direction: Literal["rising", "stable", "declining"]
    description: str


class ConsumerBehaviorShift(BaseModel):
    """A shift in consumer behavior affecting a sector."""

    shift: str
    impact: str


class TechnologyAdoptionItem(BaseModel):
    """Technology adoption levels in an industry."""

    technology: str
    adoptionLevel: Literal["early", "growing", "mainstream"]
    relevance: str


class IndustryBenchmarks(BaseModel):
    """Financial and operational benchmarks for an industry."""

    gross_margin_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None
    avg_ticket_size: Optional[float] = None
    labor_cost_pct: Optional[float] = None
    rent_pct_revenue: Optional[float] = None
    failure_rate_1yr: Optional[float] = None
    failure_rate_5yr: Optional[float] = None
    avg_startup_cost: Optional[float] = None


class IndustryAnalystOutput(BaseModel):
    """Output from IndustryAnalystAgent (deep sector analysis)."""

    overview: str
    marketSize: str
    growthRate: str
    challenges: list[IndustryChallenge] = Field(default_factory=list)
    opportunities: list[IndustryOpportunity] = Field(default_factory=list)
    trends: list[IndustryTrend] = Field(default_factory=list)
    consumerBehavior: list[ConsumerBehaviorShift] = Field(default_factory=list)
    technologyAdoption: list[TechnologyAdoptionItem] = Field(default_factory=list)
    regulatoryEnvironment: str
    benchmarks: IndustryBenchmarks = Field(default_factory=IndustryBenchmarks)


class NewsItem(BaseModel):
    """A news item relevant to an industry."""

    headline: str
    summary: str
    relevance: str
    source: Optional[str] = None


class PriceTrend(BaseModel):
    """A commodity or input price trend."""

    item: str
    trend: Literal["rising", "stable", "declining"]
    detail: str


class RegulatoryUpdate(BaseModel):
    """A regulatory change affecting an industry."""

    title: str
    summary: str
    impact: Literal["low", "medium", "high"]


class IndustryNewsOutput(BaseModel):
    """Output from IndustryNewsAgent (research recent news)."""

    recentNews: list[NewsItem] = Field(default_factory=list)
    priceTrends: list[PriceTrend] = Field(default_factory=list)
    regulatoryUpdates: list[RegulatoryUpdate] = Field(default_factory=list)


class MarketOpportunity(BaseModel):
    """Market opportunity assessment."""

    score: float
    narrative: str
    keyFactors: list[str] = Field(default_factory=list)


class KeyMetric(BaseModel):
    """A key demographic metric (name-value pair)."""

    name: str
    value: str = ""


class DemographicFit(BaseModel):
    """Demographic fit assessment."""

    score: float
    narrative: str
    keyMetrics: list[KeyMetric] = Field(default_factory=list)


class CompetitiveLandscape(BaseModel):
    """Competitive landscape assessment."""

    score: float
    narrative: str
    existingBusinessCount: int = 0
    saturationLevel: Literal["low", "moderate", "high", "saturated"]
    gaps: list[str] = Field(default_factory=list)


class TrendingInsights(BaseModel):
    """Insights on trending search terms and seasonal patterns."""

    narrative: str
    risingSearches: list[str] = Field(default_factory=list)
    decliningSearches: list[str] = Field(default_factory=list)
    seasonalPatterns: list[str] = Field(default_factory=list)


class RiskItem(BaseModel):
    """A risk to a business type in an area."""

    category: str
    severity: Literal["low", "medium", "high"]
    description: str


class RiskAssessment(BaseModel):
    """Risk assessment for an area."""

    items: list[RiskItem] = Field(default_factory=list)


class ZipCodeRecommendation(BaseModel):
    """A recommended zip code."""

    zipCode: str
    reason: str
    score: float


class AvoidZipCode(BaseModel):
    """A zip code to avoid."""

    zipCode: str
    reason: str


class Recommendations(BaseModel):
    """Recommendations for action."""

    topZipCodes: list[ZipCodeRecommendation] = Field(default_factory=list)
    actionItems: list[str] = Field(default_factory=list)
    avoidZipCodes: list[AvoidZipCode] = Field(default_factory=list)


class AreaSummaryOutput(BaseModel):
    """Output from AreaSummaryAgent (area-level synthesis)."""

    marketOpportunity: MarketOpportunity = Field(default_factory=MarketOpportunity)
    demographicFit: DemographicFit = Field(default_factory=DemographicFit)
    competitiveLandscape: CompetitiveLandscape = Field(
        default_factory=CompetitiveLandscape
    )
    trendingInsights: TrendingInsights = Field(default_factory=TrendingInsights)
    risks: RiskAssessment = Field(default_factory=RiskAssessment)
    recommendations: Recommendations = Field(default_factory=Recommendations)
    generatedAt: str = ""


class ContextCombinerOutput(BaseModel):
    """Output from ContextCombinerAgent (synthesize multiple zip reports)."""

    summary: str
    keySignals: list[str] = Field(default_factory=list)
    demographicHighlights: list[str] = Field(default_factory=list)
    marketGaps: list[str] = Field(default_factory=list)
    trendingTerms: list[str] = Field(default_factory=list)


class ZipCodeReportSection(BaseModel):
    """A section in a zip code report."""

    title: str = ""
    content: str = ""
    key_facts: list[str] = Field(default_factory=list)


class ZipcodeReportSections(BaseModel):
    """All sections in a zip code report."""

    geography: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    demographics: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    census_housing: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    business_landscape: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    economic_indicators: ZipCodeReportSection = Field(
        default_factory=ZipCodeReportSection
    )
    consumer_market: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    infrastructure: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    trending: ZipCodeReportSection = Field(default_factory=ZipCodeReportSection)
    events: Optional[ZipCodeReportSection] = None
    seasonal_weather: Optional[ZipCodeReportSection] = None


class ZipcodeReportComposerOutput(BaseModel):
    """Output from ZipcodeReportComposerAgent (compose structured report)."""

    summary: str
    zip_code: str
    sections: ZipcodeReportSections = Field(default_factory=ZipcodeReportSections)
    source_count: int = 0
    researched_at: str = ""


# ── Insight Agents ────────────────────────────────────────────────────────


class InsightsOutput(BaseModel):
    """Output from InsightsAgent (cross-capability synthesis)."""

    summary: str
    keyFindings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generatedAt: str = ""


# ── Capability Runner Outputs ─────────────────────────────────────────────


class TrafficSlot(BaseModel):
    """A single time-slot forecast entry."""

    label: str
    score: int = 0
    level: str = "Low"
    reason: str = ""


class ForecastDay(BaseModel):
    """One day of traffic forecast."""

    date: str
    dayOfWeek: str = ""
    localEvents: list[str] = Field(default_factory=list)
    weatherNote: str = ""
    slots: list[TrafficSlot] = Field(default_factory=list)


class NearbyPOI(BaseModel):
    """A nearby point of interest."""

    name: str
    lat: float = 0
    lng: float = 0
    type: str = ""


class Coordinates(BaseModel):
    """Latitude/longitude pair."""

    lat: float = 0.0
    lng: float = 0.0


class ForecastBusiness(BaseModel):
    """Business info embedded in traffic forecast."""

    name: str
    address: str = ""
    coordinates: Coordinates = Field(default_factory=Coordinates)
    type: str = ""
    nearbyPOIs: list[NearbyPOI] = Field(default_factory=list)


class TrafficForecastOutput(BaseModel):
    """Output from ForecasterAgent (3-day foot traffic forecast)."""

    business: ForecastBusiness
    summary: str = ""
    forecast: list[ForecastDay] = Field(default_factory=list)


class CompetitorEntry(BaseModel):
    """A single competitor analysis entry."""

    name: str
    key_strength: str = ""
    key_weakness: str = ""
    threat_level: int = 5


class SourceRef(BaseModel):
    """A source reference with URL and title."""

    url: str = ""
    title: str = ""


class CompetitiveAnalysisOutput(BaseModel):
    """Output from MarketPositioningAgent (competitive strategy JSON)."""

    market_summary: str = ""
    competitor_analysis: list[CompetitorEntry] = Field(default_factory=list)
    strategic_advantages: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


# ── Social Media Auditor ─────────────────────────────────────────────────


class SocialPlatformAudit(BaseModel):
    """Audit of a single social media platform."""

    name: str
    url: Optional[str] = None
    handle: Optional[str] = None
    score: int = 0
    followers: str = "Unknown"
    posting_frequency: str = "unknown"
    content_themes: list[str] = Field(default_factory=list)
    engagement: str = "unknown"
    last_post_recency: str = "Unknown"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class CompetitorBenchmark(BaseModel):
    """Social media benchmark for a competitor."""

    name: str
    strongest_platform: str = ""
    followers: str = "Unknown"
    posting_frequency: str = "unknown"
    key_advantage: str = ""


class StrategicRecommendation(BaseModel):
    """A prioritized social media recommendation."""

    priority: int = 3
    action: str
    impact: str = "medium"
    effort: str = "medium"
    rationale: str = ""


class ContentStrategy(BaseModel):
    """Content strategy summary."""

    content_pillars: list[str] = Field(default_factory=list)
    hashtag_strategy: list[str] = Field(default_factory=list)
    posting_schedule: str = ""
    quick_wins: list[str] = Field(default_factory=list)


class SocialMediaAuditOutput(BaseModel):
    """Output from SocialStrategistAgent (comprehensive social media audit)."""

    overall_score: int = 0
    summary: str = ""
    platforms: list[SocialPlatformAudit] = Field(default_factory=list)
    competitor_benchmarks: list[CompetitorBenchmark] = Field(default_factory=list)
    strategic_recommendations: list[StrategicRecommendation] = Field(default_factory=list)
    content_strategy: ContentStrategy = Field(default_factory=ContentStrategy)
    sources: list[SourceRef] = Field(default_factory=list)


class SeoMethodology(BaseModel):
    """Methodology details for an SEO section audit."""

    reasoningSteps: list[str] = Field(default_factory=list)
    toolsUsed: list[str] = Field(default_factory=list)
    searchQueries: list[str] = Field(default_factory=list)
    sourcesUsed: list[SourceRef] = Field(default_factory=list)


class SeoRecommendation(BaseModel):
    """A single SEO recommendation."""

    title: str = ""
    description: str = ""
    priority: str = ""
    impact: str = ""


class SeoSection(BaseModel):
    """A single section of the SEO audit report."""

    id: str
    title: str
    score: int = 0
    description: str = ""
    recommendations: list[SeoRecommendation] = Field(default_factory=list)
    methodology: SeoMethodology = Field(default_factory=SeoMethodology)


class SeoAuditorOutput(BaseModel):
    """Output from SeoAuditorAgent (comprehensive SEO audit)."""

    overallScore: int = 0
    summary: str = ""
    sections: list[SeoSection] = Field(default_factory=list)


# ── Margin Analyzer Agents ────────────────────────────────────────────────


class ParsedMenuItem(BaseModel):
    """A single menu item extracted from a menu screenshot."""

    item_name: str
    current_price: float = 0.0
    category: str = ""
    description: str = ""


class MenuIntakeOutput(BaseModel):
    """Output from VisionIntakeAgent (menu item extraction)."""

    items: list[ParsedMenuItem] = Field(default_factory=list)


class CompetitorBenchmarkEntry(BaseModel):
    """A competitor price benchmark for a menu item."""

    competitor_name: str
    item_match: str = ""
    price: float = 0.0
    source_url: str = ""
    distance_miles: float = 0.0


class MacroeconomicContext(BaseModel):
    """Macroeconomic context from BLS/FRED data."""

    inflation_cpi: str = ""
    unemployment_trend: str = ""
    analysis_hint: str = ""


class BenchmarkOutput(BaseModel):
    """Output from BenchmarkerAgent (competitor price benchmarks)."""

    competitors: list[CompetitorBenchmarkEntry] = Field(default_factory=list)
    macroeconomic_context: MacroeconomicContext = Field(default_factory=MacroeconomicContext)


class CommodityTrend(BaseModel):
    """A single commodity inflation trend."""

    ingredient: str
    inflation_rate_12mo: float = 0.0
    trend_description: str = ""


class CommodityOutput(BaseModel):
    """Output from CommodityWatchdogAgent (commodity price trends)."""

    trends: list[CommodityTrend] = Field(default_factory=list)


class SurgeryItem(BaseModel):
    """A single menu item after margin surgery analysis."""

    item_name: str = ""
    current_price: float = 0.0
    optimal_price: float = 0.0
    price_leakage: float = 0.0
    revenue_leakage: float = 0.0
    category: str = ""


class SurgeryReportOutput(BaseModel):
    """Output from SurgeonAgent (margin surgery results)."""

    items: list[SurgeryItem] = Field(default_factory=list)


class AdvisorRecommendation(BaseModel):
    """A strategic pricing recommendation."""

    title: str
    description: str
    impact: str = ""


class AdvisorOutput(BaseModel):
    """Output from AdvisorAgent (strategic pricing advice)."""

    recommendations: list[AdvisorRecommendation] = Field(default_factory=list)


# ── Discovery Agents (detailed schemas) ────────────────────────────────────


class SiteIdentity(BaseModel):
    """Identity information extracted from a crawled website."""

    name: str = ""
    address: str = ""
    phone: str = ""
    type: str = ""
    description: str = ""


class EntityMatchOutput(BaseModel):
    """Output from EntityMatcherAgent (site identity verification)."""

    status: str = "MATCH"
    siteIdentity: SiteIdentity = Field(default_factory=SiteIdentity)
    confidence: float = 0.0
    reason: str = ""


class ThemeOutput(BaseModel):
    """Output from ThemeAgent (site visual identity)."""

    logoUrl: Optional[str] = None
    favicon: Optional[str] = None
    primaryColor: str = ""
    secondaryColor: str = ""
    persona: str = ""


class ContactOutput(BaseModel):
    """Output from ContactAgent (business contact info)."""

    phone: str = ""
    email: str = ""
    emailStatus: str = "not_found"
    hours: str = ""
    contactFormUrl: str = ""
    contactFormStatus: str = "not_found"


class SocialMediaDiscoveryOutput(BaseModel):
    """Output from SocialMediaAgent (social link discovery)."""

    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    tiktok: Optional[str] = None
    yelp: Optional[str] = None
    grubhub: Optional[str] = None
    doordash: Optional[str] = None
    ubereats: Optional[str] = None
    seamless: Optional[str] = None
    toasttab: Optional[str] = None


class MenuDiscoveryOutput(BaseModel):
    """Output from MenuAgent (menu URL discovery)."""

    menuUrl: Optional[str] = None
    grubhub: Optional[str] = None
    doordash: Optional[str] = None
    ubereats: Optional[str] = None
    seamless: Optional[str] = None
    toasttab: Optional[str] = None


class DiscoveredCompetitor(BaseModel):
    """A single competitor found during discovery."""

    name: str
    url: str = ""
    reason: str = ""


class CompetitorDiscoveryOutput(BaseModel):
    """Output from CompetitorAgent (local competitor discovery)."""

    competitors: list[DiscoveredCompetitor] = Field(default_factory=list)


class DiscoveryNewsItem(BaseModel):
    """A news article found during discovery."""

    title: str
    url: str = ""
    source: str = ""
    date: Optional[str] = None
    snippet: str = ""


class NewsDiscoveryOutput(BaseModel):
    """Output from NewsAgent (recent business news)."""

    articles: list[DiscoveryNewsItem] = Field(default_factory=list)


class BusinessOverviewOutput(BaseModel):
    """Output from BusinessOverviewAgent (AI-generated overview)."""

    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    business_type: Optional[str] = None
    price_range: Optional[str] = None
    established: Optional[str] = None
    notable_mentions: list[str] = Field(default_factory=list)
    reputation_signals: str = "unknown"
    sources: list[SourceRef] = Field(default_factory=list)


class ComplaintItem(BaseModel):
    """A customer complaint or operational issue."""

    issue: str
    severity: str = "medium"
    source: str = ""
    sourceUrl: str = ""


class ChallengesOutput(BaseModel):
    """Output from ChallengesAgent (business risk/complaints research)."""

    customer_complaints: list[ComplaintItem] = Field(default_factory=list)
    operational_issues: list[ComplaintItem] = Field(default_factory=list)
    regulatory_flags: list[ComplaintItem] = Field(default_factory=list)
    reputation_risks: list[ComplaintItem] = Field(default_factory=list)
    competitive_weaknesses: list[ComplaintItem] = Field(default_factory=list)
    overall_risk_level: str = "low"
    summary: str = ""


class SocialPlatformMetrics(BaseModel):
    """Metrics for a single social platform from profiler."""

    url: str = ""
    username: str = ""
    followerCount: int = 0
    postCount: int = 0
    bio: str = ""
    isVerified: bool = False
    lastPostRecency: str = ""
    engagementIndicator: str = ""
    error: Optional[str] = None


class YelpMetrics(BaseModel):
    """Yelp-specific metrics."""

    url: str = ""
    rating: float = 0.0
    reviewCount: int = 0
    priceRange: str = ""
    categories: list[str] = Field(default_factory=list)
    claimedByOwner: bool = False
    error: Optional[str] = None


class SocialProfileSummary(BaseModel):
    """Summary of social media presence."""

    totalFollowers: int = 0
    strongestPlatform: str = ""
    weakestPlatform: str = ""
    overallPresenceScore: int = 0
    postingFrequency: str = ""
    recommendation: str = ""


class SocialProfilerOutput(BaseModel):
    """Output from SocialProfilerAgent (detailed social metrics)."""

    instagram: Optional[SocialPlatformMetrics] = None
    facebook: Optional[SocialPlatformMetrics] = None
    twitter: Optional[SocialPlatformMetrics] = None
    tiktok: Optional[SocialPlatformMetrics] = None
    yelp: Optional[YelpMetrics] = None
    summary: SocialProfileSummary = Field(default_factory=SocialProfileSummary)


class ValidationReport(BaseModel):
    """URL validation report from discovery reviewer."""

    totalUrlsChecked: int = 0
    valid: int = 0
    invalid: int = 0
    unverifiable: int = 0
    corrected: int = 0
    flags: list[str] = Field(default_factory=list)


class ReviewedDataOutput(BaseModel):
    """Output from DiscoveryReviewerAgent (validated discovery data)."""

    validatedSocialData: SocialMediaDiscoveryOutput = Field(default_factory=SocialMediaDiscoveryOutput)
    validatedMenuUrl: Optional[str] = None
    validatedCompetitors: list[DiscoveredCompetitor] = Field(default_factory=list)
    validatedNews: list[DiscoveryNewsItem] = Field(default_factory=list)
    validatedMapsUrl: Optional[str] = None
    validationReport: ValidationReport = Field(default_factory=ValidationReport)


# ── Content Generation Agents ───────────────────────────────────────────


class InstagramPostOutput(BaseModel):
    """Output from InstagramPostAgent."""

    caption: str = ""
    reportLink: str = ""
    imageUrl: str = ""


class FacebookPostOutput(BaseModel):
    """Output from FacebookPostAgent."""

    post: str = ""
    reportLink: str = ""
    imageUrl: str = ""


class TwitterPostOutput(BaseModel):
    """Output from TwitterPostAgent."""

    tweet: str = ""
    reportLink: str = ""
    imageUrl: str = ""


class EmailOutreachOutput(BaseModel):
    """Output from EmailOutreachAgent."""

    subject: str = ""
    body: str = ""


class ContactFormOutput(BaseModel):
    """Output from ContactFormAgent."""

    message: str = ""


class BlogResearchOutput(BaseModel):
    """Output from ResearchCompilerAgent (blog research brief)."""

    key_findings: list[str] = Field(default_factory=list)
    data_points: list[str] = Field(default_factory=list)
    narrative_angles: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


# ── Evaluator Agents ────────────────────────────────────────────────────


class EvaluationOutput(BaseModel):
    """Output from evaluator agents (score + hallucination check)."""

    score: int = 0
    isHallucinated: bool = False
    issues: list[str] = Field(default_factory=list)
