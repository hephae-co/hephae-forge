# Unified Pipeline Design — Qualification + Industry Intelligence

**Author**: Hephae Engineering
**Date**: 2026-03-14
**Status**: Unified Architecture — Ready for Review
**Depends On**: `qualification-pipeline-design.md` (v5), `industry-intelligence-skill-design.md`

This document unifies the qualification pipeline and industry intelligence skill into a single coherent system architecture. It resolves overlaps, clarifies integration points, and presents the combined system as one design.

---

## 1. The Problem (Combined)

The current pipeline has three compounding failures:

**Cost**: Every business gets the same expensive 12-agent deep discovery regardless of viability. The Nutley canary wasted 168 Gemini calls on businesses that failed viability.

**Genericity**: A barber shop, bakery, and restaurant all get the same qualification signals, scoring weights, agent instructions, and outreach pitch. An analytics pixel is strong for restaurants but meaningless for barbers. Instagram is the portfolio platform for barbers but secondary for bakeries.

**Amnesia**: Every workflow starts from zero. Insights from analyzing 50 bakeries in Essex County are unavailable when analyzing bakeries in Hudson County. The system rediscovers patterns that prior runs already revealed.

**Goal**: Build a pipeline that is cheap (qualify before spending), vertical-aware (industry-specific intelligence), and compounding (gets smarter with every run).

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  INDUSTRY INTELLIGENCE SKILL (single ADK skill, N config packages)     │
│                                                                         │
│  Config Loader ──→ loads vertical config (restaurants/barbers/bakeries) │
│  Knowledge Tools ──→ 4 ADK FunctionTools for accumulated intelligence  │
│  Friction Detector ──→ deterministic keyword scanner per vertical       │
│  Calibration Agent ──→ periodic, updates benchmarks from outcomes       │
│                                                                         │
│  Provides: signal weights, agent instructions, capability selection,   │
│            pitch angles, knowledge tools, friction keywords             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ parameterizes everything below
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  TIER 0 + TIER 1 (parallel)                                           │
│  Research (area + sector + zipcode) + Broad Scan (OSM + ADK + Hub)    │
│  Both must complete before Tier 2                                      │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
           Has website URL            No website URL
                    │                         │
                    ▼                         ▼
┌──────────────────────────────┐  ┌─────────────────────────────┐
│  TIER 2: QUALIFICATION       │  │  Digital Footprint Proxy     │
│  Step A: Metadata Scan       │  │  High ratings + reviews?     │
│  Step B: Full Probe (if amb.)│  │  On aggregators?             │
│  Hybrid Classifier           │  │  Friction keywords detected? │
│                              │  │                              │
│  Scoring uses:               │  │  → QUALIFIED_ACTION_REQUIRED │
│  - Industry config weights   │  │    ("Get a Website" track)   │
│  - Market benchmarks (Tier0) │  │  → Or PARKED                 │
│  - Signal effectiveness data │  └─────────────────────────────┘
│  - Dynamic threshold         │
│  - Friction detection        │
└──────────────┬───────────────┘
               │
      ┌────────┼──────────┐
      │        │          │
  QUALIFIED  PARKED  DISQUALIFIED
      │
      ▼
┌────────────────────────────────────────────────────────────────────────┐
│  TIER 3: DEEP DISCOVERY (industry-parameterized)                      │
│  Capability agents selected by industry config                        │
│  Agent instructions injected from config + knowledge tools registered │
│  Probe data from Tier 2 reused (State-First pattern)                  │
│  Staggered Cloud Tasks, separate Cloud Run service                    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  EVALUATION + OUTCOME RECORDING                                       │
│  Record Outcome tool writes to knowledge store per-business           │
│  Feeds the compounding loop                                           │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  OUTREACH (industry-parameterized)                                    │
│  Pitch angles from config, evidence from probe + discovery signals    │
│  Exemplars from knowledge store strengthen the pitch                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The Industry Intelligence Skill

### One Skill, N Config Packages

A single ADK skill. Restaurants, barbers, bakeries are config packages that parameterize it — not separate skills. Improvements to the knowledge system automatically benefit every vertical.

