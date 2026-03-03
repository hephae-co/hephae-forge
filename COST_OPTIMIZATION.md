# Cost Optimization Analysis — Hephae Forge

**Date:** 2026-03-03
**Scope:** Gemini model usage, Google Search grounding, external APIs, caching strategy

---

## Executive Summary

Hephae Forge currently runs **~20 LLM agent calls per business analysis**, burning through Gemini 2.5 Pro ($1.25/$10 per 1M tokens) in places where Flash ($0.30/$2.50) or even **Flash-Lite ($0.10/$0.40)** would suffice. Google Search grounding is used pervasively without rate awareness — at $35/1K prompts for Gemini 2.x, this becomes the **single largest hidden cost** at scale. This document identifies **7 concrete optimizations** that can reduce per-analysis costs by an estimated **60–75%**.

---

## 1. Current Cost Map (Per Business Analysis)

### Model Usage Audit

| Agent | Current Model | Grounding? | Est. Input Tokens | Est. Output Tokens |
|---|---|---|---|---|
| **LocatorAgent** | Flash | Yes (Search) | ~500 | ~200 |
| **SiteCrawlerAgent** | Flash | No | ~1,000 | ~3,000 |
| **ThemeAgent** | Flash | Yes (fallback) | ~31,000 | ~300 |
| **ContactAgent** | Flash | Yes (fallback) | ~31,000 | ~300 |
| **SocialMediaAgent** | Flash | Yes (3-6 calls) | ~31,000 | ~800 |
| **MenuAgent** | Flash | No | ~31,000 | ~500 |
| **MapsAgent** | Flash | Yes | ~31,000 | ~300 |
| **CompetitorAgent** | **Pro** | Yes (3+ calls) | ~31,000 | ~1,500 |
| **SocialProfilerAgent** | Flash | No | ~2,000 | ~2,000 |
| **VisionIntakeAgent** | Flash | No | ~50,000 (image) | ~2,000 |
| **BenchmarkerAgent** | Flash | No | ~2,000 | ~1,500 |
| **CommodityWatchdogAgent** | Flash | No | ~1,000 | ~500 |
| **SurgeonAgent** | Flash | No | ~3,000 | ~3,000 |
| **AdvisorAgent** | Flash | No | ~5,000 | ~2,000 |
| **CompetitorProfilerAgent** | Flash | Yes (3+ calls) | ~2,000 | ~2,000 |
| **MarketPositioningAgent** | **Pro** | No | ~5,000 | ~3,000 |
| **SEO Auditor** | **Pro** | Yes (3+ calls) | ~3,000 | ~10,000 |
| **PoiGatherer** | Flash | Yes | ~1,000 | ~1,000 |
| **WeatherGatherer** | Flash | Yes (fallback) | ~1,000 | ~500 |
| **EventsGatherer** | Flash | Yes | ~1,000 | ~1,000 |
| **Forecaster Synthesis** | Flash | No | ~5,000 | ~4,000 |
| **CreativeDirector** | Flash | No | ~5,000 | ~500 |
| **PlatformRouter** | Flash | No | ~1,000 | ~200 |
| **Copywriter** | Flash | No | ~2,000 | ~500 |
| **Chat (per message)** | Flash | No | ~2,000-10,000 | ~300 |

### Cost Per Full Analysis (Discovery + Margin + Competitive + SEO + Traffic + Marketing)

#### Model Token Costs

| Tier | Input Tokens | Output Tokens | Input Cost | Output Cost | Subtotal |
|---|---|---|---|---|---|
| Flash (~20 calls) | ~240K | ~26K | $0.072 | $0.065 | **$0.137** |
| Pro (3 calls: Competitor, MarketPositioning, SEO) | ~39K | ~14.5K | $0.049 | $0.145 | **$0.194** |
| **Token subtotal** | | | | | **$0.331** |

#### Google Search Grounding Costs (the big one)

The `google_search` tool in `shared_tools/google_search.py` makes a **separate Gemini API call with grounding enabled** per invocation. For Gemini 2.x models, grounding is billed at **$35 per 1,000 prompts** (not per search query — per prompt that uses grounding).

