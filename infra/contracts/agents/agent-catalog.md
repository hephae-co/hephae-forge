# Agent Catalog
> Auto-generated from codebase on 2026-03-22. Do not edit manually — run `/hephae-refresh-docs` to update.

---

## 1. Model Tiers

| Tier | Constant | Model ID | Use Case |
|------|----------|----------|----------|
| PRIMARY | `AgentModels.PRIMARY_MODEL` | `gemini-3.1-flash-lite-preview` | All standard agents |
| SYNTHESIS | `AgentModels.SYNTHESIS_MODEL` | `gemini-3-flash-preview` | Final synthesis stages |
| FALLBACK | `AgentModels.FALLBACK_MODEL` | `gemini-3-flash-preview` | Auto-fallback on 429/503/529 |
| CREATIVE_VISION | `AgentModels.CREATIVE_VISION_MODEL` | `gemini-3.1-flash-image-preview` | Image generation |

**Thinking Presets** (via `ThinkingPresets`):

| Preset | Use Case |
|--------|----------|
| MEDIUM | Evaluators |
| HIGH | Competitive positioning, social strategist, competitor discovery |
| DEEP | SEO auditor, blog writer, complex analysis |

> Source: `lib/common/hephae_common/model_config.py`

---

## 2. Agent Versions

All versions are tracked in `apps/api/hephae_api/config.py` under `AgentVersions`.

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

### Analysis Agents

| Agent | Version | Notes |
|-------|---------|-------|
| MARGIN_SURGEON | 1.1.0 | MINOR: PDF extraction, menuNotFound flow, pre-discovered delivery URLs |
| SEO_AUDITOR | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |
| TRAFFIC_FORECASTER | 1.0.0 | |
| COMPETITIVE_ANALYZER | 1.0.0 | |

### Marketing / Social

| Agent | Version | Notes |
|-------|---------|-------|
| MARKETING_SWARM | 1.0.0 | |
| SOCIAL_MEDIA_AUDITOR | 1.0.0 | |
| SOCIAL_POST_GENERATOR | 3.0.0 | MAJOR: CDN report links + social card images, reports via cdn.hephae.co |
| BLOG_WRITER | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |

### Research Agents

| Agent | Version | Notes |
|-------|---------|-------|
| LOCAL_CATALYST | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |
| DEMOGRAPHIC_EXPERT | 1.1.0 | MINOR: switched to PRIMARY_MODEL + DEEP thinking |

### Other

| Agent | Version | Notes |
|-------|---------|-------|
| WEEKLY_PULSE | 1.0.0 | |
| QUALIFICATION_SCANNER | 1.0.0 | |

---

## 3. Discovery Pipeline Agents

The discovery pipeline is a 4-stage sequential agent (`DiscoveryPipeline`):

### Stage 1: SiteCrawlerAgent
- **Model**: PRIMARY
- **Tools**: `playwright_tool`, `crawl4ai_tool`, `crawl4ai_advanced_tool`, `crawl4ai_deep_tool`
- **Output key**: `rawSiteData`
- **Purpose**: Crawls the business URL once to extract raw site data

### Stage 1.5: EntityMatcherAgent
- **Model**: PRIMARY
- **Tools**: None (pure analysis)
- **Output key**: `entityMatchResult`
- **Output schema**: `EntityMatchOutput`
- **Purpose**: Validates the crawled site matches the target business; runner aborts if mismatch

### Stage 2: DiscoveryFanOut (ParallelAgent — 9 sub-agents)

| Sub-Agent | Output Key | Tools | Stage Gating |
|-----------|-----------|-------|--------------|
| ThemeAgent | `themeData` | google_search | None |
| ContactAgent | `contactData` | google_search, playwright | Skip if email + phone already found |
| SocialMediaAgent | `socialData` | google_search | Skip if 3+ social links found |
| MenuAgent | `menuData` | google_search, playwright, crawl4ai_advanced, crawl4ai_deep | Skip if menuUrl already found |
| MapsAgent | `mapsData` | google_search | None |
| CompetitorAgent | `competitorData` | google_search, crawl4ai, crawl4ai_advanced | None (HIGH thinking) |
| NewsAgent | `newsData` | google_search | None |
| BusinessOverviewAgent | `aiOverview` | google_search | None |
| ChallengesAgent | `challengesData` | google_search | None |

