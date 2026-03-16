# Agent Catalog
> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

---

## 1. Model Tiers

| Tier | Constant | Model ID | Use Case |
|------|----------|----------|----------|
| PRIMARY | `AgentModels.PRIMARY_MODEL` | `gemini-3.1-flash-lite-preview` | All standard agents |
| FALLBACK | `AgentModels.FALLBACK_MODEL` | `gemini-3-flash-preview` | Auto-fallback on 429/503/529 |
| CREATIVE_VISION | `AgentModels.CREATIVE_VISION_MODEL` | `gemini-3.1-flash-image-preview` | Image generation |

**Thinking Presets** (via `ThinkingPresets`):

| Preset | Configuration | Used By |
|--------|---------------|---------|
| MEDIUM | `thinking_level="MEDIUM"` | All evaluator agents |
| HIGH | `thinking_level="HIGH"` | CompetitorAgent, MarketPositioningAgent, SocialStrategistAgent |
| DEEP | `thinking_budget=8192` | SEO Auditor, BlogWriterAgent, IndustryAnalystAgent, AreaSummaryAgent, EnhancedAreaSummaryAgent |

**File:** `lib/common/hephae_common/model_config.py`

---

## 2. Agent Versions

Source: `apps/api/hephae_api/config.py` (`AgentVersions` class)

### Discovery Pipeline

| Agent | Version | Notes |
|-------|---------|-------|
| DISCOVERY_PIPELINE | 5.1.0 | MINOR: parallel local context fetch, enhanced MenuAgent delivery search |
| SITE_CRAWLER | 1.1.0 | |
| CONTACT_DISCOVERY | 1.0.0 | |
| CONTACT_AGENT | 2.0.0 | MAJOR: added emailStatus, contactFormUrl, contactFormStatus fields |
| QUALITY_GATE_AGENT | 1.0.1 | PATCH: added banks and dollar stores to exclusion examples |
| MENU_DISCOVERY | 3.0.0 | MAJOR: searches delivery platforms (DoorDash/Grubhub/UberEats) when no menu found |
| SOCIAL_DISCOVERY | 2.0.0 | |
| SOCIAL_PROFILER | 2.0.0 | |
| MAPS_DISCOVERY | 2.0.0 | |
| COMPETITOR_DISCOVERY | 2.0.0 | |
| THEME_DISCOVERY | 2.0.0 | |
| BUSINESS_OVERVIEW | 1.0.0 | |
| NEWS_DISCOVERY | 1.0.0 | |
| DISCOVERY_REVIEWER | 1.0.0 | |

### Capability Agents

| Agent | Version | Notes |
|-------|---------|-------|
| SEO_AUDITOR | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |
| TRAFFIC_FORECASTER | 1.0.0 | |
| COMPETITIVE_ANALYZER | 1.0.0 | |
| MARGIN_SURGEON | 1.1.0 | MINOR: PDF extraction, menuNotFound flow, pre-discovered delivery URLs |
| SOCIAL_MEDIA_AUDITOR | 1.0.0 | |

### Marketing / Social

| Agent | Version | Notes |
|-------|---------|-------|
| MARKETING_SWARM | 1.0.0 | |
| SOCIAL_POST_GENERATOR | 3.0.0 | MAJOR: CDN report links + social card images, reports via cdn.hephae.co |
| BLOG_WRITER | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |

### Research

| Agent | Version | Notes |
|-------|---------|-------|
| LOCAL_CATALYST | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |
| DEMOGRAPHIC_EXPERT | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |

### Qualification / Review

| Agent | Version | Notes |
|-------|---------|-------|
| QUALIFICATION_SCANNER | 1.0.0 | |

---

## 3. Discovery Agents

All discovery agents live in `agents/hephae_agents/discovery/agent.py`.

### DiscoveryPipeline (SequentialAgent)

The top-level orchestrator. Runs Phase 1 then Phase 2 sequentially.

**Sub-agents:** `DiscoveryPhase1` -> `DiscoveryPhase2`

---

### Phase 1: Crawl + Entity Validation

#### SiteCrawlerAgent
| | |
|---|---|
| **Name** | `SiteCrawlerAgent` |
| **Model** | PRIMARY (`gemini-3.1-flash-lite-preview`) |
| **Thinking** | None |
| **Tools** | `playwright_tool`, `crawl4ai_tool`, `crawl4ai_advanced_tool`, `crawl4ai_deep_tool` |
| **Output Key** | `rawSiteData` |
| **Description** | Crawls the target business URL to extract raw site content, contact pages, social anchors, menu URLs, and delivery platform links. Produces the foundational data that all Stage 2 agents consume. |