| Agent | Grounded Calls per Analysis | Cost at $35/1K |
|---|---|---|
| LocatorAgent | 1 | $0.035 |
| SocialMediaAgent | 3-6 (per missing platform) | $0.105-$0.210 |
| MapsAgent | 1 | $0.035 |
| CompetitorAgent (Discovery) | 3-5 | $0.105-$0.175 |
| CompetitorProfilerAgent | 3-6 | $0.105-$0.210 |
| SEO Auditor | 3-5 | $0.105-$0.175 |
| PoiGatherer | 1-2 | $0.035-$0.070 |
| EventsGatherer | 1-2 | $0.035-$0.070 |
| WeatherGatherer | 0-1 (fallback) | $0.000-$0.035 |
| **Grounding subtotal** | **~17-33 calls** | **$0.560-$1.015** |

#### Total Estimated Cost Per Analysis

| Component | Low Estimate | High Estimate |
|---|---|---|
| Token costs (Flash + Pro) | $0.33 | $0.33 |
| Grounding costs | $0.56 | $1.02 |
| PageSpeed (free) | $0.00 | $0.00 |
| BLS/FRED/NWS (free) | $0.00 | $0.00 |
| Firestore ops (~50 reads/writes) | $0.00 | $0.01 |
| **Total per analysis** | **$0.89** | **$1.36** |

**Grounding is 63-75% of the total cost.**

At 1,000 analyses/month: **$890-$1,360/month**, of which $560-$1,015 is grounding alone.

---

## 2. Optimization Recommendations

### OPT-1: Downgrade CompetitorAgent (Discovery) from Pro to Flash

**File:** `backend/agents/discovery/agent.py:126`
**Current:** `model=AgentModels.DEEP_ANALYST_MODEL` (gemini-2.5-pro)
**Proposed:** `model=AgentModels.DEFAULT_FAST_MODEL` (gemini-2.5-flash)

**Rationale:** The CompetitorAgent in discovery only finds 3 competitor names + URLs via Google Search. This is a research/retrieval task, not strategic synthesis. The MarketPositioningAgent downstream already uses Pro for the actual analysis.

**Savings:** ~$0.05 per analysis (Pro→Flash token differential on ~31K input / 1.5K output)

**Risk:** Low. The agent's prompt is a structured extraction task. Flash handles this well.

**Change:**
```python
# backend/agents/discovery/agent.py, line 126
competitor_agent = LlmAgent(
    name="CompetitorAgent",
    model=AgentModels.DEFAULT_FAST_MODEL,  # was DEEP_ANALYST_MODEL
    ...
)
```

---

### OPT-2: Introduce Flash-Lite Tier for Simple Extraction Agents

**New config constant in `backend/config.py`:**
```python
class AgentModels:
    BUDGET_FAST_MODEL = "gemini-2.5-flash-lite"  # $0.10/$0.40 per 1M tokens
    DEFAULT_FAST_MODEL = "gemini-2.5-flash"
    DEEP_ANALYST_MODEL = "gemini-2.5-pro"
    CREATIVE_VISION_MODEL = "gemini-3-pro-image-preview"
```

**Agents to move to Flash-Lite:**

| Agent | Why Flash-Lite is sufficient |
|---|---|
| **ThemeAgent** | Extracts 5 fields from pre-crawled HTML. Pure pattern matching. |
| **ContactAgent** | Extracts phone/email/hours from pre-crawled data. Trivial extraction. |
| **MenuAgent** | Finds menu URL in pre-crawled link list. Structured lookup. |
| **MapsAgent** | Finds Google Maps URL. Single search + extract. |
| **PlatformRouterAgent** | Binary decision: Instagram vs Blog. ~200 tokens output. |
| **CommodityWatchdogAgent** | Maps item names to commodity keywords, calls a tool. Mechanical. |
| **BenchmarkerAgent** | Calls a tool with location/items, returns result. Mechanical. |

**Savings estimate:** These 7 agents currently use Flash. Moving to Flash-Lite:
- Input savings: (0.30 - 0.10) × ~100K tokens / 1M = $0.020
- Output savings: (2.50 - 0.40) × ~6K tokens / 1M = $0.013
- **Per-analysis saving: ~$0.033** (modest, but compounds at scale)