All fan-out agents receive `rawSiteData` via dynamic instruction injection. ContactAgent and MenuAgent additionally receive targeted crawl hints (discovered contact/menu pages from Stage 1).

### Stage 3: SocialProfilerAgent
- **Model**: PRIMARY
- **Tools**: `google_search_tool`, `crawl4ai_advanced_tool`
- **Output key**: `socialProfileMetrics`
- **Purpose**: Crawls discovered social URLs for follower counts, engagement metrics

### Stage 4: DiscoveryReviewerAgent
- **Model**: PRIMARY
- **Tools**: `validate_url_tool`, `google_search_tool`
- **Output key**: `reviewerData`
- **Purpose**: Validates all URLs discovered in earlier stages, corrects invalid ones

> Source: `agents/hephae_agents/discovery/agent.py`

---

## 4. Analysis Capability Agents

### 4.1 SEO Auditor (`seoAuditor`)
- **Model**: PRIMARY + DEEP thinking
- **Tools**: `google_search_tool`, `pagespeed_tool`, `load_memory_tool`
- **Architecture**: Single LlmAgent
- **Output**: Comprehensive SEO audit across 5 categories (technical, content, UX, performance, authority)

> Source: `agents/hephae_agents/seo_auditor/agent.py`

### 4.2 Traffic Forecaster (`ForecasterAgent`)
- **Model**: PRIMARY (gatherers) + PRIMARY (synthesis with `response_schema`)
- **Architecture**: ParallelAgent (3 gatherers) + direct Gemini synthesis call

| Sub-Agent | Tools | Output Key |
|-----------|-------|-----------|
| PoiGatherer | google_search | `poiDetails` |
| WeatherGatherer | weather_tool, google_search | `weatherData` |
| EventsGatherer | google_search | `eventsData` |

Synthesis uses `generate_with_fallback()` with `TrafficForecastOutput` response schema and temperature 0.2.

Supports `skip_synthesis=True` for deferred batch synthesis — returns raw intel without the final synthesis call.

> Source: `agents/hephae_agents/traffic_forecaster/agent.py`

### 4.3 Competitive Analysis (`CompetitivePipeline`)
- **Architecture**: SequentialAgent (2 stages)

| Stage | Agent | Model | Thinking | Tools |
|-------|-------|-------|----------|-------|
| 1 | CompetitorProfilerAgent | PRIMARY | Default | google_search, load_memory |
| 2 | MarketPositioningAgent | PRIMARY | HIGH | None (output_schema: `CompetitiveAnalysisOutput`) |

State flows via session: `competitorBrief` (output of Stage 1) is read by Stage 2.

> Source: `agents/hephae_agents/competitive_analysis/agent.py`

### 4.4 Margin Surgeon (`MarginSurgeryOrchestrator`)
- **Architecture**: SequentialAgent (4 stages with parallel fan-out)

```
VisionIntakeAgent → (BenchmarkerAgent || CommodityWatchdogAgent) → SurgeonAgent → AdvisorAgent
```

| Agent | Tools | Output Key | Output Schema |
|-------|-------|-----------|---------------|
| VisionIntakeAgent | None | `parsedMenuItems` | `MenuIntakeOutput` |
| BenchmarkerAgent | `benchmark_tool` | `competitorBenchmarks` | None (tools conflict) |
| CommodityWatchdogAgent | `commodity_inflation_tool` | `commodityTrends` | None (tools conflict) |
| SurgeonAgent | `surgery_tool` | `menuAnalysis` | None (tools conflict) |
| AdvisorAgent | None | `strategicAdvice` | `AdvisorOutput` |