### What It Provides

| Capability | Description |
|-----------|-------------|
| **Config Loader** | Loads industry-specific YAML config: signal weights, platform lists, agent selection, pitch angles, friction keywords |
| **Knowledge Tools** | 4 ADK FunctionTools for on-demand access to accumulated intelligence |
| **Friction Detector** | Deterministic keyword scanner, parameterized per vertical's friction keywords |
| **Calibration Agent** | Periodic LlmAgent that reads outcomes, updates benchmarks, curates exemplars |
| **Hook Registration** | Optional per-vertical pure functions registered as additional FunctionTools |

### Core Design Principles

**Agents query knowledge, Python doesn't pre-render it.** Knowledge is exposed as ADK FunctionTools that agents call on demand. If an SEO agent needs market benchmarks, it calls the benchmark tool. If it doesn't need them, it skips the call. The agent reasons about what it needs.

**Deterministic where possible, agentic where necessary.** HTML parsing, chain detection, pixel detection, scoring arithmetic — all stay as deterministic pure functions. The LLM is involved only where judgment is required: HVT classifier, capability agents, evaluation, calibration.

**Cold start graceful degradation.** When no accumulated knowledge exists, knowledge tools return empty results. Agents rely entirely on static instructions from the industry config. The system works on day one; it just gets better over time.

---

## 4. Industry Config Packages

Each config package is a directory containing a YAML config file and an optional hooks file. The config is purely declarative — data that parameterizes the skill, no logic.

### Config Defines:

**Qualification parameters:**
- Signal weight multipliers (boost Instagram for barbers, boost aggregator escape for restaurants)
- Platform lists indicating tech adoption for this vertical
- Aggregator lists where this vertical leaks revenue
- "Innovation Gap" definition for this vertical
- Vertical-specific fast-qualify rules
- Additional chain names beyond the shared national list
- No-website qualification thresholds
- Operational friction keywords for the friction detector

**Analysis parameters:**
- Which capability agents to run and which to skip
- Industry-specific instruction text for each active agent (static baseline knowledge)
- For barbers: SEO focuses on local pack + GBP, social focuses on Instagram portfolio, booking agent quantifies no-show costs
- For restaurants: full suite including menu analysis, margin surgery, aggregator cost analysis

**Outreach parameters:**
- Primary pain points ranked by severity
- Pitch angle definitions with required evidence signals

**Research parameters:**
- Which demographic/economic indicators matter most
- What "saturation" means in concrete numbers (8 barber shops/zip = saturated; 8 restaurants = moderate)

### Vertical Selection

| Vertical | Why | Config Challenge |
|----------|-----|-----------------|
| **Restaurants** | Pipeline most mature, richest dataset, validates qualification accuracy + knowledge loop | Most complex config: aggregator escape, menu signals, commodity pricing |
| **Barbers** | Stress test — fundamentally different signal profile (booking-centric, portfolio-driven, no food chain) | Must work without pipeline code changes, validates abstraction |
| **Bakeries** | Bridge between food and non-food, inherits from restaurants with adjustments | Fastest to build, tests whether similar verticals diverge cleanly via config alone |

### Sequencing

1. **Restaurants first** — battle-test the full system against the richest existing dataset
2. **Barbers second** — if the barber config requires any pipeline code changes, the abstraction is wrong
3. **Bakeries third** — should be the fastest vertical, borrowing heavily from restaurant config

All three config directories exist as skeletons from day one. Only restaurants need full config at initial launch.

---

## 5. Knowledge System

### Knowledge Store Structure

Organized by industry and geography. Four types of accumulated data:

**Market Benchmarks**: Aggregate statistics for an industry in a county — dominant platforms, median star rating, average qualification score, viability rate, common pain points, sample size, scanned zipcodes. Updated incrementally after each workflow.

**Signal Effectiveness**: Per-signal viability rates — how often each qualification signal (e.g., "has Instagram," "uses Booksy") appeared on businesses that ultimately passed deep discovery as viable. Allows signal weights to be calibrated empirically.

