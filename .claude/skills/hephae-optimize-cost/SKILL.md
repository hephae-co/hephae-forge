---
name: hephae-optimize-cost
description: Audit and optimize Gemini API costs — identifies context caching opportunities, batch API candidates, model tier downgrades, thinking mode reductions, prompt bloat, and token waste. Produces a cost reduction plan with estimated savings.
argument-hint: [all | pulse | agents | discovery | blog]
---

# Gemini API Cost Optimizer

You are a cost optimization engineer auditing the Hephae codebase for Gemini API token waste. Your job is to find every opportunity to reduce API costs without degrading output quality.

**The levers (ranked by impact):**
1. **Batch API** — 50% flat discount on any call that can tolerate 24h latency
2. **Context caching** — up to 90% savings on cached input tokens
3. **Model tier downgrade** — Flash-Lite ($0.25/1M) vs Flash ($0.50/1M) vs Pro ($2.00/1M)
4. **Thinking mode reduction** — DEEP (8192 tokens) vs HIGH vs MEDIUM vs None
5. **Prompt compression** — shorter prompts = fewer input tokens
6. **Structured output** — `output_schema` vs "Return JSON" in prompt (saves parsing tokens)
7. **Response format** — concise formats for chaining, detailed for final output only

## Input

- `all` → audit everything
- `pulse` → audit pulse pipeline (biggest cost center: 19 industries × 4 stages × weekly)
- `agents` → audit capability agents (discovery, SEO, traffic, competitive, margin, social)
- `discovery` → audit discovery pipeline
- `blog` → audit blog writer

Arguments: $ARGUMENTS

---

## PHASE 0: FETCH PRICING REFERENCE

Before reading code, fetch the current Gemini pricing:

```
WebFetch: https://ai.google.dev/gemini-api/docs/pricing
```

**Current pricing (March 2026):**

| Model | Input/1M | Output/1M | Cached Input | Batch Discount |
|-------|----------|-----------|-------------|----------------|
| gemini-3.1-flash-lite-preview | $0.25 | $1.50 | $0.025 (90% off) | 50% |
| gemini-3-flash-preview | $0.50 | $3.00 | $0.05 (90% off) | 50% |
| gemini-3.1-pro-preview | $2.00 | $12.00 | $0.20 (90% off) | 50% |
| gemini-2.5-flash | $0.30 | $2.50 | $0.03 (90% off) | 50% |

**Context caching storage:** $1.00/1M tokens/hour
**Context caching minimum:** 1,024 tokens (Flash), 4,096 tokens (Pro)
**Implicit caching:** Auto-enabled for Gemini 2.5+ — no code needed, savings when cache hits

**Key insight:** Thinking tokens are OUTPUT tokens charged at output rates. DEEP (8192 budget) can cost 5-10x more than MEDIUM per call.

---

## PHASE 1: READ THE CODEBASE

### 1a. Model Configuration
Read:
- `lib/common/hephae_common/model_config.py` — which models are PRIMARY, FALLBACK, SYNTHESIS
- `apps/api/hephae_api/config.py` — AgentVersions

### 1b. All Agent Definitions
```bash
grep -rn "AgentModels\.\|model=\|ThinkingPresets\.\|thinking" agents/ --include="*.py" | grep -v __pycache__
```

### 1c. Prompt Sizes
For each agent, estimate prompt size:
```bash
# Find large prompts
for f in agents/hephae_agents/*/prompts.py agents/hephae_agents/*/agent.py; do
  if [ -f "$f" ]; then
    chars=$(wc -c < "$f")
    echo "$chars $f"
  fi
done | sort -rn | head -20
```

### 1d. Call Frequency
Estimate how often each agent runs per week:
- Pulse pipeline: 19 industries × 1/week + N zipcodes × 1/week
- Discovery: on-demand, ~5-10 businesses per job
- Blog: on-demand, ~1-2 per week
- Capabilities (SEO, traffic, etc.): per-business, ~50-100 per week

### 1e. Batch API Usage
```bash
grep -rn "batch_generate\|submit_vertex_batch" apps/ lib/ --include="*.py" | grep -v __pycache__
```

---

## PHASE 2: COST ANALYSIS

### 2a. Estimate Current Weekly Cost

For each agent, compute:
```
Weekly cost = (calls/week) × (input_tokens/call × input_price + output_tokens/call × output_price)
```

Estimate tokens per call:
- Small prompt + short response: ~2K input, ~500 output
- Medium prompt (with data context): ~5-10K input, ~1K output
- Large prompt (pulse synthesis with DEEP thinking): ~15K input, ~5K output (including thinking tokens)
- Blog writer (DEEP thinking): ~20K input, ~8K output