**Risk:** Medium-low. Flash-Lite handles structured extraction and tool calling well. The key constraint is that Flash-Lite's reasoning is weaker — but these agents don't need reasoning, just extraction.

**Important:** ThemeAgent, ContactAgent, MapsAgent currently have Google Search as a fallback tool. Flash-Lite supports grounding, so this still works. But consider removing the grounding fallback from ThemeAgent and ContactAgent (see OPT-3).

---

### OPT-3: Eliminate Unnecessary Grounding Calls (Biggest Impact)

This is the **highest-ROI optimization**. At $35/1,000 prompts, every grounded call costs $0.035.

#### 3a. Remove grounding from ThemeAgent and ContactAgent

**Current:** Both have `google_search_tool` as a fallback when crawl data is missing.
**Reality:** These agents receive 30KB of raw crawl data injected via `_with_raw_data()`. The crawl data already contains `playwright.primaryColor`, `playwright.logoUrl`, `playwright.phone`, `playwright.email`, `playwright.hours`, `playwright.jsonLd`, etc.

**Proposed:** Remove `google_search_tool` from their tool lists. If the data isn't in the crawl, it's not going to be reliably found via search either.

```python
# backend/agents/discovery/agent.py
theme_agent = LlmAgent(
    name="ThemeAgent",
    model=AgentModels.BUDGET_FAST_MODEL,
    instruction=_with_raw_data(THEME_AGENT_INSTRUCTION),
    tools=[],  # was [google_search_tool]
    output_key="themeData",
)

contact_agent = LlmAgent(
    name="ContactAgent",
    model=AgentModels.BUDGET_FAST_MODEL,
    instruction=_with_raw_data(CONTACT_AGENT_INSTRUCTION),
    tools=[],  # was [google_search_tool]
    output_key="contactData",
)
```

**Savings:** 2-4 grounding calls eliminated → **$0.070-$0.140 per analysis**

**Risk:** Low. The prompt already says "ONLY if the above are missing." In practice, Playwright + Crawl4AI capture this data 90%+ of the time.

#### 3b. Consolidate SocialMediaAgent searches into fewer calls

**Current:** The prompt instructs the agent to make **separate** Google Search calls for each missing platform (Instagram, Facebook, Yelp, TikTok, DoorDash, GrubHub, UberEats). That's 3-7 grounding calls per analysis.

**Proposed options:**

**Option A — Batched search prompt (Recommended):**
Change the agent instruction to perform ONE search: `"[business name] [city] instagram facebook yelp tiktok grubhub doordash"` and extract all platform URLs from a single grounded response.

```
# In prompts.py, modify SOCIAL_MEDIA_AGENT_INSTRUCTION:
# Replace "make separate search calls" with:
# "Search for ALL missing platforms in a SINGLE query:
#  '[business name] [city] social media instagram facebook yelp tiktok delivery'
#  Then extract platform URLs from the sources array."
```

**Savings:** Reduces 3-7 grounding calls to 1 → **$0.070-$0.210 saved per analysis**

**Risk:** Medium. A single combined query may miss some platforms that a targeted search would find. Mitigation: accept this trade-off; the SocialProfilerAgent downstream will catch gaps.

**Option B — Use Crawl4AI instead of grounding:**
For platforms like Yelp and DoorDash, use `crawl4ai_tool` to directly fetch `yelp.com/biz/{slug}` or `doordash.com/store/{business}` URLs constructed from the business name. No grounding needed.

#### 3c. Cache LocatorAgent results per business query

**Current:** LocatorAgent makes a grounded Gemini call every time a business is searched.
**Proposed:** Cache resolved identities in Firestore (`cache_business_identity/{normalized_query}`) with a 30-day TTL. Most businesses don't move.

**Savings:** Eliminates repeat grounding calls for returning users. At $0.035 per call, saves proportionally to repeat query rate.

#### 3d. Rate-limit grounding to free tier

**Free tier:** 500 grounded queries/day (free) or 1,500/day (paid plan).

At ~17-33 grounding calls per analysis, the free tier supports **~15-29 analyses per day** before charges kick in.