**Exemplars**: Curated top-performing business profiles from prior runs. Each stores: qualification score, platform, signals present, star rating, review count, gaps found, pitch angle used, and demographic context (income bracket, population density tier from Tier 0 research). Agents query exemplars to find comparable businesses.

**Outcomes**: Raw per-business outcome log. For every business completing deep discovery: qualification score, signals present, viability result, failure reason, gaps found. Input data for the calibration agent. Written per-business (not per-workflow) so partial workflow crashes don't lose data.

### 5 Knowledge Tools (ADK FunctionTools)

| Tool | Input | Returns | Who Calls It |
|------|-------|---------|--------------|
| **Get Market Benchmarks** | industry, county | Dominant platforms, median ratings, pain points, sample size | Qualification scorer, capability agents, outreach agent |
| **Find Similar Exemplars** | industry, county, optional filters | 2-3 anonymized business profiles matching criteria | Capability agents (pattern matching), outreach agent (pitch angle selection) |
| **Get Signal Effectiveness** | industry, county | Per-signal viability correlation data | Qualification scorer (weight calibration), HVT classifier (ambiguous reasoning) |
| **Record Outcome** | full business result profile | Writes to outcomes collection | Evaluation agent (after each business completes) |
| **Detect Operational Friction** | text, industry | Matched friction keywords + sources | Qualification scorer, outreach agent |

**Why tools, not pre-injected context**: Not every agent needs benchmarks for every business. A barber shop with obvious signals (Booksy + Instagram + 4.8 stars) doesn't need market comparison. A borderline case does. The agent decides.

**The friction detector** is deterministic — regex/substring matching against the config's keyword list, zero LLM. Each vertical declares its own keywords:
- Barbers: "long wait," "couldn't get appointment," "no online booking," "had to call"
- Restaurants: "couldn't get a reservation," "phone was busy," "no one answered"
- Bakeries: "sold out," "wish I could pre-order," "gone by the time I got there"

Friction keywords are demand signals that validate pitch angles. A barber with no website but 4.8 stars and 15 reviews mentioning wait times is not just a "Get a Website" lead — it's a "Your customers are telling you they want to book online" lead.

### Cross-Geographic Transfer

Knowledge is stored per county. When local sample size is thin, tools can return data from adjacent counties with similar demographics, flagged as borrowed. Each exemplar stores demographic context so agents can reason about relevance.

In v1, the agent handles this relevance judgment itself based on the metadata. The `find_similar_exemplars` tool returns exemplars with demographic metadata attached — the agent decides how much weight to give them.

---

## 6. Qualification Pipeline (Tier 2) — Industry-Parameterized

### Signal Weight Multipliers

The base scoring from `qualification-pipeline-design.md` (Innovation Gap, contact path, domain, pixels, social, JSON-LD, chain detection) is adjusted by industry config multipliers:

| Signal | Base | Restaurants | Barbers | Bakeries |
|--------|------|-------------|---------|----------|
| Innovation Gap | +30 | 1.0x | 1.0x | 1.0x |
| Contact path | +20 | 1.0x | 0.8x | 1.0x |
| Analytics pixel | +10 | 1.2x | 0.5x | 0.8x |
| Social presence | +10 | 0.8x | 1.5x (Instagram) | 0.8x |
| Platform detected | +10 | 1.2x (Toast) | 1.3x (Booksy) | 1.0x (Square) |
| Aggregator escape | +15 | 1.5x | 0x (N/A) | 1.2x |

### Confidence Curve for Signal Effectiveness Blending

When the qualification scorer has access to signal effectiveness data from the knowledge store:

- Below minimum sample size (~10 businesses): use static config weights only (cold start)
- Above minimum but below confidence threshold (~50): blend config and observed equally
- Above confidence threshold (~100+): lean heavily on observed data, use config as a prior

### Friction Detection in Qualification

If a no-website business has high ratings AND detected friction keywords matching a pitch angle, it qualifies as QUALIFIED_ACTION_REQUIRED with a specialized pitch angle rather than being PARKED. The friction evidence is attached to the qualification decision.

---

## 7. Deep Discovery (Tier 3) — Industry-Parameterized