### 2b. Build Cost Table

| Agent/Pipeline | Model | Thinking | Calls/Week | Est. Input Tokens | Est. Output Tokens | Weekly Cost |
|---------------|-------|----------|------------|-------------------|--------------------| ------------|
| Pulse: Data Gatherer (19 industries) | PRIMARY | None | 19 | — (no LLM) | — | $0 |
| Pulse: Domain Experts (3 × 19) | PRIMARY | None | 57 | ~5K each | ~2K | $X |
| Pulse: Synthesis (Gemini + Claude) | SYNTHESIS | HIGH/DEEP | 38 | ~15K each | ~5K | $X |
| Pulse: Critique | SYNTHESIS | MEDIUM | 19 | ~10K | ~2K | $X |
| Pulse: Rewrite (if critique fails) | SYNTHESIS | DEEP | ~5 | ~15K | ~5K | $X |
| Industry Pulse: Trend Summary (19) | PRIMARY | None | 19 | ~3K | ~1K | $X |
| Discovery: 13 sub-agents per business | PRIMARY | None/HIGH | ~650 | ~3K each | ~1K | $X |
| Capabilities (SEO, traffic, etc.) | PRIMARY | DEEP/None | ~200 | ~5K each | ~3K | $X |
| Evaluators (4 per business) | PRIMARY | MEDIUM | ~200 | ~5K each | ~500 | $X |
| Blog writer | PRIMARY | DEEP | ~2 | ~20K | ~8K | $X |

**Fill in actual numbers** by reading prompts and estimating token counts.

---

## PHASE 3: OPTIMIZATION CHECKS

### Check 1: Batch API Opportunities (50% savings)

Any LLM call that:
- Doesn't need real-time response
- Processes multiple items with same prompt structure
- Can tolerate hours of latency

**Candidates in Hephae:**
- Industry pulse trend summaries (19 industries, same prompt, weekly batch → 50% savings)
- Pulse domain expert reports (57 calls, same structure → could batch)
- Evaluator runs during workflow (4 evals per business, can batch across businesses)
- Blog critique (not time-sensitive)

Check: `grep -rn "batch_generate" apps/ | grep -v __pycache__` — are these using batch or sequential?

### Check 2: Context Caching (up to 90% savings)

Cache candidates are prompts with:
- Large static instruction (>1024 tokens for Flash, >4096 for Pro)
- Called repeatedly with different data but same instructions
- Instruction doesn't change between calls

**High-value cache candidates:**
- Pulse synthesis prompt (same instruction for all 19 industries — only data changes)
- Discovery sub-agent prompts (13 agents with same instructions, different businesses)
- Evaluator prompts (4 evaluators with same criteria, different outputs)
- Blog writer instruction (large static prompt, called repeatedly)

Check: is `cached_content` parameter used anywhere? If not, estimate savings.

### Check 3: Model Tier Downgrades

| Current | Could Downgrade? | Savings | Risk |
|---------|-----------------|---------|------|
| SYNTHESIS (3-flash/Pro) for pulse | PRIMARY (flash-lite) for domain experts | 50-80% | Lower quality domain reports |
| PRIMARY for evaluators | Flash-Lite | 50% | Evaluators are simple pass/fail — Flash-Lite may suffice |
| PRIMARY for discovery sub-agents | Flash-Lite for simple extraction agents | 50% | Theme, maps, news agents are simple |
| DEEP thinking for blog | HIGH thinking | ~40% output token savings | Slightly less creative |

### Check 4: Thinking Mode Optimization

Thinking tokens are OUTPUT tokens — expensive. DEEP (8192 budget) can use 5-10x the output tokens of MEDIUM.

| Agent | Current Thinking | Justified? | Recommendation |
|-------|-----------------|-----------|----------------|
| Pulse synthesis | HIGH | Yes — complex cross-signal reasoning | Keep |
| Pulse critique | MEDIUM | Yes — needs evaluation reasoning | Keep |
| Blog writer | DEEP | Maybe — could try HIGH | Test HIGH, compare quality |
| SEO auditor | DEEP | Maybe — audit is structured, not creative | Test HIGH |
| Area summary | DEEP | Yes — synthesizing multiple sources | Keep |
| Competitive analysis | HIGH | Yes — market positioning needs reasoning | Keep |
| Industry analyst | DEEP | Maybe — could be HIGH | Test |
| Evaluators (4) | MEDIUM | Maybe — pass/fail is simple | Test None |
| Discovery competitor agent | HIGH | Maybe — could be MEDIUM | Test |

### Check 5: Prompt Bloat Detection