**Proposed:** Add a grounding budget counter in Firestore or Redis. When approaching daily limit, degrade gracefully:
- Skip non-critical searches (ThemeAgent, ContactAgent fallbacks)
- Use cached competitor data from prior analyses in the same zip code
- Queue remaining analyses for the next day's free allocation

---

### OPT-4: Downgrade MarketPositioningAgent from Pro to Flash

**File:** `backend/agents/competitive_analysis/agent.py:23`
**Current:** `model=AgentModels.DEEP_ANALYST_MODEL` (gemini-2.5-pro)
**Proposed:** `model=AgentModels.DEFAULT_FAST_MODEL` (gemini-2.5-flash)

**Rationale:** This agent takes a competitor brief (structured text, ~2KB) and generates a positioning JSON. It doesn't use tools or grounding — it's pure synthesis from pre-gathered data. Flash's reasoning capability at the 2.5 generation is strong enough for this structured comparison task.

**Savings:** ~$0.033 per analysis
- Input: (1.25 - 0.30) × 5K / 1M = $0.005
- Output: (10.00 - 2.50) × 3K / 1M = $0.023
- Plus reduced latency

**Risk:** Medium. The "threat_level" scoring and "strategic_advantages" generation benefit from deeper reasoning. **Monitor quality** after switching — if competitive reports become generic, revert to Pro.

**Compromise:** Keep Pro for now but mark as "evaluate after Flash quality check."

---

### OPT-5: SEO Auditor — Keep Pro but Reduce Grounding

**File:** `backend/agents/seo_auditor/agent.py`

The SEO Auditor is the one agent that genuinely benefits from Pro's deeper reasoning across 5 audit categories. **Keep it on Pro.** But optimize grounding:

**Current:** Agent makes 3-5 Google Search calls (site: indexing, brand authority, competitor comparison).

**Proposed:**
- **Cache PageSpeed results** in Firestore with a 7-day TTL per URL. Lighthouse scores don't change daily.
- **Reduce search queries** to 2 max: one `site:` query for indexing, one brand query for authority. Remove competitor comparison searches (that's the CompetitiveAnalyzer's job).

**Savings:** 1-3 fewer grounding calls → **$0.035-$0.105 per analysis**

---

### OPT-6: Leverage Implicit Caching for Discovery Fan-Out

**Opportunity:** All 6 Stage 2 discovery agents receive the **same 30KB of rawSiteData** injected via `_with_raw_data()`. Because they run in parallel with the same session, Gemini's **implicit caching** should already be providing some savings — but you can maximize this by:

1. **Using explicit caching** for the rawSiteData prefix. Create a cached context with the raw crawl data, then reference it in all 6 sub-agent calls. This guarantees a **90% discount** on the shared ~30K input tokens across 6 agents.

2. **Implementation sketch:**
```python
from google import genai

# After SiteCrawlerAgent completes:
cache = client.caches.create(
    model="gemini-2.5-flash",
    contents=[raw_site_data_content],
    config={"ttl": "300s"},  # 5 minutes, enough for fan-out
)
# Then pass cache reference to each sub-agent call
```

**Savings estimate:**
- Current: 6 agents × 30K tokens × $0.30/1M = $0.054
- With caching: 1 × 30K × $0.30/1M (initial) + 5 × 30K × $0.03/1M (90% off) = $0.014 + storage
- **Net savings: ~$0.036 per analysis** (minus negligible storage for 5-min TTL)

**Risk:** Low. Requires ADK compatibility with cached contexts — may need to use raw `genai.Client` calls instead of `LlmAgent`.

---

### OPT-7: Batch Processing for Non-Interactive Pipelines

**Gemini Batch API** offers a **50% discount** on all models for asynchronous processing.

**Candidates for batch mode:**
- Marketing Swarm (already runs as a background task via `asyncio.create_task`)
- Margin Surgery pipeline (called from `/api/analyze`, response can be async)
- Traffic Forecaster synthesis step

**Savings:** 50% off token costs for batched agents. On Flash: $0.15/$1.25 instead of $0.30/$2.50.

**Trade-off:** Higher latency (batch responses may take minutes). Only viable for pipelines where the user isn't waiting for a real-time response.

---