### Capability Agent Selection by Vertical

| Capability | Restaurants | Barbers | Bakeries |
|-----------|-------------|---------|----------|
| SEO Audit | Yes | Yes (local pack focus) | Yes |
| Social Media Audit | Yes | Yes (Instagram-first) | Yes |
| Menu Analysis | Yes | No | Yes (lighter) |
| Margin Surgery | Yes | No | No |
| Aggregator Cost Analysis | Yes | No | Yes |
| Booking Flow Analysis | No | Yes | No |
| Traffic Forecast | Yes | Yes | Yes |
| Competitive Analysis | Yes | Yes | Yes |

### Agent Instructions from Config

Each active agent receives:
1. **Static instruction text** from the industry config YAML (baseline vertical knowledge)
2. **Knowledge tools** registered as FunctionTools (accumulated data, called on demand)

The agent decides how to use both. For straightforward cases, it relies on static instructions. For unusual cases, it queries exemplars or benchmarks.

### State-First Agent Pattern

Every Tier 3 agent must check `session.state` first. If Tier 2 qualification already found email, social links, or platform info — skip the redundant tool call, validate/format the existing data. Without this enforcement, cost savings from qualification are theoretical.

---

## 8. The Compounding Loop

```
Step 1 — RUN: Pipeline processes businesses for a vertical + zipcode.
                Agents use static config + accumulated knowledge.
                    │
Step 2 — RECORD: As each business completes evaluation,
                  Record Outcome tool writes to knowledge store.
                    │
Step 3 — CALIBRATE: Calibration agent (periodic, every 10 businesses
                     or weekly) reads outcomes, updates benchmarks,
                     recomputes signal effectiveness, curates exemplars,
                     writes qualitative notes about patterns.
                    │
Step 4 — LOAD: Next workflow loads updated benchmarks through
                knowledge tools. Qualification weights are better
                calibrated. Exemplar comparisons are richer.
                    │
Step 5 — IMPROVE: Fewer businesses fail in deep discovery.
                   Analysis is more targeted. Pitch angles
                   grounded in what worked for similar businesses.
                    │
                 └──→ Back to Step 1 (compounds each revolution)
```

**The first run is generic. The fifth run is informed. The twentieth run is precise.**

### Calibration Agent

An ADK LlmAgent that runs on schedule (not per-workflow). It reads raw outcome data and produces:
- Updated benchmark documents
- Updated signal effectiveness statistics
- Qualitative calibration notes about patterns and anomalies
- Curated exemplar set (adding top performers, pruning stale ones)

**Why an agent, not a batch script**: A script sees "low correlation number." An agent reasons about *why* — "these bakeries all use the same Wix template with no customization, indicating low digital investment despite having a website. Content depth is the real differentiator here."

The calibration agent flags discrepancies between static config and observed data for human review. It does NOT auto-modify the config — the config is editorial control that humans own.

---

## 9. Infrastructure

### Cloud Tasks Fan-Out (GCP-Native Rate Limiting)

**Qualification Queue** (`hephae-qualification-queue`):
- `maxDispatchesPerSecond`: 5
- `maxConcurrentDispatches`: 3
- `maxAttempts`: 3 with exponential backoff
- 60-second task timeout

**Discovery Queue** (`hephae-agent-queue`):
- Existing config, 30-minute task timeout
- Staggered scheduling (15s between businesses)

### Separate Cloud Run Services

| Service | Purpose | Timeout | Scaling |
|---------|---------|---------|---------|
| `hephae-qualification` | Tier 2 metadata scan + scoring | 60s | High throughput, low memory |
| `hephae-forge-api` | Tier 3 deep discovery + capabilities | 30 min | Low throughput, high memory |

Mixed latency causes poor autoscaling. Separate services let Cloud Run optimize each independently.

### Barrier Pattern

Qualification Cloud Tasks include a `research_complete` prerequisite check. If area/sector research isn't available in Firestore, the task returns retriable and Cloud Tasks re-dispatches after backoff. Ensures qualification always has full market context.

### Research Staleness Guard