For each agent prompt:
1. Count characters/tokens
2. Identify repeated sections (same text in multiple prompts)
3. Find examples or instructions that could be shorter
4. Check for redundant "Return JSON" instructions when `output_schema` is set

```bash
# Largest prompt files
find agents/ -name "prompts.py" -exec wc -c {} \; | sort -rn | head -10
```

### Check 6: Duplicate LLM Calls

Find cases where the same data is processed by multiple agents unnecessarily:
- Are there agents that re-read the same data with slightly different prompts?
- Are there sequential agents that could be merged into one?
- Are there agents that run but their output is never used?

### Check 7: Output Token Waste

- Agents returning verbose text when a structured JSON would suffice
- Agents returning full analysis when only a score/decision is needed
- Blog critique returning detailed rewrite instructions when a PASS/FAIL would suffice

### Check 8: Cron Frequency Optimization

- Are any crons running more often than needed?
- Could weekly pulses be biweekly for low-traffic industries?
- Could industry pulses be cached and reused for 2 weeks instead of 1?

### Check 9: Claude Model Cost

Verify CLAUDE_SYNTHESIS_MODEL is the cheapest viable option:
```bash
grep -n "CLAUDE_SYNTHESIS_MODEL" lib/common/hephae_common/model_config.py
```

**Pricing comparison:**
| Model | Input/1M | Output/1M | Use Case |
|-------|----------|-----------|----------|
| claude-haiku-4-5-20251001 | $0.80 | $4.00 | Dual-synthesis secondary (recommended) |
| claude-sonnet-4-20250514 | $3.00 | $15.00 | Only if Haiku quality is insufficient |

Flag if using Sonnet when Haiku would suffice (dual-synthesis where Gemini is primary).

### Check 10: Cron Batch API Coverage

For each cron that makes LLM calls, check if it uses batch processing:
```bash
for f in apps/api/hephae_api/routers/batch/*.py; do
  echo "=== $(basename $f) ==="
  grep -c "batch_generate\|submit_vertex_batch" "$f" 2>/dev/null || echo "0"
done
```

**Important distinction:**
- `batch_generate()` — concurrent calls with semaphore, **NO cost discount** (just faster)
- `submit_vertex_batch()` — TRUE Vertex AI Batch API with **50% cost discount** (requires GCS)

Flag any cron with sequential LLM calls (`for ... run_agent_to_text`) that could use `batch_generate()`.
Flag high-volume crons (>50 calls) that should use `submit_vertex_batch()` for the 50% discount.

### Check 11: Context Cache Exclusion Rate

Count agents with callable vs static instructions:
```bash
echo "=== Callable instructions (excluded from cache) ==="
grep -rn "instruction=_" agents/ --include="*.py" | grep -v __pycache__ | grep -v "instruction=_.*INSTRUCTION" | wc -l

echo "=== Static string instructions (cached) ==="
grep -rn 'instruction="' agents/ --include="*.py" | grep -v __pycache__ | wc -l
grep -rn 'instruction=[A-Z]' agents/ --include="*.py" | grep -v __pycache__ | wc -l
```

**Target:** < 20% callable instruction rate (currently ~53% before refactoring).

For each callable instruction, check if it could be refactored to:
- Static instruction string (the core prompt)
- `before_model_callback` (dynamic data injection from session.state)

Also verify the pulse pipeline uses `App` with `ContextCacheConfig`:
```bash
grep -n "ContextCacheConfig\|context_cache_config" apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py
```

---

## PHASE 4: ESTIMATE SAVINGS

For each optimization, estimate:

```markdown
| Optimization | Current Cost/Week | Optimized Cost/Week | Savings | Effort |
|-------------|-------------------|---------------------|---------|--------|
| Batch industry pulse summaries | $X | $X/2 | 50% | Low — already uses batch_generate |
| Cache pulse synthesis prompt | $X | $X × 0.1 | 90% | Medium — implement explicit caching |
| Downgrade evaluators to Flash-Lite | $X | $X/2 | 50% | Low — change model= |
| Remove DEEP thinking from evaluators | $X | $X/5 | 80% | Low — change thinking config |
| ... | | | | |
| **TOTAL** | **$X** | **$Y** | **Z%** | |
```

---

## PHASE 5: IMPLEMENTATION PLAN

Rank optimizations by savings/effort ratio. For each:

```markdown
### OPT-{N}: {title} [{HIGH|MEDIUM|LOW} impact, {LOW|MEDIUM|HIGH} effort]
- **Current:** {what happens now}
- **Change:** {specific code change}
- **File:** `{path}:{line}`
- **Estimated savings:** {$/week or %}
- **Risk:** {quality impact}
- **Test plan:** {how to verify no quality regression}
```

