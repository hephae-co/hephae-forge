# Gemini API Cost Optimization Report
Generated: 2026-03-27

## Current Estimated Weekly Cost: $8.36

Based on: 19 zip-code pulses, 3 industry pulses, ~50 discovered businesses, ~50 capability runs, ~200 evaluations, ~2 blog posts per week.

**Model Pricing Used:**
| Model | Tier | Input/1M | Output/1M |
|-------|------|----------|-----------|
| gemini-3.1-flash-lite-preview | PRIMARY | $0.25 | $1.50 |
| gemini-3-flash-preview | SYNTHESIS | $0.50 | $3.00 |
| claude-sonnet-4-20250514 | CLAUDE | $3.00 | $15.00 |

---

## Cost Breakdown by Pipeline

| Pipeline | Weekly Cost | % of Total | Biggest Cost Driver |
|----------|-----------|-----------|---------------------|
| Pulse (zip-level, 19 zips) | $3.52 | 42% | Claude dual-synthesis ($2.28) |
| Capability Agents (50 businesses) | $2.06 | 25% | SEO Auditor + Social Auditor HIGH thinking |
| Discovery (50 businesses) | $1.56 | 19% | 650 fan-out calls (volume) |
| Evaluators (200 evals) | $0.70 | 8% | MEDIUM thinking on simple pass/fail |
| Other (insights, area, qual, tech) | $0.45 | 5% | AreaSummary DEEP thinking |
| Blog Writer | $0.07 | 1% | Low volume (2/week) |
| **TOTAL** | **$8.36** | **100%** | |

---

## Detailed Cost Table

| Agent/Pipeline | Model | Thinking | Calls/Week | Input Tokens | Output Tokens | Thinking Tokens | Weekly Cost |
|---|---|---|---|---|---|---|---|
| **PULSE PIPELINE** | | | | | | | **$3.52** |
| BaseLayerFetcher | — | — | 19 | — | — | — | $0.00 |
| SocialPulseResearch | PRIMARY | None | 19 | ~3K | ~1K | 0 | $0.04 |
| LocalCatalystResearch | PRIMARY | None | 19 | ~3K | ~1K | 0 | $0.04 |
| PulseHistorySummarizer | PRIMARY | None | 19 | ~5K | ~2K | 0 | $0.08 |
| EconomistAgent | PRIMARY | None | 19 | ~5K | ~2K | 0 | $0.08 |
| LocalScoutAgent | PRIMARY | None | 19 | ~5K | ~2K | 0 | $0.08 |
| GeminiSynthesis | SYNTHESIS | HIGH | 19 | ~15K | ~3K | ~4K | $0.28 |
| **ClaudeSynthesis** | **CLAUDE** | **None** | **19** | **~15K** | **~5K** | **0** | **$2.28** |
| PulseCritique | SYNTHESIS | MEDIUM | 19 | ~10K | ~1K | ~2K | $0.27 |
| PulseRewrite (~25% fail rate) | SYNTHESIS | DEEP | ~5 | ~15K | ~3K | ~8K | $0.37 |
| **INDUSTRY PULSE** | | | | | | | **$0.01** |
| TrendSummarizer | PRIMARY | None | 3 | ~3K | ~1K | 0 | $0.01 |
| **DISCOVERY** | | | | | | | **$1.56** |
| SiteCrawler | PRIMARY | None | 50 | ~3K | ~2K | 0 | $0.19 |
| EntityMatcher | PRIMARY | None | 50 | ~2K | ~500 | 0 | $0.06 |
| 8 Fan-out agents (no thinking) | PRIMARY | None | 400 | ~3K | ~1K | 0 | $0.61 |
| CompetitorAgent | PRIMARY | HIGH | 50 | ~3K | ~1K | ~3K | $0.34 |
| SocialProfiler | PRIMARY | None | 50 | ~3K | ~1K | 0 | $0.11 |
| DiscoveryReviewer | PRIMARY | None | 50 | ~5K | ~2K | 0 | $0.21 |
| QualScanner batch | PRIMARY | None | 50 | ~3K | ~500 | 0 | $0.07 |
| **CAPABILITY AGENTS** | | | | | | | **$2.06** |
| SEO Auditor | PRIMARY | HIGH | 50 | ~8K | ~3K | ~3K | $0.55 |
| Traffic Forecaster | PRIMARY | None/HIGH* | 50 | ~5K | ~3K | ~1.5K | $0.29 |
| Competitive Analyzer | PRIMARY | HIGH | 50 | ~5K | ~3K | ~3K | $0.49 |
| Margin Surgeon | PRIMARY | None | 30 | ~8K | ~4K | 0 | $0.24 |
| Social Media Auditor | PRIMARY | HIGH | 50 | ~5K | ~3K | ~3K | $0.49 |
| **EVALUATORS** | | | | | | | **$0.70** |
| SEO Evaluator | PRIMARY | MEDIUM | 50 | ~5K | ~500 | ~1K | $0.18 |
| Traffic Evaluator | PRIMARY | MEDIUM | 50 | ~5K | ~500 | ~1K | $0.18 |
| Competitive Evaluator | PRIMARY | MEDIUM | 50 | ~5K | ~500 | ~1K | $0.18 |
| Margin Evaluator | PRIMARY | MEDIUM | 50 | ~5K | ~500 | ~1K | $0.18 |
| **INSIGHTS + RESEARCH** | | | | | | | **$0.35** |
| InsightsAgent | PRIMARY | None | 50 | ~5K | ~2K | 0 | $0.21 |
| AreaSummary | PRIMARY | DEEP | 5 | ~8K | ~3K | ~8K | $0.09 |
| IndustryAnalyst | PRIMARY | DEEP | 3 | ~5K | ~2K | ~8K | $0.05 |
| **BLOG WRITER** | | | | | | | **$0.07** |
| ResearchCompiler | PRIMARY | None | 2 | ~8K | ~2K | 0 | $0.01 |
| BlogWriter | PRIMARY | DEEP | 2 | ~15K | ~5K | ~8K | $0.05 |
| SEOEnricher | PRIMARY | None | 2 | ~3K | ~500 | 0 | $0.00 |
| BlogCritique | PRIMARY | MEDIUM | 2 | ~10K | ~1K | ~1K | $0.01 |
| **TECH INTELLIGENCE** | | | | | | | **$0.07** |
| TechScout | PRIMARY | None | 3 | ~5K | ~3K | 0 | $0.02 |