BenchmarkerAgent and CommodityWatchdogAgent run in parallel via `BenchmarkAndCommodity` ParallelAgent.

> Source: `agents/hephae_agents/margin_analyzer/agent.py`

### 4.5 Social Media Auditor (`SocialAuditPipeline`)
- **Architecture**: SequentialAgent (2 stages)

| Stage | Agent | Model | Thinking | Tools |
|-------|-------|-------|----------|-------|
| 1 | SocialResearcherAgent | PRIMARY | Default | google_search, crawl4ai_advanced, load_memory |
| 2 | SocialStrategistAgent | PRIMARY | HIGH | None (output_schema: `SocialMediaAuditOutput`) |

> Source: `agents/hephae_agents/social/media_auditor/agent.py`

---

## 5. Marketing / Content Agents

### 5.1 Marketing Swarm

Pipeline: CreativeDirector → PlatformRouter → Instagram/Blog Copywriter (conditional).

| Agent | Model | Output Key |
|-------|-------|-----------|
| CreativeDirectorAgent | PRIMARY | `creativeDirection` |
| PlatformRouterAgent | PRIMARY | `platformDecision` |
| InstagramCopywriterAgent | PRIMARY | `instagramDraft` |
| BlogCopywriterAgent | PRIMARY | `blogDraft` |

Agents run sequentially via manual Runner calls (not a SequentialAgent).

> Source: `agents/hephae_agents/social/marketing_swarm/agent.py`

### 5.2 Social Post Generator (`SocialPostParallel`)
- **Architecture**: ParallelAgent (5 channels)

| Agent | Output Key | Output Schema |
|-------|-----------|---------------|
| InstagramPostAgent | `instagramPost` | `InstagramPostOutput` |
| FacebookPostAgent | `facebookPost` | `FacebookPostOutput` |
| TwitterPostAgent | `twitterPost` | `TwitterPostOutput` |
| EmailOutreachAgent | `emailOutreach` | `EmailOutreachOutput` |
| ContactFormAgent | `contactFormDraft` | `ContactFormOutput` |

All agents use PRIMARY model. Falls back to template-based posts if any channel agent fails.

> Source: `agents/hephae_agents/social/post_generator/agent.py`

### 5.3 Blog Writer (`BlogPipeline`)
- **Architecture**: SequentialAgent (2 stages)

| Stage | Agent | Model | Thinking | Output Key |
|-------|-------|-------|----------|-----------|
| 1 | ResearchCompilerAgent | PRIMARY | Default | `researchBrief` (`BlogResearchOutput`) |
| 2 | BlogWriterAgent | PRIMARY | DEEP | `blogContent` |

Generates 800-1200 word blog posts from Firestore `latestOutputs`.

> Source: `agents/hephae_agents/social/blog_writer/agent.py`

### 5.4 Outreach Generator
- **Model**: PRIMARY
- **Architecture**: Single LlmAgent
- **Purpose**: Generates personalized marketing outreach content

> Source: `agents/hephae_agents/social/outreach_generator/agent.py`

---

## 6. Other Agents

### 6.1 Insights Agent
- **Model**: PRIMARY
- **Architecture**: Single LlmAgent
- **Purpose**: Synthesizes cross-capability findings (SEO, traffic, competitive, margin) into actionable insights
- **Output schema**: `InsightsOutput` — `{summary, keyFindings[], recommendations[]}`
- **Integrates**: Food pricing context from BLS/USDA when available

> Source: `agents/hephae_agents/insights/insights_agent.py`

### 6.2 Business Profiler (legacy)
- **Architecture**: Python class (not an LLM agent)
- **Purpose**: Crawls website, extracts colors/logo/persona, takes menu screenshot
- **Tools**: `crawl_web_page`, `screenshot_page` (shared tools)

> Source: `agents/hephae_agents/business_profiler/agent.py`