#### EntityMatcherAgent
| | |
|---|---|
| **Name** | `EntityMatcherAgent` |
| **Model** | PRIMARY |
| **Thinking** | None |
| **Tools** | None (pure analysis) |
| **Output Key** | `entityMatchResult` |
| **Output Schema** | `EntityMatchOutput` |
| **Description** | Validates that the crawled site actually belongs to the target business. Prevents wasted compute on mismatched URLs. If it fails, Phase 2 is skipped entirely. |

---

### Phase 2: Fan-Out + Profiling + Review

#### DiscoveryFanOut (ParallelAgent)

Runs 9 specialized sub-agents concurrently. Three agents (Contact, Social, Menu) have stage gating that skips them if Stage 1 already found sufficient data.

##### ThemeAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `themeData` |
| **Description** | Extracts visual theme, branding, and persona information from the raw crawl data plus supplementary Google searches. |

##### ContactAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool`, `playwright_tool` |
| **Output Key** | `contactData` |
| **Gated** | Skipped if deterministic extraction already found email + phone |
| **Description** | Discovers contact information (email, phone, contact form URL) by crawling contact pages and searching. Uses targeted crawl of discovered contact page URLs. |

##### SocialMediaAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `socialData` |
| **Gated** | Skipped if crawl found 3+ social links |
| **Description** | Finds social media profile URLs (Instagram, Facebook, Twitter, TikTok, Yelp) for the business. |

##### MenuAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool`, `playwright_tool`, `crawl4ai_advanced_tool`, `crawl4ai_deep_tool` |
| **Output Key** | `menuData` |
| **Gated** | Skipped if crawl already found a menu URL |
| **Description** | Searches for the business menu, including delivery platform listings (DoorDash, Grubhub, UberEats) when no direct menu is found. |

##### MapsAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `mapsData` |
| **Description** | Gathers Google Maps data including ratings, reviews, hours, and address verification. |

##### CompetitorAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Thinking** | HIGH |
| **Tools** | `google_search_tool`, `crawl4ai_tool`, `crawl4ai_advanced_tool` |
| **Output Key** | `competitorData` |
| **Description** | Identifies and researches local competitors by searching and crawling competitor websites for pricing, positioning, and market data. |

##### NewsAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `newsData` |
| **Description** | Searches for recent news articles, press mentions, and media coverage about the business. |

##### BusinessOverviewAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `aiOverview` |
| **Description** | Generates a concise AI-powered business overview combining crawl data with Google search results. |

##### ChallengesAgent
| | |
|---|---|
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Output Key** | `challengesData` |
| **Description** | Dedicated pain points researcher that identifies specific challenges and problems the business faces. |

#### SocialProfilerAgent
| | |
|---|---|
| **Name** | `SocialProfilerAgent` |
| **Model** | PRIMARY |
| **Tools** | `google_search_tool`, `crawl4ai_advanced_tool` |
| **Output Key** | `socialProfileMetrics` |
| **Description** | Crawls discovered social profile URLs to extract engagement metrics (followers, posting frequency, engagement rates) for each platform. Runs after the fan-out so it has social URLs available. |

#### DiscoveryReviewerAgent
| | |
|---|---|
| **Name** | `DiscoveryReviewerAgent` |
| **Model** | PRIMARY |
| **Tools** | `validate_url_tool`, `google_search_tool` |
| **Output Key** | `reviewerData` |
| **Description** | Final validation stage that cross-references all discovery data, validates URLs, corrects invalid ones, and ensures data consistency across all 9 sub-agent outputs. |

---

## 4. Qualification Agents

### QualityGateAgent

| | |
|---|---|
| **File** | `apps/api/hephae_api/workflows/scheduled_discovery/quality_gate.py` |
| **Name** | `QualityGateAgent` |
| **Model** | PRIMARY |
| **Thinking** | None |
| **Tools** | `qualify()` (FunctionTool) |
| **Description** | Critical filter between discovery and capability analysis. Disqualifies chains/franchises, businesses with no contact info, permanently closed businesses, and profiles too thin for meaningful analysis. Fail-open on agent error. |

### ReviewerAgent