## 3. Summary: Projected Savings

| Optimization | Per-Analysis Savings | Difficulty | Risk |
|---|---|---|---|
| **OPT-1:** CompetitorAgent Pro→Flash | $0.050 | Easy | Low |
| **OPT-2:** Flash-Lite for 7 extraction agents | $0.033 | Easy | Low |
| **OPT-3a:** Remove grounding from Theme/Contact | $0.070-$0.140 | Easy | Low |
| **OPT-3b:** Consolidate Social searches to 1 | $0.070-$0.210 | Medium | Medium |
| **OPT-3c:** Cache LocatorAgent results | $0.035 × repeat% | Easy | Low |
| **OPT-3d:** Free-tier grounding budget | Variable | Medium | Low |
| **OPT-4:** MarketPositioning Pro→Flash | $0.033 | Easy | Medium |
| **OPT-5:** SEO Auditor grounding reduction | $0.035-$0.105 | Easy | Low |
| **OPT-6:** Explicit caching for discovery fan-out | $0.036 | Medium | Low |
| **OPT-7:** Batch API for background tasks | 50% of batch tokens | Medium | Low |
| **Total (conservative)** | **$0.36-$0.64** | | |

**Current cost per analysis:** $0.89-$1.36
**Optimized cost per analysis:** $0.35-$0.72
**Reduction: ~47-60%**

At 1,000 analyses/month: **$540-$640 saved per month**.

---

## 4. Implementation Priority

### Phase 1 — Quick Wins (1-2 hours, no quality risk)
1. OPT-1: Change CompetitorAgent to Flash
2. OPT-3a: Remove grounding from ThemeAgent and ContactAgent
3. OPT-5: Cache PageSpeed results, reduce SEO search queries

### Phase 2 — Model Tier Restructuring (half day)
4. OPT-2: Add `BUDGET_FAST_MODEL` config, migrate 7 agents to Flash-Lite
5. OPT-3b: Consolidate SocialMediaAgent to single search query

### Phase 3 — Infrastructure (1-2 days)
6. OPT-3c: LocatorAgent result caching
7. OPT-3d: Grounding budget counter + graceful degradation
8. OPT-6: Explicit context caching for discovery fan-out

### Phase 4 — Async Optimization (1 day)
9. OPT-7: Migrate Marketing Swarm + Margin Surgery to Batch API

---

## 5. External API Cost Summary (Non-Gemini)

| Service | Cost | Status | Action Needed |
|---|---|---|---|
| BLS API | Free | Cached 7 days | None — already optimized |
| FRED API | Free | Cached 30 days | None — already optimized |
| NWS Weather | Free | Cached 6 hours | None — already optimized |
| PageSpeed Insights | Free (25K/day) | Not cached | **Add 7-day Firestore cache** |
| Google Geocoding | $5/1K requests | Fallback to Nominatim | Already has free fallback |
| Google Places | $200/mo free credit | UI autocomplete only | Monitor usage |
| Nominatim (OSM) | Free | Geocoding fallback | None |
| Crawl4AI | Self-hosted | Infrastructure cost | None |
| Playwright | Free (library) | Infrastructure cost | None |
| Firestore | $0.06/100K reads | Caching layer | Monitor — increased caching = more reads |

**Key insight:** All market data APIs (BLS, FRED, NWS) are already free and cached. The cost optimization problem is almost entirely a **Gemini model tier + grounding** problem.

---

## 6. Monitoring Recommendations

After implementing optimizations, track:

1. **Grounding calls per day** — Stay under 500 (free) or 1,500 (paid) to avoid $35/1K charges
2. **Model-tier distribution** — Verify Flash-Lite agents produce acceptable quality
3. **Cache hit rates** — Commodity (target >80%), Weather (target >60%), PageSpeed (new, target >70%)
4. **Per-analysis cost** — Log total Gemini API spend per analysis run to BigQuery for trending

---

## References

- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini 2.5 Flash-Lite Documentation](https://deepmind.google/models/gemini/flash-lite/)
- [Grounding with Google Search](https://ai.google.dev/gemini-api/docs/google-search)
- [Context Caching Guide](https://ai.google.dev/gemini-api/docs/caching)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