### 6.3 Profile Builder (chatbot)
- **Architecture**: Instruction-only agent (no `agent.py` LlmAgent defined, instruction used in chatbot flow)
- **Purpose**: Guided chatbot flow to collect business details (social accounts, delivery platforms, menu URL, capabilities to run)

> Source: `agents/hephae_agents/profile_builder/agent.py`

### 6.4 Business Overview Agent
- **Architecture**: 3-stage agent (Search + Maps + Synthesizer)
- **Purpose**: Produces rich business overview combining Google Search reputation, Maps competitor density, zipcode research, and pulse data
- **Output**: Structured JSON with `businessSnapshot`, `marketPosition`, `localEconomy`, `localBuzz`, `keyOpportunities`, `capabilityTeasers`

> Source: `agents/hephae_agents/business_overview/agent.py`

### 6.5 Qualification Scanner
- **Architecture**: Python functions (not an LLM agent for Step A; batched LLM for Step B tiebreaker)
- **Purpose**: Two-step qualification — metadata scan + optional full probe + LLM classification
- **Tools**: `page_fetcher`, `domain_analyzer`, `platform_detector`, `pixel_detector`, `contact_path_detector`, `meta_extractor`

> Source: `agents/hephae_agents/qualification/scanner.py`

---

## 7. Evaluator Agents

| Agent | Name | Capability | Model | Thinking |
|-------|------|-----------|-------|----------|
| SeoEvaluatorAgent | `seo_evaluator` | SEO Audit | PRIMARY | MEDIUM |
| TrafficEvaluatorAgent | `traffic_evaluator` | Traffic Forecast | PRIMARY | MEDIUM |
| CompetitiveEvaluatorAgent | `competitive_evaluator` | Competitive Analysis | PRIMARY | MEDIUM |
| MarginSurgeonEvaluatorAgent | `margin_surgeon_evaluator` | Margin Surgeon | PRIMARY | MEDIUM |

All evaluators output `EvaluationOutput`: `{score: 0-100, isHallucinated: boolean, issues: string[]}`.

All use `fallback_on_error` for automatic model fallback.

> Source: `agents/hephae_agents/evaluators/`

---

## 8. NEW: Industry Pulse Agents

### 8.1 Industry Trend Summarizer

- **Agent name**: `industry_trend_summarizer`
- **Model**: PRIMARY (`gemini-3.1-flash-lite-preview`)
- **Thinking**: None (default)
- **Architecture**: Single LlmAgent, instantiated per-call in `_generate_trend_summary()`
- **System instruction**: "You are a concise economic analyst. Summarize data signals in 2-3 paragraphs with specific numbers. No advice, just facts."
- **Purpose**: Generates a 2-3 paragraph national trend summary from pre-computed impact variables and triggered playbooks

**Input context** (injected into prompt):
- Pre-computed impact variables (e.g., `dairy_yoy_pct: 3.56`)
- Triggered playbook names and first 120 chars of play text

**Output**: Plain text summary (no JSON schema)

> Source: `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py`

### 8.2 IndustryConfig Verticals

Three verticals are currently registered:

| Vertical | Aliases (sample) | Economist Context Focus |
|----------|------------------|------------------------|
| **restaurant** | restaurant, pizza, cafe, deli, coffee, grocery | Food cost inflation across proteins, dairy, produce. Margins 3-9%. |
| **bakery** | bakery, patisserie, bread shop, donut shop, cupcake shop | Flour/wheat, eggs, butter, dairy, sugar — 20-35% of revenue. Net margins 4-15%. |
| **barber** | barber, barbershop, salon, spa, nail salon | Barber/beauty services CPI. Labor 40-60%. A $30 haircut nets $12-15. |

Adding a new vertical requires:
1. Creating a new `IndustryConfig` instance
2. Appending to the `_ALL` list
3. Aliases are automatically indexed for `resolve()` lookup

> Source: `apps/api/hephae_api/workflows/orchestrators/industries.py`