*Traffic Forecaster: ForecastContext has no thinking, ForecastSynthesizer has HIGH.*

---

## Top 10 Optimizations (ranked by savings ÷ effort)

| # | Optimization | Savings/Week | % of Total | Effort | Risk |
|---|---|---|---|---|---|
| **1** | **Drop Claude dual-synthesis** | **$2.28** | **27%** | Low | Medium — quality may dip slightly |
| **2** | Remove thinking from evaluators (MEDIUM→None) | $0.40 | 5% | Low | Low — pass/fail is simple |
| **3** | Downgrade pulse critique SYNTHESIS→PRIMARY | $0.17 | 2% | Low | Low — structured output |
| **4** | Reduce SocialMediaAuditor HIGH→MEDIUM | $0.19 | 2% | Low | Low — structured audit |
| **5** | Reduce CompetitorAgent (discovery) HIGH→MEDIUM | $0.14 | 2% | Low | Low — extraction task |
| **6** | Expand context caching to discovery pipeline | $0.46 | 6% | Medium | None — same output |
| **7** | Shorten evaluator output format | $0.15 | 2% | Medium | None — internal only |
| **8** | Reduce AreaSummary DEEP→HIGH | $0.04 | <1% | Low | Low |
| **9** | Reduce IndustryAnalyst DEEP→HIGH | $0.02 | <1% | Low | Low |
| **10** | Tech intelligence biweekly | $0.03 | <1% | Low | None |
| | **TOTAL SAVINGS** | **$3.88** | **46%** | | |

**Optimized weekly cost: ~$4.48** (down from $8.36)

---

## Implementation Plan

### OPT-1: Drop Claude Dual-Synthesis [HIGH impact, LOW effort]
- **Current:** Pulse orchestrator runs Gemini + Claude in parallel, merges with InsightMerger
- **Change:** Remove `claude_synth` from `DualSynthesis` ParallelAgent. Remove `InsightMerger`. Route `GeminiSynthesis` output directly to `pulseOutput`.
- **File:** `agents/hephae_agents/research/pulse_orchestrator.py:305-322`
- **Estimated savings:** $2.28/week (27% of total)
- **Risk:** Medium — Claude sometimes catches insights Gemini misses. Run A/B test on 2-3 pulses first.
- **Test plan:** Generate 3 pulses with Gemini-only vs dual-model. Compare insight count, specificity, and critique pass rate. If Gemini-only passes critique at >80% rate, ship it.
- **Mitigation:** If quality drops, consider using Claude as a fallback ONLY when Gemini synthesis fails critique (saves ~90% of Claude calls since most pass first time).