| | |
|---|---|
| **File** | `agents/hephae_agents/reviewer/runner.py` |
| **Name** | `ReviewerAgent` |
| **Model** | PRIMARY |
| **Thinking** | None |
| **Tools** | `record_review()` (FunctionTool) |
| **Description** | Scores a business 1-10 for outreach readiness based on its identity and all capability outputs. Identifies the best contact channel and provides strengths/concerns for the sales team. |

### BatchSupervisorAgent

| | |
|---|---|
| **File** | `agents/hephae_agents/discovery/batch_supervisor.py` |
| **Name** | `batch_supervisor` |
| **Model** | PRIMARY |
| **Thinking** | None |
| **Tools** | None |
| **Description** | Summarizes a large discovery sweep for the Admin UI. Identifies top "gold" leads, flags data quality issues, and recommends next steps. Runs as Phase 7 of area research. |

---

## 5. Capability Agents

### SEO Auditor

| | |
|---|---|
| **File** | `agents/hephae_agents/seo_auditor/agent.py` |
| **Runner** | `agents/hephae_agents/seo_auditor/runner.py` |
| **Name** | `seoAuditor` |
| **Model** | PRIMARY |
| **Thinking** | DEEP (`thinking_budget=8192`) |
| **Tools** | `google_search_tool`, `pagespeed_tool`, `load_memory_tool` |
| **Description** | Comprehensive SEO auditor that scores websites across 5 categories (Technical, Content, UX, Performance, Authority). Uses Google Search for competitive benchmarking and PageSpeed Insights for performance metrics. |

### Traffic Forecaster

| | |
|---|---|
| **File** | `agents/hephae_agents/traffic_forecaster/agent.py` |
| **Runner** | `agents/hephae_agents/traffic_forecaster/runner.py` |
| **Architecture** | ParallelAgent gathering -> separate synthesis call |

**Sub-agents (ContextGatherer ParallelAgent):**

| Agent | Tools | Output Key | Description |
|-------|-------|------------|-------------|
| `PoiGatherer` | `google_search_tool` | `poiDetails` | Researches nearby points of interest and their impact on foot traffic |
| `WeatherGatherer` | `weather_tool`, `google_search_tool` | `weatherData` | Gathers real-time weather forecasts for the business location |
| `EventsGatherer` | `google_search_tool` | `eventsData` | Discovers upcoming local events that could affect traffic patterns |

**Synthesis:** Uses `generate_with_fallback` (PRIMARY model, `temperature=0.2`, structured JSON output with `TrafficForecastOutput` schema) to produce a 3-day foot traffic forecast with hourly slots. Supports deferred mode (`skip_synthesis=True`) for workflow pipelining.

### Competitive Analyzer

| | |
|---|---|
| **File** | `agents/hephae_agents/competitive_analysis/agent.py` |
| **Runner** | `agents/hephae_agents/competitive_analysis/runner.py` |
| **Architecture** | SequentialAgent: CompetitorProfiler -> MarketPositioning |

| Agent | Model | Thinking | Tools | Output Key |
|-------|-------|----------|-------|------------|
| `CompetitorProfilerAgent` | PRIMARY | None | `google_search_tool`, `load_memory_tool` | `competitorBrief` |
| `MarketPositioningAgent` | PRIMARY | HIGH | None | (output_schema: `CompetitiveAnalysisOutput`) |

**Description:** Two-stage pipeline that first profiles each competitor via Google Search, then synthesizes market positioning analysis with HIGH thinking for strategic depth.

### Margin Surgeon

| | |
|---|---|
| **File** | `agents/hephae_agents/margin_analyzer/agent.py` |
| **Runner** | `agents/hephae_agents/margin_analyzer/runner.py` |
| **Architecture** | SequentialAgent: VisionIntake -> (Benchmarker \|\| CommodityWatchdog) -> Surgeon -> Advisor |

| Agent | Model | Tools | Output Key | Schema |
|-------|-------|-------|------------|--------|
| `VisionIntakeAgent` | PRIMARY | None | `parsedMenuItems` | `MenuIntakeOutput` |
| `BenchmarkerAgent` | PRIMARY | `benchmark_tool` | `competitorBenchmarks` | -- |
| `CommodityWatchdogAgent` | PRIMARY | `commodity_inflation_tool` | `commodityTrends` | -- |
| `SurgeonAgent` | PRIMARY | `surgery_tool` | `menuAnalysis` | -- |
| `AdvisorAgent` | PRIMARY | None | `strategicAdvice` | `AdvisorOutput` |

