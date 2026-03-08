"""Pydantic models for agent outputs — used with ADK native structured outputs.

These models define the expected JSON output schema for each agent when using
ADK's response_schema parameter. They replace manual markdown-stripping and
JSON parsing with native Gemini structured output validation.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

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


class DemographicFit(BaseModel):
    """Demographic fit assessment."""

    score: float
    narrative: str
    keyMetrics: dict[str, Any] = Field(default_factory=dict)


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