### OPT-2: Remove Thinking from Evaluators [MEDIUM impact, LOW effort]
- **Current:** All 4 evaluators use `ThinkingPresets.MEDIUM` (generates ~1K thinking tokens per call)
- **Change:** Remove `generate_content_config=ThinkingPresets.MEDIUM` from all evaluator agents
- **Files:**
  - `agents/hephae_agents/evaluators/seo_evaluator.py:21`
  - `agents/hephae_agents/evaluators/traffic_evaluator.py:38`
  - `agents/hephae_agents/evaluators/competitive_evaluator.py:37`
  - `agents/hephae_agents/evaluators/margin_surgeon_evaluator.py:33`
- **Estimated savings:** $0.40/week
- **Risk:** Low — evaluators produce structured JSON (score + isHallucinated + reasoning). Flash-Lite without thinking should handle this fine.
- **Test plan:** Run batch evals with and without thinking on 10 businesses. Compare score distributions. If scores are within ±5 points, ship it.

### OPT-3: Downgrade Pulse Critique to PRIMARY [LOW impact, LOW effort]
- **Current:** Pulse critique uses SYNTHESIS model (gemini-3-flash-preview) + MEDIUM thinking
- **Change:** Switch to `AgentModels.PRIMARY_MODEL` (keep MEDIUM thinking)
- **File:** `agents/hephae_agents/research/pulse_orchestrator.py:326`
- **Estimated savings:** $0.17/week
- **Risk:** Low — critique produces structured CritiqueResult (pass/fail per insight). PRIMARY model handles structured output well.
- **Test plan:** Compare critique results on 5 pulses. If same insights are flagged, ship it.

### OPT-4: Reduce SocialMediaAuditor HIGH→MEDIUM [LOW impact, LOW effort]
- **Current:** SocialMediaAuditor uses ThinkingPresets.HIGH
- **Change:** Switch to `ThinkingPresets.MEDIUM`
- **File:** `agents/hephae_agents/social/media_auditor/agent.py:75`
- **Estimated savings:** $0.19/week
- **Risk:** Low — audit produces structured JSON with platform scores
- **Test plan:** Run on 5 businesses, compare output structure and quality.

### OPT-5: Reduce Discovery CompetitorAgent HIGH→MEDIUM [LOW impact, LOW effort]
- **Current:** CompetitorAgent (discovery fan-out) uses ThinkingPresets.HIGH
- **Change:** Switch to `ThinkingPresets.MEDIUM`
- **File:** `agents/hephae_agents/discovery/agent.py:245`
- **Estimated savings:** $0.14/week
- **Risk:** Low — competitor extraction is structured data gathering, not creative analysis
- **Test plan:** Compare competitor lists for 10 businesses before/after.

### OPT-6: Expand Context Caching to Discovery Pipeline [MEDIUM impact, MEDIUM effort]
- **Current:** Discovery sub-agents have large shared prompts (30KB prompts.py) called 650×/week. `_DEFAULT_CACHE_CONFIG` in adk_helpers.py should auto-apply, but discovery may use direct LlmAgent instantiation bypassing the App wrapper.
- **Change:** Verify discovery agents go through `adk_helpers.create_app()` or add explicit `ContextCacheConfig` to the discovery App.
- **File:** `agents/hephae_agents/discovery/agent.py` (main agent creation)
- **Estimated savings:** $0.46/week (30% reduction on discovery input tokens)
- **Risk:** None — caching doesn't change output
- **Test plan:** Check cache hit rate in logs after deployment.

### OPT-7: Shorten Evaluator Output Format [LOW impact, MEDIUM effort]
- **Current:** Evaluators return full EvaluationOutput with detailed `reasoning` text (~500 output tokens)
- **Change:** Add `maxTokens` constraint or simplify output schema to just score + isHallucinated + 1-line reason
- **Files:** `agents/hephae_agents/evaluators/*.py` + `hephae_db/schemas.py` (EvaluationOutput)
- **Estimated savings:** $0.15/week
- **Risk:** Low — reasoning is for debugging only, rarely read
- **Test plan:** Verify evaluation.py still parses the simplified output correctly.

### OPT-8: Reduce AreaSummary DEEP→HIGH [LOW impact, LOW effort]
- **Current:** `generate_content_config=ThinkingPresets.DEEP` (8192 budget)
- **Change:** Switch to `ThinkingPresets.HIGH`
- **File:** `agents/hephae_agents/research/area_summary.py:42,65`
- **Estimated savings:** $0.04/week
- **Risk:** Low — area summary is not final user-facing output
- **Test plan:** Compare 2-3 area summaries side-by-side.