**Description:** Five-stage menu profitability pipeline. Parses menu items from screenshots/PDFs, benchmarks prices against competitors, checks commodity inflation trends, performs margin surgery analysis, and produces strategic pricing advice. Benchmarker and CommodityWatchdog run in parallel.

### Social Media Auditor

| | |
|---|---|
| **File** | `agents/hephae_agents/social/media_auditor/agent.py` |
| **Runner** | `agents/hephae_agents/social/media_auditor/runner.py` |
| **Architecture** | SequentialAgent: SocialResearcher -> SocialStrategist |

| Agent | Model | Thinking | Tools | Output Key |
|-------|-------|----------|-------|------------|
| `SocialResearcherAgent` | PRIMARY | None | `google_search_tool`, `crawl4ai_advanced_tool`, `load_memory_tool` | `researchBrief` |
| `SocialStrategistAgent` | PRIMARY | HIGH | None | (output_schema: `SocialMediaAuditOutput`) |

**Description:** Two-stage audit that first researches each social platform via Google Search and crawling, then synthesizes a scored strategy with platform-by-platform recommendations using HIGH thinking.

---

## 6. Evaluator Agents

All evaluators live in `agents/hephae_agents/evaluators/`. Every evaluator uses PRIMARY model + MEDIUM thinking and outputs `EvaluationOutput` (`{score, isHallucinated, issues}`). Pass threshold: score >= 80 AND !isHallucinated.

### SEO Evaluator
| | |
|---|---|
| **File** | `agents/hephae_agents/evaluators/seo_evaluator.py` |
| **Name** | `seo_evaluator` |
| **Description** | Reviews SEO audit output for completeness, coherence, and URL-relevance. Checks whether the audit actually describes the target website and flags hallucinated findings. |

### Traffic Evaluator
| | |
|---|---|
| **File** | `agents/hephae_agents/evaluators/traffic_evaluator.py` |
| **Name** | `traffic_evaluator` |
| **Description** | Validates traffic forecast plausibility: geographic consistency, time-slot logic, weather accuracy, event relevance, and score distribution. Cross-checks against admin research context when available. Conservative hallucination flagging since the forecaster has real-time search access. |

### Competitive Evaluator
| | |
|---|---|
| **File** | `agents/hephae_agents/evaluators/competitive_evaluator.py` |
| **Name** | `competitive_evaluator` |
| **Description** | Validates competitor names are plausible real businesses, analysis depth is sufficient, internal consistency holds, and insights are actionable. Conservative on hallucination since the analyzer uses Google Search. |

### Margin Surgeon Evaluator
| | |
|---|---|
| **File** | `agents/hephae_agents/evaluators/margin_surgeon_evaluator.py` |
| **Name** | `margin_surgeon_evaluator` |
| **Description** | Reviews margin analysis for menu item plausibility (e.g., no sushi for a pizza shop), score consistency, and strategic advice coherence. When food pricing context is provided, verifies that advice acknowledges commodity cost trends. |

---

## 7. Research Agents

### Zip Code Research

#### ZipCodeResearchAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/zipcode_research.py` |
| **Name** | `zipcode_researcher` |
| **Model** | PRIMARY |
| **Tools** | `google_search` (ADK built-in) |
| **Description** | Deep-researches a US zip code across 9 categories: geography, demographics, census/housing, business landscape, economic indicators, consumer behavior, infrastructure, upcoming events (2-week window), and weather/seasonal patterns. Extracts the DMA region name for Google Trends queries. |

#### ReportComposerAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/zipcode_report_composer.py` |
| **Name** | `zipcode_report_composer` |
| **Model** | PRIMARY |
| **Output Schema** | `ZipcodeReportComposerOutput` |
| **Description** | Transforms raw research findings and Google Trends data into a structured 10-section zip code report with summaries, key facts, and source counts. |

**Orchestrator:** `apps/api/hephae_api/workflows/orchestrators/zipcode_research.py` -- Pipeline: check cache -> research agent -> BigQuery trends -> report composer -> save to Firestore.

### Area Research

#### AreaSummaryAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/area_summary.py` |
| **Name** | `area_summary` |
| **Model** | PRIMARY |
| **Thinking** | DEEP |
| **Description** | Synthesizes multiple zip code reports into an area-level business opportunity summary with market opportunity, demographic fit, competitive landscape, trending insights, risks, and recommendations. |

#### EnhancedAreaSummaryAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/area_summary.py` |
| **Name** | `enhanced_area_summary` |
| **Model** | PRIMARY |
| **Thinking** | DEEP |
| **Description** | Enhanced version that synthesizes 6+ data sources (zip reports, industry analysis, news, Google Trends, FDA, BLS CPI, USDA prices, local catalysts, Census demographics) into a comprehensive area analysis. Uses concrete BLS/USDA numbers as evidence. |

**Orchestrator:** `apps/api/hephae_api/workflows/orchestrators/area_research.py` -- 7-phase pipeline: resolve zip codes -> research each zip -> industry intelligence -> local sector analysis -> synthesis -> lead discovery -> batch supervision.

### Sector Research

**Orchestrator:** `apps/api/hephae_api/workflows/orchestrators/sector_research.py` -- Pipeline: industry analysis -> local trends per zip -> synthesis.

### Intelligence Fan-Out (ParallelAgent)

| | |
|---|---|
| **File** | `agents/hephae_agents/research/intel_fan_out.py` |
| **Name** | `IntelligenceFanOut` |
| **Architecture** | ParallelAgent with 4 LLM sub-agents + parallel API data sources |

| Sub-Agent | Model | Thinking | Tools | Output Key |
|-----------|-------|----------|-------|------------|
| `IndustryAnalystIntel` | PRIMARY | DEEP | None | `industryAnalysis` |
| `IndustryNewsIntel` | PRIMARY | None | `google_search` | `industryNews` |
| `LocalCatalystIntel` | PRIMARY | None | `google_search_tool`, `crawl4ai_advanced_tool` | `localCatalysts` |
| `DemographicExpertIntel` | PRIMARY | None | `google_search_tool` | `demographicData` |

**API Sources (run in parallel alongside LLM agents):** BLS CPI, USDA prices, FDA enforcements, BigQuery industry trends. Uses ADK context caching (15-min TTL, 1024-token minimum) to save prefill tokens across zip codes.

### IndustryAnalystAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/industry_analyst.py` |
| **Name** | `industry_analyst` |
| **Model** | PRIMARY |
| **Thinking** | DEEP |
| **Output Schema** | `IndustryAnalystOutput` |
| **Description** | Performs deep industry/sector analysis covering market size, growth rate, challenges, opportunities, trends, consumer behavior shifts, technology adoption, regulatory environment, and financial benchmarks. |

### IndustryNewsAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/industry_news.py` |
| **Name** | `industry_news` |
| **Model** | PRIMARY |
| **Tools** | `google_search` (ADK built-in) |
| **Output Schema** | `IndustryNewsOutput` |
| **Description** | Searches for recent industry news (last 6 months), commodity/input price trends, and regulatory updates relevant to a specific industry and area. |

### LocalCatalystAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/local_catalyst.py` |
| **Name** | `local_catalyst` |
| **Model** | PRIMARY |
| **Tools** | `google_search_tool`, `crawl4ai_advanced_tool` |
| **Description** | Deep researcher for forward-looking local government signals. Searches town council agendas, planning board minutes, and legal notices to find development catalysts (construction, zoning changes, grants, infrastructure projects) that will impact local businesses. |

### DemographicExpertAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/demographic_expert.py` |
| **Name** | `demographic_expert` |
| **Model** | PRIMARY |
| **Tools** | `google_search_tool` |
| **Description** | Targeted Census/ACS data researcher that finds authoritative demographic data (population, income, age distribution, housing, education, economic indicators) from data.census.gov and ACS 5-year estimates. Cites source years and prefers Census Bureau data over third-party aggregators. |

### LocalSectorTrendsAgent
| | |
|---|---|
| **File** | `agents/hephae_agents/research/local_sector_trends.py` |
| **Name** | `local_sector_trends` |
| **Model** | PRIMARY |
| **Description** | Extracts sector-specific trends from zip code research reports, including demand signals, competitor density, and local opportunities for a given industry. |

---

## 8. Social / Marketing Agents

### Marketing Swarm

| | |
|---|---|
| **File** | `agents/hephae_agents/social/marketing_swarm/agent.py` |
| **Runner** | (inline `run_marketing_pipeline` function) |
| **Architecture** | Sequential: CreativeDirector -> PlatformRouter -> (Instagram OR Blog) Copywriter |

| Agent | Model | Tools | Output Key |
|-------|-------|-------|------------|
| `CreativeDirectorAgent` | PRIMARY | None | `creativeDirection` |
| `PlatformRouterAgent` | PRIMARY | None | `platformDecision` |
| `InstagramCopywriterAgent` | PRIMARY | None | `instagramDraft` |
| `BlogCopywriterAgent` | PRIMARY | None | `blogDraft` |