---

## PHASE 6: REPORT

Write to `.claude/findings/cost-optimization.md`:

```markdown
# Gemini API Cost Optimization Report
Generated: {date}

## Current Estimated Weekly Cost: ${X}

## Cost Breakdown by Pipeline
| Pipeline | % of Total | Biggest Cost Driver |
|----------|-----------|-------------------|

## Top 10 Optimizations (ranked by savings ÷ effort)
{table with estimated savings per optimization}

## Implementation Plan
{ordered list of changes with estimated cumulative savings}

## Quick Wins (< 1 hour, no quality risk)
{list}

## Medium-Term (requires testing)
{list}

## Long-Term (architectural changes)
{list}
```

---

## Reference: Gemini Pricing Docs

| Doc | URL | Key Info |
|-----|-----|---------|
| Gemini API Pricing | https://ai.google.dev/gemini-api/docs/pricing | Per-model token prices, batch discount, cache pricing |
| Context Caching | https://ai.google.dev/gemini-api/docs/caching | Explicit vs implicit, minimum tokens, TTL, storage cost |
| Vertex AI Pricing | https://cloud.google.com/vertex-ai/generative-ai/pricing | Vertex-specific pricing (different from Developer API) |
| ADK Cost Patterns (41% reduction case study) | https://tomtunguz.com/modernizing-agent-tools-with-google-adk-patterns/ | Unified tools, format control, cache hits |
| ADK Token Minimization | https://github.com/google/adk-python/discussions/2811 | Community patterns for reducing token usage |
| ADK Context Management | https://arjunprabhulal.com/adk-context-management/ | Tiered storage, compression, scoping |
| Cost Visibility (Labels + Tracking) | https://medium.com/google-cloud/improving-cost-visibility-for-gemini-adk-agents-labels-and-token-tracking-0c9f9e4699d9 | BigQuery analytics plugin for token tracking |

## Reference: Cost Reduction Techniques

| Technique | Savings | When to Use | When NOT to Use |
|-----------|---------|-------------|-----------------|
| **Batch API** | 50% flat | Any call tolerating 24h latency | Real-time user-facing calls |
| **Explicit context cache** | Up to 90% on cached tokens | Same large prompt used 5+ times/hour | Prompts that change every call |
| **Implicit cache (auto)** | Variable (0-90%) | Gemini 2.5+ — free, automatic | Older models |
| **Model downgrade** | 50-80% | Simple extraction, classification, pass/fail | Complex reasoning, creative writing |
| **Thinking reduction** | 40-80% output tokens | Structured/simple tasks | Complex synthesis, analysis |
| **Prompt compression** | 10-30% | Verbose instructions, redundant examples | Already concise prompts |
| **Structured output** | 5-15% | JSON responses — eliminates "Return JSON" instruction + parsing tokens | Free-form text output |
| **Format control** | 70-95% | Chain outputs that feed next agent (IDs only, concise) | Final user-facing output |
| **Deduplication** | Varies | Same data processed multiple times | Genuinely different analyses |

## Key Codebase Files

| Area | File |
|------|------|
| Model tiers + Claude model | `lib/common/hephae_common/model_config.py` |
| Model fallback | `lib/common/hephae_common/model_fallback.py` |
| Batch API (batch_generate + submit_vertex_batch) | `lib/common/hephae_common/gemini_batch.py` |
| ADK helpers + default cache config | `lib/common/hephae_common/adk_helpers.py` |
| Pulse orchestrator (biggest cost center) | `agents/hephae_agents/research/pulse_orchestrator.py` |
| Pulse domain experts | `agents/hephae_agents/research/pulse_domain_experts.py` |
| Pulse synthesis agent | `agents/hephae_agents/research/weekly_pulse_agent.py` |
| Industry pulse generator | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| Discovery agents (13 sub-agents) | `agents/hephae_agents/discovery/agent.py` |
| Capability agents | `agents/hephae_agents/seo_auditor/`, `traffic_forecaster/`, etc. |
| Evaluator agents | `agents/hephae_agents/evaluators/` |
| Blog writer | `agents/hephae_agents/social/blog_writer/agent.py` |

## What NOT To Do

- Do NOT recommend removing agents — optimize them instead.
- Do NOT downgrade models without a test plan to verify quality.
- Do NOT skip the cost estimation — raw optimization without numbers is useless.
- Do NOT recommend caching for prompts that change every call (waste of storage cost).
- Do NOT ignore thinking token costs — they're charged at OUTPUT rates, which are 3-6x input rates.
- Do NOT just say "use batch" — verify the call can actually tolerate async processing.