### OPT-9: Reduce IndustryAnalyst DEEP→HIGH [LOW impact, LOW effort]
- **Current:** Uses DEEP thinking
- **Change:** Switch to HIGH
- **File:** `agents/hephae_agents/research/industry_analyst.py:19`
- **Estimated savings:** $0.02/week
- **Risk:** Low
- **Test plan:** Compare outputs for 1-2 industries.

### OPT-10: Tech Intelligence Biweekly [LOW impact, LOW effort]
- **Current:** Weekly tech intelligence runs for each industry
- **Change:** Run biweekly (tech landscape doesn't change weekly)
- **File:** Cron schedule configuration
- **Estimated savings:** $0.03/week
- **Risk:** None — tech tools don't change weekly

---

## Quick Wins (< 1 hour, no quality risk)

1. **Remove evaluator thinking** — delete 4 lines of `generate_content_config=ThinkingPresets.MEDIUM`
2. **Downgrade pulse critique to PRIMARY** — change 1 model= line
3. **Reduce CompetitorAgent thinking** — HIGH→MEDIUM, 1 line change
4. **Reduce SocialMediaAuditor thinking** — HIGH→MEDIUM, 1 line change
5. **Reduce AreaSummary thinking** — DEEP→HIGH, 2 line changes
6. **Reduce IndustryAnalyst thinking** — DEEP→HIGH, 1 line change

**Combined quick win savings: ~$0.96/week (11%)**

## Medium-Term (requires A/B testing)

1. **Drop Claude dual-synthesis** — $2.28/week savings, needs quality comparison
2. **Expand context caching to discovery** — verify App wrapper applies caching
3. **Shorten evaluator output format** — schema change, verify downstream compatibility

**Combined medium-term savings: ~$2.89/week (35%)**

## Long-Term (architectural changes)

1. **Batch API for industry pulses** — when industries grow to 10+, use Vertex AI Batch API (50% discount) for trend summaries. Currently only 3 industries, not worth the infra.
2. **Streaming pulse synthesis** — replace dual-model with single model + streaming critique. Run critique IN the synthesis prompt as a self-check (saves a separate LLM call).
3. **Tiered pulse frequency** — high-activity zips weekly, low-activity biweekly. Requires activity scoring.
4. **Prompt compression** — discovery prompts.py is 30KB. Could reduce by 20-30% by removing verbose examples and redundant instructions. Low ROI at current volume.
5. **Token tracking pipeline** — add BigQuery analytics plugin for actual token counts per agent. Current estimates are rough; real data enables precise optimization.

---

## Scaling Projections

At current volume ($8.36/week), costs are modest. But costs scale linearly:

| Scale | Zips | Industries | Businesses/wk | Est. Weekly Cost | With Optimizations |
|-------|------|-----------|---------------|-----------------|-------------------|
| Current | 19 | 3 | 50 | $8.36 | $4.48 |
| 2× growth | 40 | 6 | 100 | ~$17 | ~$9 |
| 5× growth | 100 | 10 | 250 | ~$42 | ~$22 |
| 10× growth | 200 | 15 | 500 | ~$84 | ~$45 |

**Key scaling risks:**
- Claude dual-synthesis scales at $0.12/zip/week — at 100 zips = $12/week just for Claude
- Discovery fan-out scales at ~$0.03/business — at 500 businesses = $15/week
- Batch API becomes critical at 10× scale (50% discount on async calls)

---

## What's Already Working Well

1. **Batch processing** in pulse_batch_processor.py — 4-stage batch with Vertex AI fallback
2. **Context caching** via `_DEFAULT_CACHE_CONFIG` in adk_helpers.py — applied to all App instances
3. **Structured output** (output_schema) on 15+ agents — eliminates "Return JSON" parsing overhead
4. **Model fallback** via `fallback_on_error` — prevents wasted retries on rate limits
5. **PRIMARY model default** — flash-lite ($0.25/1M) for most agents, SYNTHESIS only where needed

---

## Methodology

- Token estimates based on prompt character counts (÷4 for rough token count) + expected output length
- Thinking token estimates: MEDIUM ~1K, HIGH ~3K, DEEP ~8K (based on budget limits)
- Call frequency based on: 19 registered zip codes, 3 industries, ~50 new businesses/week, ~2 blogs/week
- Costs rounded to nearest cent; actual costs may vary ±30% based on actual token usage
- Claude pricing from Anthropic's published rates (March 2026)
- Gemini pricing from Google AI Developer API (March 2026)