**Description:** Three-stage content pipeline. The Creative Director sets the strategic direction, the Platform Router picks the best channel (Instagram or Blog), and the appropriate Copywriter generates a platform-specific draft. Supports admin research context (consumer market data, trending searches, demographics) for data-driven marketing.

### Blog Writer

| | |
|---|---|
| **File** | `agents/hephae_agents/social/blog_writer/agent.py` |
| **Runner** | `agents/hephae_agents/social/blog_writer/runner.py` |
| **Architecture** | SequentialAgent: ResearchCompiler -> BlogWriter |

| Agent | Model | Thinking | Tools | Output Key | Schema |
|-------|-------|----------|-------|------------|--------|
| `ResearchCompilerAgent` | PRIMARY | None | None | `researchBrief` | `BlogResearchOutput` |
| `BlogWriterAgent` | PRIMARY | DEEP | None | `blogContent` | -- |

**Description:** Two-stage blog generation pipeline. The ResearchCompiler distills all capability outputs (SEO, traffic, competitive, margin, marketing) into a research brief, then the BlogWriter generates an 800-1200 word authoritative HTML blog post using DEEP thinking.

### Social Post Generator

| | |
|---|---|
| **File** | `agents/hephae_agents/social/post_generator/agent.py` |
| **Runner** | `agents/hephae_agents/social/post_generator/runner.py` |
| **Architecture** | ParallelAgent: 5 channel agents running concurrently |

| Agent | Model | Output Key | Schema |
|-------|-------|------------|--------|
| `InstagramPostAgent` | PRIMARY | `instagramPost` | `InstagramPostOutput` |
| `FacebookPostAgent` | PRIMARY | `facebookPost` | `FacebookPostOutput` |
| `TwitterPostAgent` | PRIMARY | `twitterPost` | `TwitterPostOutput` |
| `EmailOutreachAgent` | PRIMARY | `emailOutreach` | `EmailOutreachOutput` |
| `ContactFormAgent` | PRIMARY | `contactFormDraft` | `ContactFormOutput` |

**Description:** Generates outreach content for 5 channels in parallel from report data. Supports both simple (single summary) and rich (all latestOutputs) context modes. Includes CDN report links and social card image URLs. Falls back to template-based content on agent failure.

### Outreach Generator

| | |
|---|---|
| **File** | `agents/hephae_agents/social/outreach_generator/agent.py` |
| **Runner** | `agents/hephae_agents/social/outreach_generator/runner.py` |
| **Name** | `OutreachGenerator` |
| **Model** | PRIMARY |
| **Tools** | None |
| **Description** | Generates personalized marketing outreach content using industry intelligence. Takes business data, analysis insights, industry config, and report URL to produce tailored outreach messages. |

---

## 9. Insights Agent

| | |
|---|---|
| **File** | `agents/hephae_agents/insights/insights_agent.py` |
| **Name** | `insights_agent` |
| **Model** | PRIMARY |
| **Thinking** | None |
| **Tools** | None |
| **Output Schema** | `InsightsOutput` |
| **Description** | Cross-capability synthesizer that takes all capability outputs (SEO, traffic, competitive, margin) for a business and generates a summary, 3-5 key findings, and 3-5 prioritized recommendations. When food pricing context (BLS/USDA) is available, incorporates cost environment analysis into recommendations. Supports both single-business and batch generation modes. |

---

## 10. Legacy Agents

### ProfilerAgent

| | |
|---|---|
| **File** | `agents/hephae_agents/business_profiler/agent.py` |
| **Runner** | `agents/hephae_agents/business_profiler/runner.py` |
| **Type** | Plain Python class (not an LlmAgent) |
| **Description** | Legacy slow-path business profiler. Extracts colors, logo, and persona via `crawl_web_page` and takes a menu screenshot. Used by the analyze slow path only. |

---

## Agent Count Summary

| Category | LlmAgent Count | Orchestrators |
|----------|---------------|---------------|
| Discovery | 13 | 2 SequentialAgents, 1 ParallelAgent |
| Qualification / Review | 3 | -- |
| Capabilities | 12 | 3 SequentialAgents, 2 ParallelAgents |
| Evaluators | 4 | -- |
| Research | 8 | 1 ParallelAgent (IntelligenceFanOut) |
| Social / Marketing | 10 | 1 SequentialAgent, 1 ParallelAgent |
| Insights | 1 | -- |
| **Total** | **51** | **10** |