Track `research_generated_at` on research context. If >30 min old at qualification time, log warning. If >60 min, fall back to base threshold.

---

## 10. Qualification Tool Architecture

### Composable Analyzers (Single Fetch, Multiple Parsers)

```
page_fetcher(url) → raw HTML + response headers
     │
     ├── robots_probe(url) ──────── crawl policy check (0-cost)
     ├── domain_analyzer(url) ───── URL classification (no HTTP)
     ├── platform_detector(html) ── Shopify/Wix/Toast/MindBody/Booksy
     ├── pixel_detector(html) ───── FB Pixel, GA, GTM, Hotjar
     ├── contact_path_detector(html, base_url) ── /contact, mailto:
     ├── meta_extractor(html, headers) ── og:type, generator, SSL, JSON-LD
     └── menu_freshness_detector(html) ── last-modified, specials (dining only)
           │
     qualification_scanner ──── orchestrates, aggregates, scores
```

Each analyzer is a pure function. New signals are new tools, not modifications to existing ones.

### Module Structure

```
packages/capabilities/hephae_agents/qualification/
  ├── __init__.py
  ├── page_fetcher.py
  ├── robots_probe.py
  ├── domain_analyzer.py
  ├── platform_detector.py
  ├── pixel_detector.py
  ├── contact_path_detector.py
  ├── meta_extractor.py
  ├── menu_freshness_detector.py
  ├── chain_detector.py
  ├── friction_detector.py
  ├── scorer.py
  └── hvt_classifier.py

packages/capabilities/hephae_agents/industry_intelligence/
  ├── __init__.py
  ├── config_loader.py
  ├── knowledge_tools.py          (4 ADK FunctionTools)
  ├── calibration_agent.py
  └── configs/
      ├── restaurants/
      │   ├── config.yaml
      │   └── hooks.py (optional)
      ├── barbers/
      │   ├── config.yaml
      │   └── hooks.py (walk-in detection)
      └── bakeries/
          └── config.yaml
```

### Shared Models

In `packages/common-python/hephae_common/models.py`:
- `ProbeResult` — aggregated output from all analyzers (versioned with `schemaVersion`)
- `QualificationDecision` — disposition + score + reason + signals
- `HVTClassifierOutput` — flat schema: `{is_hvt: bool, score: int, reason: str}`
- `IndustryConfig` — typed representation of the YAML config
- `MarketBenchmark`, `SignalEffectiveness`, `Exemplar`, `Outcome` — knowledge store models

---

## 11. Qualification Tracks

| Track | Condition | Pipeline Path |
|-------|-----------|---------------|
| **QUALIFIED** | Website + contact + score >= threshold | Full deep discovery (Tier 3) |
| **QUALIFIED_ACTION_REQUIRED** | No website but high reputation + friction signals or aggregator presence | "Get a Website" outreach track |
| **PARKED** | Below threshold, no website, no strong reputation | Stored for future batch |
| **DISQUALIFIED** | Chain, closed, not a business | Never process |

---

## 12. Scoring Summary

### Hard Gate (Before Scoring)

Contact path is mandatory for standard qualification. No contact path → PARKED.

### Base Scoring (100-point scale, adjusted by industry config multipliers)

| Signal | Base Points |
|--------|------------|
| Innovation Gap (platform + marketing gap) | up to +30 |
| Contact path (email/form/mailto) | +20 |
| Custom domain | +15 |
| Not a chain | +15 |
| Analytics pixel | +10 |
| Social presence (2+ links) | +10 |
| JSON-LD structured data | +5 |

### Market-Context Bonuses

| Bonus | Points | Condition |
|-------|--------|-----------|
| Economic Delta | +15 | Wealthy zip + poor digital presence |
| Aggregator Escape | +15 (+30 for Menu Mismatch auto-qualify) | On aggregators but no own website/ordering |
| Friction detected | +10 | Operational friction keywords match a pitch angle |

### Dynamic Threshold

```
Base: 40
Saturated (40+): 60    High (20-40): 50    Moderate (10-20): 40    Underserved (<10): 30
High opportunity (>70): threshold -= 10
```

