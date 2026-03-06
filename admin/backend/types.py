"""All Pydantic v2 models for the hephae-admin backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Workflow Types ──────────────────────────────────────────────────────────

class WorkflowPhase(str, Enum):
    DISCOVERY = "discovery"
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
    slug: str
    name: str
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
    id: str = ""
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


# ── Zip Code Research Types ─────────────────────────────────────────────────

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


# ── Area Research Types ─────────────────────────────────────────────────────

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
    """BLS Consumer Price Index data for food categories."""
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
    """USDA NASS agricultural commodity price data."""
    commodities: list[UsdaCommodityPrice] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class IndustryIntelligence(BaseModel):
    industryAnalysis: dict[str, Any] | None = None
    industryNews: IndustryNewsData | None = None
    industryTrends: dict[str, Any] | None = None
    fdaData: FdaData | None = None
    blsCpiData: BlsCpiData | None = None
    usdaPriceData: UsdaPriceData | None = None


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


# ── Sector Research Types ───────────────────────────────────────────────────

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


class IndustryChallenge(BaseModel):
    title: str = ""
    description: str = ""
    severity: Literal["low", "medium", "high"] = "low"


class IndustryOpportunity(BaseModel):
    title: str = ""
    description: str = ""
    timeframe: Literal["immediate", "short_term", "long_term"] = "short_term"


class IndustryTrend(BaseModel):
    name: str = ""
    direction: Literal["rising", "stable", "declining"] = "stable"
    description: str = ""


class ConsumerBehaviorShift(BaseModel):
    shift: str = ""
    impact: str = ""


class TechAdoption(BaseModel):
    technology: str = ""
    adoptionLevel: Literal["early", "growing", "mainstream"] = "growing"
    relevance: str = ""


class IndustryAnalysis(BaseModel):
    overview: str = ""
    marketSize: str = ""
    growthRate: str = ""
    challenges: list[IndustryChallenge] = Field(default_factory=list)
    opportunities: list[IndustryOpportunity] = Field(default_factory=list)
    trends: list[IndustryTrend] = Field(default_factory=list)
    consumerBehavior: list[ConsumerBehaviorShift] = Field(default_factory=list)
    technologyAdoption: list[TechAdoption] = Field(default_factory=list)
    regulatoryEnvironment: str = ""
    benchmarks: dict[str, Any] = Field(default_factory=dict)


class LocalSectorTrendItem(BaseModel):
    term: str = ""
    direction: Literal["rising", "declining"] = "rising"
    insight: str = ""


class LocalSectorTrends(BaseModel):
    zipCode: str = ""
    relevantTrends: list[LocalSectorTrendItem] = Field(default_factory=list)
    sectorDemandSignals: list[str] = Field(default_factory=list)
    competitorDensity: str = ""
    localOpportunities: list[str] = Field(default_factory=list)


class SectorSynthesis(BaseModel):
    narrative: str = ""
    sectorHealthScore: float = 0
    localFitScore: float = 0
    topInsights: list[str] = Field(default_factory=list)
    strategicRecommendations: list[str] = Field(default_factory=list)


class SectorResearchSummary(BaseModel):
    industryAnalysis: IndustryAnalysis = Field(default_factory=IndustryAnalysis)
    localTrends: list[LocalSectorTrends] = Field(default_factory=list)
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


# ── Combined Context Types ──────────────────────────────────────────────────

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


# ── Fixture Types ───────────────────────────────────────────────────────────

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


# ── Capability Types ────────────────────────────────────────────────────────

class CapabilityDefinition(BaseModel):
    name: str
    displayName: str
    apiVersion: Literal["capabilities", "v1"]
    endpointSlug: str
    firestoreOutputKey: str
    enabled: bool = True


# ── Scanner / Discovery Types ───────────────────────────────────────────────

class DiscoveredBusiness(BaseModel):
    name: str
    address: str = ""
    category: str = ""
    website: str = ""
    docId: str = ""


class CountyResolverOutput(BaseModel):
    zipCodes: list[str] = Field(default_factory=list)
    countyName: str = ""
    state: str = ""
    error: str | None = None


# ── Enrichment Types ────────────────────────────────────────────────────────

class EnrichedProfile(BaseModel):
    name: str = ""
    address: str = ""
    phone: str | None = None
    email: str | None = None
    officialUrl: str | None = None
    hours: dict[str, Any] | None = None
    social: dict[str, str] | None = None
    competitors: list[dict[str, Any]] | None = None
    news: list[dict[str, Any]] | None = None
    colors: dict[str, Any] | None = None
    logos: list[str] | None = None
    menu: dict[str, Any] | None = None
    coordinates: dict[str, float] | None = None
    validationReport: dict[str, Any] | None = None


# ── Content Types ──────────────────────────────────────────────────────────

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