Saturation definitions come from the industry config (8 barbers = saturated; 8 restaurants = moderate).

### Hybrid Classification

- Rules handle ~80% of cases (free)
- HVT classifier agent handles ~20% ambiguous cases (~$0.001 each, same-model retry, PARKED on failure)

---

## 13. Where MCP Fits (Planned, Not v1)

MCP is not needed for the internal pipeline — agents access the knowledge store through ADK FunctionTools backed by direct Firestore reads.

MCP becomes relevant when external consumers need access:
- Human-facing research dashboard ("What do we know about bakeries in Bergen County?")
- Customer-facing insights ("How do I compare to other barber shops in my area?")
- Third-party integrations

The migration path: build Firestore-backed tools now (clean, self-contained functions with well-defined I/O), wrap them in an MCP server later when there's a consumer.

---

## 14. Success Criteria

1. Adding a new vertical requires ONLY writing a config YAML (and optionally hooks). No pipeline code changes.
2. After 50+ businesses for an industry+county, qualification viability rate exceeds 80% (vs ~46% baseline).
3. Capability agents produce measurably more targeted analysis with accumulated knowledge vs cold start.
4. Calibration agent identifies at least one signal weight miscalibration within first 100 businesses.
5. Cross-geographic knowledge transfer works: new zipcode in a county with existing data produces higher accuracy on first run than cold-start county.

---

## 15. Deferred Enhancements (v2+)

| Enhancement | Why Deferred | What to Do Now |
|-------------|-------------|----------------|
| Socio-Economic Mirror Matching | Needs exemplar volume across counties | Store income bracket + density tier on every exemplar |
| Calibration Auto-Tuning | Needs trust built through human review | Store structured calibration notes (field, current value, observed, sample size, reasoning) |
| Dedicated Review Search Query | Each query adds cost to cheap qualification | Track friction detection source (snippet vs review vs website) to measure if snippets suffice |
| MCP Server for Knowledge Store | No external consumer yet | Keep knowledge tools as clean pure functions, no pipeline internals entangled |
| Cross-Vertical Knowledge Transfer | Needs 50+ outcomes per vertical in overlapping counties | Knowledge store structure already supports cross-industry queries |
| Exemplar-Based Outreach Personalization | Needs outreach response tracking | Include `pitch_angle_used` on every exemplar and outcome |

---

## 16. Cost Model

| Step | Cost | When |
|------|------|------|
| Research (area + sector) | ~$0.05 shared | Once per workflow |
| Broad scan (Tier 1) | ~$0.001 shared | Once per workflow |
| Metadata scan (Step A) | $0 (HTTP) | All with website |
| Full probe (Step B) | $0 (existing tool) | ~30% ambiguous |
| Friction detection | $0 (regex) | All businesses |
| LLM classifier | ~$0.001 each | ~20% ambiguous |
| Knowledge tool queries | $0 (Firestore reads) | On-demand |
| Deep discovery | ~$0.50 each | Only qualified |

**Before (26 biz, generic)**: 26 × $0.50 = $13.00, 46% viability
**After (26 biz, industry-aware)**: 6-10 × $0.50 + $0.05 = $3-5, target >80% viability
**Savings: 60-75% cost, 2x quality**

---

## 17. Verification Plan

1. Deploy as canary, run workflow for 07110 Restaurants (restaurant config)
2. Verify industry config loaded correctly (restaurant-specific signal weights, agent selection)
3. Verify research completes before qualification (barrier pattern)
4. Verify dynamic threshold adapts to market saturation
5. Verify friction keywords detected from available text
6. Verify no-website businesses with friction signals → QUALIFIED_ACTION_REQUIRED
7. Verify chains → DISQUALIFIED
8. Verify only qualified businesses enter deep discovery with restaurant-specific agents
9. Verify probe data reused (State-First pattern, agents skipped)
10. Verify Record Outcome writes to knowledge store after each business
11. Run calibration agent manually, verify benchmark documents created
12. Run second workflow for adjacent zipcode, verify knowledge tools return accumulated data
13. Compare Gemini API calls: target 60%+ reduction
14. Compare viability rate: target >80%
