# Weekly Pulse Pipeline — Implementation Plan

## Context

The Weekly Pulse generates zipcode-level intelligence reports for local businesses. It cross-correlates 15+ data sources into 3-5 ranked insight cards that tell business owners things they **cannot** figure out by walking down the street.

This plan covers two execution modes:
- **Interactive**: Single zip, triggered from UI or admin, completes in ~30-40s
- **Batch**: 100+ zips (county-level), triggered by cron, uses Vertex AI batch prediction

### Existing Infrastructure to Reuse

| Component | File | Reuse |
|-----------|------|-------|
| Inline batch (semaphore=3) | `hephae_common/gemini_batch.py` → `batch_generate()` | Small batches (<100) |
| Vertex AI batch (GCS JSONL) | `hephae_common/gemini_batch.py` → `submit_vertex_batch()` | Large batches (100+) |
| Batch orchestrator | `hephae_api/workflows/batch_runner.py` → `run_batch()` | Prompt collection + submission |
| Cloud Run Job launcher | `hephae_api/lib/job_launcher.py` | Offload heavy batch work |
| Workflow dispatcher | `hephae_api/routers/batch/workflow_dispatcher.py` | Cron-triggered job queue |
| Batch CLI | `apps/batch/hephae_batch/main.py` | Add `pulse-batch` command |
| ADK ParallelAgent pattern | `hephae_agents/research/intel_fan_out.py` | Agent tree architecture |
| Evaluator pattern | `hephae_agents/evaluators/*.py` | Critique agent scoring |
| Data cache (TTL-based) | `hephae_db/firestore/data_cache.py` | Signal caching (ALREADY BUILT) |
| Signal fetchers | `hephae_api/workflows/orchestrators/industry_plugins.py` | 11 fetch wrappers to migrate |
| Social pulse | `hephae_agents/research/social_pulse.py` | `SOCIAL_PULSE_INSTRUCTION` (module-level) |
| Local catalyst | `hephae_agents/research/local_catalyst.py` | `LOCAL_CATALYST_INSTRUCTION` (module-level) |

---

## Part 1: Multi-Agent Reasoning Architecture

### Why Not Single-Pass Synthesis

The current approach feeds 15+ raw JSON blocks into one LLM call. Problems:
1. **"Lost in the middle"** — LLM attention dilutes across too many inputs
2. **Obvious insights leak through** — prompt says "don't be obvious" but LLMs drift
3. **LLM does math** — hallucinated percentages and impact scores
4. **No longitudinal context** — only sees last week, misses slow trends
5. **No quality gate** — output ships regardless of quality

### The Pipeline: 5 Stages

```
┌─────────────────────────────────────────────────────────────────┐
│                    PulseOrchestrator                             │
│                   (SequentialAgent)                              │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Stage 1: DataGatherer (ParallelAgent)                  │     │
│  │  ├─ BaseLayerFetcher (custom BaseAgent — deterministic)│     │
│  │  │   tools: [fetch_weather, fetch_news, fetch_trends,  │     │
│  │  │           fetch_census, fetch_osm, fetch_legal...]  │     │
│  │  ├─ IndustryPluginFetcher (custom BaseAgent)           │     │
│  │  │   tools: [fetch_bls_cpi, fetch_usda, fetch_fda...] │     │
│  │  └─ ResearchFanOut (ParallelAgent)                     │     │
│  │      ├─ SocialPulseResearch (LlmAgent + google_search) │     │
│  │      └─ LocalCatalystResearch (LlmAgent + tools)       │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓ all results in session.state        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Stage 2: PreSynthesis (ParallelAgent)                  │     │
│  │  ├─ PulseHistorySummarizer (LlmAgent — Flash Lite)     │     │
│  │  │   reads: last 12 weeks from Firestore               │     │
│  │  │   output_key: "trendNarrative"                      │     │
│  │  ├─ EconomistAgent (LlmAgent)                          │     │
│  │  │   reads: BLS, Census, IRS, SBA, QCEW, Trends       │     │
│  │  │   output_key: "macroReport"                         │     │
│  │  └─ LocalScoutAgent (LlmAgent)                         │     │
│  │      reads: weather, events, catalysts, legal, social  │     │
│  │      output_key: "localReport"                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Stage 3: Synthesis (LlmAgent — DEEP thinking)          │     │
│  │  WeeklyPulseAgent                                      │     │
│  │  reads: macroReport, localReport, trendNarrative,      │     │
│  │         preComputedImpact, matchedPlaybooks             │     │
│  │  output_key: "pulseOutput"                             │     │
│  │  response_schema: WeeklyPulseOutput                    │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Stage 4: Critique Loop (LoopAgent, max_iterations=2)   │     │
│  │  ├─ PulseCritiqueAgent (LlmAgent)                      │     │
│  │  │   reads: pulseOutput                                │     │
│  │  │   Persona: Cynical Local Business Owner             │     │
│  │  │   Three tests per insight:                          │     │
│  │  │     1. Walking Down the Street (obviousness)        │     │
│  │  │     2. So What? (actionability)                     │     │
│  │  │     3. Show Your Work (cross-signal reasoning)      │     │
│  │  │   output_key: "critiqueResult"                      │     │
│  │  │   → if all pass: escalate=True                      │     │
│  │  │   → if any fail: writes rewriteFeedback to state    │     │
│  │  │                                                     │     │
│  │  └─ (loop back to WeeklyPulseAgent on failure)         │     │
│  │     WeeklyPulseAgent reads state["rewriteFeedback"]    │     │
│  │     and revises only the failing insights              │     │
│  └────────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  Stage 5: Save to Firestore + archive raw signals               │
└─────────────────────────────────────────────────────────────────┘
```

### Stage 1 Design Decision: Custom BaseAgent vs LlmAgent for Data Fetching

Data fetching is deterministic — there's no LLM decision about which APIs to call. Using an `LlmAgent` to dispatch tool calls adds latency, tokens, and unpredictability. Instead, subclass ADK's `BaseAgent`:

```python
class BaseLayerFetcher(BaseAgent):
    """Deterministic parallel data fetcher — no LLM, just tools."""

    async def _run_async_impl(self, ctx: InvocationContext):
        # Call all fetch tools in parallel via asyncio.TaskGroup
        # Write results to ctx.session.state
        # Yield Event with state_delta
```

This participates in ADK's session/state/event system while keeping data fetching deterministic and fast. The fetch functions themselves stay as regular Python async functions with cache-through logic (using the existing `data_cache.py`).

### Pre-Computed Impact Multipliers (Feed to LLM, Don't Let LLM Calculate)

Between Stage 1 and Stage 3, Python computes the numbers. The LLM writes the narrative.

```python
# Computed in the runner before Stage 3:
pre_computed = {
    "dairy_yoy_pct": 12.1,          # from BLS
    "dairy_mom_pct": 3.4,           # from BLS
    "poultry_yoy_pct": -5.3,        # from BLS
    "competitor_count": 14,          # from Census/OSM
    "competitor_delta_3mo": +3,      # from OSM history
    "delivery_adoption_pct": 0.71,   # from OSM category analysis
    "weather_traffic_modifier": -0.15,  # rain historical avg
    "event_traffic_modifier": +0.30,    # street fair historical avg
    "net_traffic_delta": +0.15,         # Python arithmetic
    "median_income_3yr_change_pct": 8.0, # from Census/IRS
}
# Injected into session.state["preComputedImpact"]
# Synthesis prompt: "Use these pre-computed figures. Do not recalculate."
```

### Playbook Registry (Deterministic, Not RAG)

```python
# Static registry — no vector search needed
PLAYBOOKS = {
    "dairy_margin_swap": {
        "trigger_conditions": ["dairy_yoy_pct > 8", "poultry_yoy_pct < 0"],
        "play": "Shift daily specials from cream/cheese-heavy to grilled protein...",
        "variables": ["margin_delta", "substitute_protein", "menu_items_affected"],
    },
    "competitor_delivery_wave": {
        "trigger_conditions": ["delivery_adoption_pct > 0.65"],
        "play": "Launch delivery with first-week promo targeting unserved demand...",
        "variables": ["platform", "promo_discount", "competitor_count"],
    },
    "construction_spillover": {
        "trigger_conditions": ["road_closure_active", "parallel_street_exists"],
        "play": "Capture foot traffic spillover with sidewalk signage...",
        "variables": ["closed_street", "spillover_streets", "duration_weeks"],
    },
    # ... ~20 playbooks total, built over time
}

def match_playbooks(pre_computed: dict, signals: dict) -> list[dict]:
    """Evaluate trigger conditions against pre-computed values."""
    # Returns matched playbooks with variables filled in
```

Matched playbooks are injected into `session.state["matchedPlaybooks"]` before Stage 3. The synthesis prompt says: "Where applicable, map your recommendations to these established plays: {matchedPlaybooks}."

### Critique Agent Detail

The `PulseCritiqueAgent` uses a structured output schema:

```python
class InsightCritique(BaseModel):
    insight_rank: int
    obviousness_score: int    # 0-100, higher = more obvious
    actionability_score: int  # 0-100, higher = more actionable
    cross_signal_score: int   # 0-100, higher = better reasoning
    verdict: str              # "PASS" | "REWRITE" | "DROP"
    rewrite_instruction: str  # specific feedback if REWRITE

class CritiqueResult(BaseModel):
    overall_pass: bool
    insights: list[InsightCritique]
```

**Pass threshold**: Every insight must have `obviousness_score < 30` AND `actionability_score >= 70` AND `cross_signal_score >= 60`. If any insight fails, the critique writes specific `rewrite_instruction` into state and does NOT escalate (triggering a loop iteration).

On the second iteration, the `WeeklyPulseAgent`'s dynamic instruction reads `state["rewriteFeedback"]` and sees the specific failing insights with instructions like: *"Insight #2 'costs are rising' scored 85 on obviousness. Rewrite with specific cross-signal correlation showing which costs, what the delta is vs last month, and what competitor response looks like."*

---

## Part 2: Interactive Mode (ADK-Native)

### How It Runs

```python
async def generate_pulse_interactive(
    zip_code: str, business_type: str, week_of: str = "",
) -> dict:
    """Single-zip pulse generation via ADK agent tree."""

    # 1. Resolve geography (BQ) — same as current
    geo = await resolve_zip_geography(zip_code)

    # 2. Load pulse history for longitudinal context
    history = await get_pulse_history(zip_code, business_type, weeks=12)

    # 3. Build initial session state
    # NOTE: preComputedImpact and matchedPlaybooks are computed INSIDE
    # Stage 1 (BaseLayerFetcher) after signals are fetched, then written
    # to session.state for Stage 3 to read. They cannot be computed here
    # because we don't have the raw signals yet.
    initial_state = {
        "zipCode": zip_code,
        "businessType": business_type,
        "weekOf": week_of or current_iso_week(),
        "city": geo["city"],
        "state": geo["state"],
        "county": geo["county"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
        "dmaName": geo["dma_name"],
        "pulseHistory": [p["signalArchive"] for p in history],  # raw signals
        "pulseHistoryInsights": [p["insights"] for p in history],  # past cards
    }

    # 6. Run ADK agent tree
    session_service = InMemorySessionService()
    runner = Runner(
        agent=pulse_orchestrator,  # the SequentialAgent tree
        app_name="weekly_pulse",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="weekly_pulse",
        user_id="system",
        state=initial_state,
    )

    # Run and collect final state
    final_state = {}
    async for event in runner.run_async(
        user_id="system",
        session_id=session.id,
        new_message=user_msg(f"Generate weekly pulse for {zip_code} ({business_type})"),
    ):
        if event.is_final_response():
            final_state = event.actions.state_delta or {}

    # 7. Post-processing: save pulse + archive signals
    pulse_output = session.state.get("pulseOutput")
    critique = session.state.get("critiqueResult")
    raw_signals = session.state.get("rawSignals")

    await save_weekly_pulse(zip_code, business_type, week_of, pulse_output)
    await save_signal_archive(zip_code, week_of, raw_signals)

    return {"pulse": pulse_output, "critique": critique}
```

### What the Current `weekly_pulse.py` Becomes

The current 463-line file with inline `_fetch_*()` functions and `asyncio.gather()` is **fully replaced** by:
1. The ADK agent tree definition (new file)
2. The `generate_pulse_interactive()` runner function (replaces `generate_pulse()`)
3. Fetch functions move to FunctionTool wrappers (new file)

---

## Part 3: Batch Mode (Vertex AI Batch Prediction)

### Batch Architecture

```
County Batch Pipeline (e.g., Essex County = 47 zip codes)
════════════════════════════════════════════════════════════

Trigger: POST /api/cron/pulse-batch-submit { county, state, businessType }
  → Resolve all zips in county via BQ
  → Create batch work items in Firestore
  → Launch Cloud Run Job

Cloud Run Job executes 5 stages:
──────────────────────────────────

Stage 0: Data Fetch (Python, no LLM)
  Per zip: call all API fetchers with cache-through
  Shared data (county/state scope) fetched ONCE
  Output: raw signals written to work item docs
  Duration: ~30s for 47 zips (most cached)

Stage 1: Research Batch (Vertex Batch Job #1)
  Build 94 prompts (2 per zip: social_pulse + local_catalyst)
  Enable google_search_retrieval grounding in JSONL request
  Submit as ONE Vertex batch job
  Poll for completion
  Parse results, write to work item docs
  Duration: ~2-5 min (Vertex batch processing)

Stage 2: Pre-Synthesis Batch (Vertex Batch Job #2)
  Build 141 prompts (3 per zip: historian + economist + scout)
  No tools needed — pure prompt-in, text-out
  Submit as ONE Vertex batch job
  Parse results, write to work item docs
  Duration: ~2-5 min

Stage 3: Synthesis Batch (Vertex Batch Job #3)
  Build 47 prompts (1 per zip)
  Each prompt includes: macroReport + localReport +
    trendNarrative + preComputedImpact + matchedPlaybooks
  response_schema via generation_config for structured output
  Submit as ONE Vertex batch job
  Duration: ~2-5 min

Stage 4: Critique Batch (Vertex Batch Job #4)
  Build 47 prompts (1 per zip: score the synthesis output)
  Submit as ONE Vertex batch job
  Parse results:
    PASS → save to zipcode_weekly_pulse + signal archive
    FAIL → collect for rewrite batch

Stage 4b: Rewrite Batch (Vertex Batch Job #5, conditional)
  Only failed zips from Stage 4
  Build N prompts with critique feedback injected
  Submit as ONE smaller Vertex batch job
  Save results regardless (mark as critiquePass=false if still failing)

Total duration: ~15-25 min for a full county
Total Vertex batch jobs: 4-5
```

### ID Tracking Across Stages

**Anchor format**: `{batchId}:{zipCode}:{stage}`

```
Batch ID: pulse-essex-2026-W12

Stage 1 request_ids:
  pulse-essex-2026-W12:07110:social_pulse
  pulse-essex-2026-W12:07110:local_catalyst
  pulse-essex-2026-W12:07042:social_pulse
  ...

Stage 2 request_ids:
  pulse-essex-2026-W12:07110:historian
  pulse-essex-2026-W12:07110:economist
  pulse-essex-2026-W12:07110:local_scout
  ...

Stage 3 request_ids:
  pulse-essex-2026-W12:07110:synthesis
  pulse-essex-2026-W12:07042:synthesis
  ...

Stage 4 request_ids:
  pulse-essex-2026-W12:07110:critique
  ...
```

### Batch Work Item Document (Glue Between Stages)

```
Collection: pulse_batch_work_items
Doc ID: pulse-essex-2026-W12:07110

{
  batchId: "pulse-essex-2026-W12",
  zipCode: "07110",
  businessType: "restaurants",
  weekOf: "2026-W12",
  status: "COMPLETED",    // QUEUED | FETCHING | RESEARCH | PRE_SYNTHESIS |
                          //   SYNTHESIS | CRITIQUE | COMPLETED | FAILED

  // Stage outputs — each stage writes its result here
  rawSignals: { ... },           // Stage 0
  socialPulse: "...",            // Stage 1
  localCatalysts: "...",         // Stage 1
  trendNarrative: "...",         // Stage 2
  macroReport: "...",            // Stage 2
  localReport: "...",            // Stage 2
  preComputedImpact: { ... },    // Stage 0 (Python-computed)
  matchedPlaybooks: [ ... ],     // Stage 0 (Python-matched)
  synthesisOutput: { ... },      // Stage 3 (WeeklyPulseOutput)
  critiqueResult: { ... },       // Stage 4

  retryCount: 0,
  lastError: null,
  createdAt: timestamp,
  updatedAt: timestamp,
  expireAt: timestamp,  // Firestore TTL — 14 days after creation
}
```

### Google Search Grounding in Vertex Batch

The existing `submit_vertex_batch()` builds JSONL lines with `contents` and `generation_config`. To support grounding, add an optional `tools` field:

```python
# In gemini_batch.py — submit_vertex_batch() JSONL builder:
line = {
    "request_id": req["request_id"],
    "model": f"publishers/google/models/{model}",
    "contents": req["contents"],
}
if req.get("config"):
    line["generation_config"] = req["config"]
if req.get("tools"):                              # NEW
    line["tools"] = req["tools"]                   # NEW
jsonl_lines.append(json.dumps(line))
```

Research stage prompts include grounding config:
```python
{
    "request_id": "pulse-essex-2026-W12:07110:social_pulse",
    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    "tools": [{"google_search_retrieval": {
        "dynamic_retrieval_config": {"mode": "MODE_DYNAMIC"}
    }}],
    "config": {"response_mime_type": "application/json"},
}
```

### Extending Existing Batch Infrastructure

**Do NOT build a new workflow system.** Extend the existing one:

1. **Add `pulse-batch` command to `apps/batch/hephae_batch/main.py`**:
   ```python
   elif command == "pulse-batch":
       batch_id = sys.argv[2]
       await run_pulse_batch(batch_id)
   ```

2. **Add batch submission endpoint to `hephae_api/routers/batch/`**:
   ```python
   @router.post("/api/cron/pulse-batch-submit")
   async def pulse_batch_submit(req: PulseBatchRequest):
       # Resolve zips in county via BQ
       # Create work item docs in Firestore
       # Launch Cloud Run Job via job_launcher.py
   ```

3. **Reuse `job_launcher.py`** to submit Cloud Run Job with args `["pulse-batch", batch_id]`.

4. **Reuse `gemini_batch.py`** — `submit_vertex_batch()` for large stages, `batch_generate()` for small rewrite batches.

---

## Part 4: Data Retention Strategy

### What Lives Forever

| Data | Why | Location | Est. Size |
|------|-----|----------|-----------|
| Final pulse output (insight cards, headline, quickStats) | The product | `zipcode_weekly_pulse` | ~5KB/zip/week |
| Raw API responses per source per zip per week | Enables retroactive recomputation, weight tuning, new signal backfill, A/B testing synthesis prompts | `pulse_signal_archive` | ~50KB/zip/week |
| Critique scores and pass/fail | Quality tracking over time | Field on pulse doc | <1KB |
| Playbook match history | Measure strategy effectiveness | Field on pulse doc | <1KB |
| Pre-computed impact numbers | Anomaly detection, trend analysis | Field on archive doc | <1KB |

**Storage cost**: 100 zips x 52 weeks x 55KB = ~286MB/year = ~$0.60/year in Firestore.

### What Gets Auto-Deleted

| Data | TTL | Mechanism | Why Deletable |
|------|-----|-----------|---------------|
| Batch work item docs (intermediate LLM outputs: economist report, scout report, etc.) | 14 days | Firestore TTL on `expireAt` field | Regenerable from raw signals in archive |
| Vertex batch JSONL files in GCS | 7 days | GCS lifecycle rule on `batch-inputs/` and `batch-outputs/` prefixes | Debug-only |
| Data cache entries | 7/30/90 days per tier | Existing `data_cache.py` TTL logic | Re-fetchable from APIs |

### Permanent Firestore Schemas

**`zipcode_weekly_pulse` collection** (the product):
```
Doc ID: 07110-restaurants-2026-W12

{
  zipCode: "07110",
  businessType: "restaurants",
  weekOf: "2026-W12",
  headline: "Delivery adoption hits tipping point...",
  insights: [
    {
      rank: 1,
      title: "Delivery gap closing fast",
      analysis: "3 of 14 restaurants added delivery this month...",
      recommendation: "Launch delivery with first-week promo...",
      impactScore: 82,
      impactLevel: "high",
      timeSensitivity: "this_week",
      signalSources: ["osm", "trends", "socialPulse"],
      playbookUsed: "competitor_delivery_wave",
    },
    // ... 2-4 more InsightCards
  ],
  quickStats: {
    trendingSearches: ["meal prep delivery", "outdoor dining"],
    weatherOutlook: "Rain Saturday, clear Sunday",
    upcomingEventCount: 3,
    activePriceAlerts: ["dairy +12.1% YoY"],
  },
  critiqueScore: 87,
  critiquePass: true,
  playbooksMatched: ["competitor_delivery_wave", "dairy_margin_swap"],
  signalsUsed: ["blsCpi", "census", "osm", "socialPulse", "trends", "weather", "news"],
  agentVersion: "1.0.0",
  batchId: "pulse-essex-2026-W12",  // null for interactive
  generatedAt: timestamp,
}
```

**`pulse_signal_archive` collection** (the raw material):
```
Doc ID: 07110-2026-W12

{
  zipCode: "07110",
  weekOf: "2026-W12",
  collectedAt: timestamp,
  sources: {
    blsCpi:     { raw: {...}, fetchedAt: timestamp, version: "v1" },
    census:     { raw: {...}, fetchedAt: timestamp, version: "v1" },
    osm:        { raw: {...}, fetchedAt: timestamp, version: "v1" },
    fda:        { raw: {...}, fetchedAt: timestamp, version: "v1" },
    weather:    { raw: {...}, fetchedAt: timestamp, version: "v1" },
    trends:     { raw: {...}, fetchedAt: timestamp, version: "v1" },
    news:       { raw: [...], fetchedAt: timestamp, version: "v1" },
    eia:        { raw: {...}, fetchedAt: timestamp, version: "v1" },
    sba:        { raw: {...}, fetchedAt: timestamp, version: "v1" },
    fhfa:       { raw: {...}, fetchedAt: timestamp, version: "v1" },
    irs:        { raw: {...}, fetchedAt: timestamp, version: "v1" },
    cdcPlaces:  { raw: {...}, fetchedAt: timestamp, version: "v1" },
    qcew:       { raw: {...}, fetchedAt: timestamp, version: "v1" },
    usda:       { raw: {...}, fetchedAt: timestamp, version: "v1" },
    noaa:       { raw: {...}, fetchedAt: timestamp, version: "v1" },
  },
  // Pre-computed values derived from the raw sources above
  preComputedImpact: {
    dairyYoY: 0.121,
    dairyMoM: 0.034,
    poultryYoY: -0.053,
    competitorCount: 14,
    competitorDelta3mo: 3,
    deliveryAdoptionPct: 0.71,
    medianIncome: 72500,
    weatherTrafficModifier: -0.15,
    eventTrafficModifier: 0.30,
    netTrafficDelta: 0.15,
    newPermits: 2,
  },
}
```

The `version` field per source enables filtering: when you change how BLS data is fetched, bump the version. You can then query "all archives where `blsCpi.version == 'v2'`" vs the old format.

**Note**: `preComputedImpact` in the archive is a convenience snapshot — it is fully derivable from the `sources` data above. If calculation methods change, recompute from `sources`, don't trust the cached snapshot.

---

## Part 5: Data Cache Tiers

`data_cache.py` already exists with TTL logic. The fetch tools use cache-through:

```python
async def fetch_bls_cpi(business_type: str) -> dict:
    cached = await get_cached("blsCpi", business_type)
    if cached:
        return cached
    result = await query_bls_cpi_deltas(business_type)
    await set_cached("blsCpi", business_type, result, TTL_WEEKLY)
    return result
```

| Tier | TTL | Scope Key | Sources |
|------|-----|-----------|---------|
| Static (90d) | Per zip | `{zip}` | Census ACS, FHFA HPI, IRS SOI, CDC PLACES, OSM density, NOAA climate norms |
| Shared (30d) | Per county or state | `{county_fips}` or `{state}` | BLS QCEW, FDA recalls, EIA energy, USDA NASS |
| Weekly (7d) | Per zip or DMA | `{zip}` or `{dma}` | NWS weather, Google News, Google Trends, BLS CPI, SBA |

**Batch optimization**: For a 47-zip county batch, Tier 1 (static) and Tier 2 (shared) data is fetched ONCE and cached. Only Tier 3 (weekly) fetches per-zip. This reduces API calls from ~705 (47 x 15) to ~250 (47 x 3 weekly + 1 x 6 shared + 47 x 4 static-if-expired).

---

## Part 6: Zipcode Profile Discovery (One-Time Onboarding)

### The Problem

Every weekly run currently tries all 15+ sources blindly for every zip. But:
- Some zips have rich municipal websites with planning board minutes, DPW bulletins, event calendars — others have nothing
- Some towns are covered by Patch.com or TAPinto — others aren't
- Some counties publish health inspection data via API — others use scanned PDFs
- Every locality has different organizations, departments, and data providers — there's no universal list
- Searching for sources that don't exist wastes tokens and time every single week

### The Solution: Two-Phase Discovery → Capability Registry

When a new zipcode is onboarded, run a systematic **two-phase discovery** that first enumerates what data sources MIGHT exist for that locality, then probes each one to verify availability and capture URLs. Store the results as a **Zipcode Capability Registry** that the weekly pulse reads to know exactly which tools and sources to use.

### Phase 1: Enumerate Possible Sources (SourceEnumeratorAgent)

**Goal**: Given a city/state/zip, produce a comprehensive list of data source categories that MIGHT exist for this locality. This is a research agent that uses google_search to discover what organizations and data providers serve this area.

The agent works from a **Master Source Taxonomy** — a static checklist of ~30 source categories grouped by type. For each category, it determines whether a candidate exists for this specific locality.

#### Master Source Taxonomy

```python
# Static Python dict — the "menu" of possible source types
# Agent checks each category for the target locality

MASTER_SOURCE_TAXONOMY = {
    # === MUNICIPAL GOVERNMENT ===
    "municipal_website": {
        "description": "Official city/town/township/borough government website",
        "search_template": "{city} {state} official website government",
        "always_exists": True,  # every municipality has one (or should)
    },
    "planning_zoning_board": {
        "description": "Planning board, zoning board, or land use board",
        "search_template": "{city} {state} planning board zoning applications",
        "subpages": ["agendas", "minutes", "applications", "decisions"],
    },
    "public_works_dpw": {
        "description": "Dept of Public Works — road closures, paving, utilities",
        "search_template": "{city} {state} department public works DPW",
        "subpages": ["road-closures", "paving-schedule", "water-sewer"],
    },
    "building_permits": {
        "description": "Building department — permit applications, inspections",
        "search_template": "{city} {state} building department permits",
    },
    "recreation_events": {
        "description": "Recreation department / events calendar",
        "search_template": "{city} {state} recreation events calendar",
    },
    "municipal_budget": {
        "description": "Municipal budget and financial documents",
        "search_template": "{city} {state} municipal budget financial documents",
    },
    "meeting_minutes": {
        "description": "Town council / board of commissioners meeting minutes",
        "search_template": "{city} {state} council meeting minutes agendas",
    },
    "municipal_rss": {
        "description": "Any RSS or Atom feeds from the municipality",
        "search_template": "{city} {state} site:{municipal_domain} rss OR feed OR atom",
    },

    # === COUNTY GOVERNMENT ===
    "county_health_dept": {
        "description": "County health department — inspections, permits, data",
        "search_template": "{county} county {state} health department restaurant inspections",
        "check": "has_api_or_portal",  # distinguish API vs PDF vs nothing
    },
    "county_clerk": {
        "description": "County clerk — business filings, property records",
        "search_template": "{county} county {state} clerk records online",
    },
    "county_planning": {
        "description": "County planning board — major development applications",
        "search_template": "{county} county {state} planning board applications",
    },
    "county_economic_dev": {
        "description": "County economic development office — grants, programs",
        "search_template": "{county} county {state} economic development office",
    },

    # === STATE GOVERNMENT ===
    "state_legal_notices": {
        "description": "Centralized legal notice portal (NJ DOS, etc.)",
        "search_template": "{state} statewide legal notices portal government",
        "note": "NJ has nj.gov/state/statewide-legal-notices — other states vary",
    },
    "state_business_registry": {
        "description": "State business entity search / registration",
        "search_template": "{state} business entity search registration",
    },

    # === LOCAL NEWS & MEDIA ===
    "patch_com": {
        "description": "Patch.com hyperlocal news community",
        "search_template": "site:patch.com {city} {state}",
        "verify_url_pattern": "patch.com/*/{}",
    },
    "tapinto": {
        "description": "TAPinto local news network",
        "search_template": "site:tapinto.net {city}",
        "verify_url_pattern": "tapinto.net/towns/{}",
    },
    "local_newspaper": {
        "description": "Local/community newspaper (print or online)",
        "search_template": "{city} {state} local newspaper community news",
    },
    "municipal_newsletter": {
        "description": "Town newsletter, bulletin, or email blast archive",
        "search_template": "{city} {state} municipal newsletter bulletin",
    },

    # === BUSINESS & ECONOMIC ORGANIZATIONS ===
    "chamber_of_commerce": {
        "description": "Local chamber of commerce",
        "search_template": "{city} {state} chamber of commerce",
    },
    "business_improvement_district": {
        "description": "BID / Business Improvement District / SID",
        "search_template": "{city} {state} business improvement district BID downtown",
    },
    "downtown_development": {
        "description": "Downtown development corporation / Main Street program",
        "search_template": "{city} {state} downtown development main street program",
    },
    "economic_development_corp": {
        "description": "Local or regional economic development corporation",
        "search_template": "{city} OR {county} {state} economic development corporation",
    },
    "merchants_association": {
        "description": "Local merchants association or business alliance",
        "search_template": "{city} {state} merchants association business alliance",
    },

    # === COMMUNITY & CIVIC ===
    "library_system": {
        "description": "Public library — events calendar, community programs",
        "search_template": "{city} {state} public library events calendar",
    },
    "school_district": {
        "description": "School district — calendar, closings, enrollment data",
        "search_template": "{city} {state} school district calendar",
    },
    "community_calendar": {
        "description": "Unified community events calendar (if separate from municipal)",
        "search_template": "{city} {state} community events calendar 2026",
    },

    # === SOCIAL MEDIA & FORUMS ===
    "local_subreddit": {
        "description": "Town/city-specific subreddit",
        "search_template": "site:reddit.com r/{city_slug}",
    },
    "state_subreddit": {
        "description": "State-level subreddit (fallback for towns without their own)",
        "search_template": "site:reddit.com r/{state_slug}",
        "always_exists": True,
    },
    "facebook_community_groups": {
        "description": "Local Facebook groups (names only — can't access content)",
        "search_template": "{city} {state} facebook community group",
        "access": "names_only",
    },

    # === FEDERAL/API DATA SOURCES ===
    "census_zbp": {
        "description": "Census ZIP Business Patterns — establishment counts by NAICS",
        "check": "api_call",  # deterministic API check, no search needed
    },
    "census_acs": {
        "description": "Census American Community Survey — demographics, income",
        "check": "api_call",
    },
    "google_trends": {
        "description": "Google Trends via BigQuery — DMA-level search interest",
        "check": "dma_lookup",
    },
    "nws_weather": {
        "description": "National Weather Service — nearest station for forecasts",
        "check": "api_call",
    },
    "osm_businesses": {
        "description": "OpenStreetMap — local business counts and categories",
        "check": "api_call",
    },
    "fema_declarations": {
        "description": "FEMA disaster declarations for the area",
        "check": "api_call",
    },
}
```

**How Phase 1 works**:

1. The `SourceEnumeratorAgent` (LlmAgent + google_search) receives the taxonomy and the target city/state/county.
2. For categories marked `always_exists: True`, it adds them to the candidate list immediately.
3. For categories with `check: "api_call"`, it delegates to deterministic API checks (Python functions, no LLM) — Census API returns data? NWS returns a station? OSM returns businesses?
4. For all other categories, it executes the `search_template` queries via google_search and evaluates whether a real result exists.
5. Output: A list of `SourceCandidate` objects — `{category, exists: bool, searchEvidence: str, candidateUrl: str | null}`.

This phase is **fast** (~15-20s) because it's mostly search queries, not deep crawling.

### Phase 2: Verify & Capture Each Source (SourceVerifierAgent)

**Goal**: For every source that Phase 1 flagged as `exists: True`, verify it's real and capture the specific URLs, feeds, subpages, and access methods. This is the deep crawling phase.

The `SourceVerifierAgent` runs as a **ParallelAgent** with one sub-agent per source category, processing up to 5-8 sources concurrently.

**What verification looks like per source type**:

| Source Category | Verification Steps | What Gets Stored |
|----------------|-------------------|-----------------|
| `municipal_website` | Crawl homepage, find main navigation, identify subpage structure | Base URL, sitemap of key sections |
| `planning_zoning_board` | Crawl candidate URL, confirm it has agendas/minutes/applications | URL, has_minutes: bool, has_applications: bool, update_frequency |
| `public_works_dpw` | Crawl candidate URL, check for road closure info or paving schedules | URL, has_road_closures: bool, has_paving_schedule: bool |
| `chamber_of_commerce` | Crawl homepage, find events page, member directory, news/blog | URL, events_url, directory_url, has_blog: bool |
| `patch_com` | Verify the Patch URL loads and has recent articles for this town | URL, last_article_date (to confirm it's active) |
| `county_health_dept` | Check if inspections are searchable online (API, portal, or PDF-only) | portal_url, access_type: "api" / "searchable_portal" / "pdf_only" / "none" |
| `local_subreddit` | Verify subreddit exists and has recent activity | subreddit_name, subscriber_count, last_post_date |
| `census_zbp` | (Already checked in Phase 1 via API) | available: bool, naics_codes found |
| `library_system` | Crawl library website, find events calendar page | URL, events_calendar_url |
| `merchants_association` | Verify org exists, find any events/news pages | URL, has_events: bool, has_directory: bool |

**How Phase 2 works**:

1. Takes the `SourceCandidate` list from Phase 1.
2. Filters to only `exists: True` candidates.
3. For each candidate, runs a `SourceVerifierSubAgent` (LlmAgent + crawl4ai) that:
   a. Navigates to the `candidateUrl`
   b. Crawls 1-3 key subpages (guided by the taxonomy's `subpages` hints)
   c. Extracts specific URLs, feed links, and capability flags
   d. Returns a `VerifiedSource` with all captured details
4. Output: List of `VerifiedSource` objects ready to write to the registry.

This phase is **slower** (~60-90s) because it does real web crawling, but it only runs on sources that Phase 1 confirmed exist.

### The Zipcode Capability Registry

```
Collection: zipcode_profiles
Doc ID: 07110

{
  zipCode: "07110",
  city: "Nutley",
  state: "NJ",
  county: "Essex",
  countyFips: "34013",
  dmaName: "New York",
  profileVersion: "1.0",
  discoveredAt: timestamp,
  refreshAfter: timestamp,  // discoveredAt + 90 days

  // Phase 1 results: what source categories were enumerated
  enumeratedSources: 34,   // total taxonomy categories checked
  confirmedSources: 22,    // how many exist for this locality
  unavailableSources: 12,  // how many don't exist

  // Phase 2 results: verified capabilities for this zip
  sources: {
    // === MUNICIPAL GOVERNMENT ===
    "municipal_website": {
      status: "verified",
      url: "https://www.nutleynj.org",
      lastVerified: timestamp,
      subpages: {
        "planning_board": "https://www.nutleynj.org/planning-board",
        "dpw": "https://www.nutleynj.org/dpw",
        "recreation": "https://www.nutleynj.org/recreation/events",
        "meeting_minutes": "https://www.nutleynj.org/meeting-minutes",
      },
      rssFeed: null,
    },
    "building_permits": {
      status: "verified",
      url: "https://www.nutleynj.org/building-department",
      hasOnlinePortal: false,  // in-person only
    },
    "municipal_budget": {
      status: "verified",
      url: "https://www.nutleynj.org/finance/budget",
    },

    // === COUNTY GOVERNMENT ===
    "county_health_dept": {
      status: "verified",
      url: "https://essexcountynj.org/health",
      accessType: "pdf_only",  // no API, no searchable portal
      note: "Restaurant inspections are PDF downloads only",
    },
    "county_clerk": {
      status: "verified",
      url: "https://essexclerk.com",
      hasOnlinePortal: true,
    },

    // === LOCAL NEWS ===
    "patch_com": {
      status: "verified",
      url: "https://patch.com/new-jersey/nutley",
      lastArticleDate: "2026-03-15",
      active: true,
    },
    "tapinto": {
      status: "verified",
      url: "https://www.tapinto.net/towns/nutley",
      active: true,
    },
    "local_newspaper": {
      status: "not_found",
    },

    // === BUSINESS ORGS ===
    "chamber_of_commerce": {
      status: "verified",
      url: "https://nutleychamber.com",
      eventsUrl: "https://nutleychamber.com/events",
      hasDirectory: true,
      hasBlog: false,
    },
    "business_improvement_district": {
      status: "not_found",
    },
    "merchants_association": {
      status: "not_found",
    },
    "downtown_development": {
      status: "not_found",
    },

    // === COMMUNITY ===
    "library_system": {
      status: "verified",
      url: "https://www.nutleypubliclibrary.org",
      eventsCalendarUrl: "https://www.nutleypubliclibrary.org/events",
    },
    "school_district": {
      status: "verified",
      url: "https://www.nutleyschools.org",
      calendarUrl: "https://www.nutleyschools.org/calendar",
    },

    // === SOCIAL ===
    "local_subreddit": {
      status: "not_found",
      note: "No r/Nutley — use state subreddit",
    },
    "state_subreddit": {
      status: "verified",
      subreddit: "r/newjersey",
    },

    // === API DATA SOURCES (deterministic checks) ===
    "census_zbp": {
      status: "verified",
      available: true,
      naicsCodes: ["7225", "7224", "4451"],
    },
    "census_acs": {
      status: "verified",
      available: true,
    },
    "google_trends": {
      status: "verified",
      available: true,
      dma: "New York",
    },
    "nws_weather": {
      status: "verified",
      available: true,
      stationId: "KEWR",
    },
    "osm_businesses": {
      status: "verified",
      available: true,
      businessCount: 127,
    },
    "fema_declarations": {
      status: "verified",
      activeDeclarations: false,
    },
    "state_legal_notices": {
      status: "verified",
      available: true,
      municipalityMatch: "Township of Nutley",
    },
  },

  // Flat list of what's NOT available — human-readable for debugging
  unavailable: [
    "local_newspaper: not_found",
    "business_improvement_district: not_found",
    "merchants_association: not_found",
    "downtown_development: not_found",
    "local_subreddit: not_found (use r/newjersey)",
    "municipal_rss: not_found",
    "county_health_dept: pdf_only (no API or searchable portal)",
  ],
}
```

### How the Weekly Pulse Uses the Registry

In Stage 1 (DataGatherer), the `BaseLayerFetcher` reads the profile FIRST:

```python
class BaseLayerFetcher(BaseAgent):
    async def _run_async_impl(self, ctx):
        zip_code = ctx.session.state["zipCode"]

        # Read capability registry
        profile = await get_zipcode_profile(zip_code)
        if not profile:
            # Fallback: run full two-phase discovery inline (slower, first-time only)
            profile = await run_zipcode_profile_discovery(zip_code)

        # Only call tools for sources with status == "verified"
        tasks = []
        sources = profile.get("sources", {})

        # API data sources — check availability flag
        if sources.get("census_zbp", {}).get("available"):
            tasks.append(fetch_census(zip_code))

        # Web sources — use discovered URLs directly (no searching)
        if sources.get("patch_com", {}).get("status") == "verified":
            tasks.append(fetch_patch_news(sources["patch_com"]["url"]))
        if sources.get("municipal_website", {}).get("subpages", {}).get("planning_board"):
            tasks.append(crawl_planning_board(sources["municipal_website"]["subpages"]["planning_board"]))

        # Business org intelligence — only if they exist
        if sources.get("chamber_of_commerce", {}).get("eventsUrl"):
            tasks.append(crawl_chamber_events(sources["chamber_of_commerce"]["eventsUrl"]))

        # Skip everything marked not_found or pdf_only
        # No wasted searches — we already know what's available
```

### Benefits

| Without Registry | With Registry |
|-----------------|---------------|
| `google_search("Nutley NJ planning board")` every week | Direct crawl of `nutleynj.org/planning-board` — faster, more reliable |
| `google_search("Nutley chamber of commerce events")` every week | Direct crawl of `nutleychamber.com/events` — already discovered |
| Try all 30+ source categories, 12 return nothing | Only call sources known to work for this zip |
| Don't know if county has health API | Registry says "pdf_only" — skip |
| Don't know if there's a BID, merchants assoc, etc. | Registry says "not_found" — don't waste tokens searching |
| Same generic approach for every zip | Each zip has a tailored, enumerated tool set |
| Miss sources we didn't think to look for | Taxonomy ensures every category is checked systematically |

### Refresh Cadence

- **Default**: Every 90 days (quarterly) — full re-run of both phases
- **Trigger refresh**: Admin can manually trigger for a zip
- **Auto-refresh for broken sources**: If 3+ consecutive weekly runs fail to get data from a registered source, mark it as stale and re-verify just that source (Phase 2 only, not full re-enumeration)
- **New source type onboarding**: When a new category is added to `MASTER_SOURCE_TAXONOMY`, run a lightweight Phase 1 check for that category across all registered zips
- **Partial refresh**: Re-verify just one source category without re-running the full discovery

### Discovery Agent Architecture

```
ZipcodeProfileDiscovery (SequentialAgent, ~90-120s total)
│
├─ Stage 1: SourceEnumeratorAgent (LlmAgent + google_search, ~15-20s)
│   Input: city, state, county, zip, MASTER_SOURCE_TAXONOMY
│   Process:
│     1. For "api_call" categories → run deterministic Python checks
│     2. For "always_exists" → add to candidates immediately
│     3. For all others → execute search_template queries
│     4. Evaluate search results → exists: true/false + candidateUrl
│   Output (output_key: "sourceCandidates"):
│     [ {category, exists, searchEvidence, candidateUrl}, ... ]
│
├─ Stage 2: SourceVerifierFanOut (ParallelAgent, ~60-90s)
│   Input: sourceCandidates (filtered to exists==true only)
│   Sub-agents: One SourceVerifierSubAgent per source, max 8 concurrent
│   Each sub-agent:
│     1. Navigates to candidateUrl
│     2. Crawls 1-3 subpages (guided by taxonomy hints)
│     3. Extracts URLs, feeds, capability flags
│     4. Returns VerifiedSource
│   Output (output_key: "verifiedSources"):
│     [ {category, status, url, subpages, flags...}, ... ]
│
└─ Stage 3: ProfileAssemblerAgent (custom BaseAgent — deterministic, ~1s)
    Input: sourceCandidates + verifiedSources + API check results
    Process: Merge all results into ZipcodeProfile schema
    Output: Saves to Firestore zipcode_profiles collection
```

### Discovery Implementation Files

| # | File | What |
|---|------|------|
| D1 | `agents/hephae_agents/research/zipcode_profile_discovery.py` | SequentialAgent orchestrator: SourceEnumeratorAgent → SourceVerifierFanOut → ProfileAssemblerAgent. Contains `MASTER_SOURCE_TAXONOMY` dict and `run_zipcode_profile_discovery(zip_code)` runner function. |
| D2 | `agents/hephae_agents/research/source_verifier.py` | `SourceVerifierSubAgent` (LlmAgent + crawl4ai) that verifies a single source candidate. Parameterized with category-specific verification instructions from the taxonomy. |
| D3 | `lib/db/hephae_db/schemas/zipcode_profile.py` | Pydantic models: `ZipcodeProfile`, `SourceEntry` (with `status`, `url`, `subpages`, `flags`), `SourceCandidate`, `VerifiedSource`. |
| D4 | `lib/db/hephae_db/firestore/zipcode_profiles.py` | CRUD: `get_zipcode_profile()`, `save_zipcode_profile()`, `list_stale_profiles()`, `mark_source_stale(zip, category)`, `refresh_source(zip, category, verified_data)` |
| D5 | `apps/api/hephae_api/routers/admin/zipcode_profiles.py` | `POST /api/zipcode-profiles/discover/{zip}` (trigger full discovery), `GET /api/zipcode-profiles/{zip}` (view registry), `POST /api/zipcode-profiles/refresh-stale` (batch refresh), `POST /api/zipcode-profiles/{zip}/refresh/{category}` (single source refresh) |

### Implementation Phase

This is **Phase E** — after the core pulse pipeline (Phases A-D) is working. The pulse pipeline works without the registry (falls back to blind search), but gets significantly faster and more accurate with it.

```
Phase E: Zipcode Profile Discovery
E1. zipcode_profile.py (schema) — Pydantic models for profile + source entries
E2. MASTER_SOURCE_TAXONOMY dict — static taxonomy of ~30 source categories
E3. zipcode_profiles.py (firestore CRUD) — get/save/stale/refresh
E4. source_verifier.py (agent) — per-source verification sub-agent
E5. zipcode_profile_discovery.py (agent) — SequentialAgent orchestrator
E6. zipcode_profiles.py (admin router) — API endpoints
E7. Modify BaseLayerFetcher to read profile before fetching
E8. Run discovery for initial 50 zips, review + tune taxonomy
```

**Verification E**: Discover profile for 07110 (Nutley, NJ). Confirm:
- Phase 1 enumerates all 30+ taxonomy categories and correctly identifies which exist
- Phase 2 verifies each confirmed source and captures specific URLs
- Registry correctly stores `nutleynj.org/planning-board`, `patch.com/new-jersey/nutley`, `nutleychamber.com`, etc.
- Sources like "local_subreddit" are correctly marked `not_found`
- Run weekly pulse with and without the profile — confirm profile-aware run is faster and uses direct URLs
- Add a new category to the taxonomy → verify it gets checked across existing profiles

---

## Part 7: All New Files

### Agents (4 new files + 1 rewrite)

| # | File | What | ADK Type |
|---|------|------|----------|
| 1 | `agents/hephae_agents/research/pulse_orchestrator.py` | Top-level SequentialAgent tree (Stages 1-4) | SequentialAgent |
| 2 | `agents/hephae_agents/research/pulse_data_gatherer.py` | Stage 1: BaseLayerFetcher + IndustryPluginFetcher + ResearchFanOut | ParallelAgent with custom BaseAgent children |
| 3 | `agents/hephae_agents/research/pulse_domain_experts.py` | Stage 2: PulseHistorySummarizer + EconomistAgent + LocalScoutAgent | ParallelAgent with 3 LlmAgent children |
| 4 | `agents/hephae_agents/research/weekly_pulse_agent.py` | **REWRITE** (472-line file already exists with inline `generate_weekly_pulse()` + `_build_signal_prompt()`). Becomes Stage 3: pure Synthesis LlmAgent that reads signals from `session.state` instead of building its own prompt. Uses DEEP thinking + `response_schema=WeeklyPulseOutput`. Also supports rewrite mode: when `state["rewriteFeedback"]` is set, instruction shifts to revise only failing insights. | LlmAgent |
| 5 | `agents/hephae_agents/research/pulse_critique_agent.py` | Stage 4: LoopAgent wrapping a SequentialAgent of [PulseCritiqueAgent, WeeklyPulseAgent (rewrite mode)]. Iteration 1: critique evaluates Stage 3's `pulseOutput` → if all pass, `escalate=True` exits loop before rewrite runs; if any fail, rewrite runs with `rewriteFeedback` in state. Iteration 2: critique re-evaluates rewritten output. After `max_iterations=2`, loop exits regardless. | LoopAgent → SequentialAgent → [LlmAgent, LlmAgent] |

### Data Layer (3 new files)

| # | File | What |
|---|------|------|
| 6 | `lib/db/hephae_db/schemas/pulse_outputs.py` | **NOTE**: `WeeklyPulseOutput`, `PulseInsight`, `PulseQuickStats` already exist in `agent_outputs.py` (lines 856-887). This new file re-exports those base models and adds: `CritiqueResult`, `InsightCritique` (new), plus extends `PulseInsight` with `signalSources: list[str]` and `playbookUsed: str` fields (update in `agent_outputs.py`). Keeps critique-specific models separate from the shared schema file. |
| 7 | `lib/db/hephae_db/firestore/signal_archive.py` | `save_signal_archive()`, `get_signal_archive()` CRUD |
| 8 | `lib/db/hephae_db/firestore/pulse_batch.py` | Batch work item CRUD: `create_work_items()`, `update_work_item()`, `get_work_items_by_status()` |

### Orchestrators (2 new files)

| # | File | What |
|---|------|------|
| 9 | `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` | All fetch functions as FunctionTool wrappers with cache-through logic. Migrated from `industry_plugins.py` inline fetchers. |
| 10 | `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` | Playbook registry + `match_playbooks()` + `compute_impact_multipliers()` |

### Batch (2 new files)

| # | File | What |
|---|------|------|
| 11 | `apps/api/hephae_api/workflows/orchestrators/pulse_batch_processor.py` | `run_pulse_batch(batch_id)` — 5-stage pipeline using `submit_vertex_batch()` |
| 12 | `apps/api/hephae_api/routers/batch/pulse_batch.py` | `POST /api/cron/pulse-batch-submit` + `GET /api/cron/pulse-batch-status/{batch_id}` |

### Admin (1 new file)

| # | File | What |
|---|------|------|
| 13 | `apps/api/hephae_api/routers/admin/pulse_admin.py` | Batch-specific endpoints: `GET /api/weekly-pulse/batches`, `GET /api/weekly-pulse/batches/{id}`, batch monitoring. **NOTE**: `routers/admin/weekly_pulse.py` already exists (105 lines) with single-pulse endpoints: `POST /api/weekly-pulse`, `GET .../latest`, `GET .../history`, `DELETE`. Keep existing router for single-pulse ops; this new file handles batch ops only. |

### Zipcode Profile Discovery (5 new files — Phase E)

| # | File | What |
|---|------|------|
| 14 | `agents/hephae_agents/research/zipcode_profile_discovery.py` | SequentialAgent orchestrator: SourceEnumeratorAgent → SourceVerifierFanOut → ProfileAssemblerAgent. Contains `MASTER_SOURCE_TAXONOMY` dict and `run_zipcode_profile_discovery()` runner. |
| 15 | `agents/hephae_agents/research/source_verifier.py` | `SourceVerifierSubAgent` — LlmAgent + crawl4ai that verifies a single source candidate. Parameterized per category from taxonomy. |
| 16 | `lib/db/hephae_db/schemas/zipcode_profile.py` | Pydantic models: ZipcodeProfile, SourceEntry, SourceCandidate, VerifiedSource |
| 17 | `lib/db/hephae_db/firestore/zipcode_profiles.py` | CRUD: get/save/list_stale/mark_source_stale/refresh_source |
| 18 | `apps/api/hephae_api/routers/admin/zipcode_profiles.py` | Admin endpoints: discover, view, refresh-stale, refresh single source |

**Total: 17 new files + 1 major rewrite** (`weekly_pulse_agent.py`)

## Part 8: Modified Files (6 active changes + 1 no-op + 1 in Phase E)

| # | File | Change |
|---|------|--------|
| 1 | `hephae_common/gemini_batch.py` | Add `tools` field support in `submit_vertex_batch()` JSONL builder (for google_search_retrieval grounding) |
| 2 | `hephae_api/workflows/orchestrators/weekly_pulse.py` | Full rewrite: replace 463-line asyncio.gather with call to `generate_pulse_interactive()` using ADK agent tree (~80 lines) |
| 3 | `hephae_api/workflows/orchestrators/industry_plugins.py` | Remove all `_fetch_*()` wrappers and `fetch_industry_data()`. Keep only type classification sets (`FOOD_TYPES`, etc.) and `is_food_business()`. Fetchers move to `pulse_fetch_tools.py`. |
| 4 | `hephae_api/config.py` | Add `WEEKLY_PULSE = "1.0.0"` to `AgentVersions` |
| 5 | `hephae_api/main.py` | Register `pulse_batch`, `pulse_admin`, and `zipcode_profiles` routers |
| 6 | `apps/batch/hephae_batch/main.py` | Add `pulse-batch` command |
| 7 | `hephae_db/firestore/weekly_pulse.py` | Already has `get_pulse_history()`, `save_weekly_pulse()`, `get_latest_pulse()`, etc. (175 lines). **No changes needed** unless history query needs to return `signalArchive` field (currently returns full pulse docs). If so, add a `fields` filter param. |
| 8 | `agents/hephae_agents/research/pulse_data_gatherer.py` | (Phase E) Read zipcode profile registry before fetching; skip unavailable sources; use discovered URLs directly |

---

## Part 9: Implementation Order

### Phase A: Foundation (no LLM changes)

```
A1. pulse_outputs.py (schemas)           — Pydantic models, no dependencies
A2. signal_archive.py (firestore)        — CRUD, depends on schemas
A3. pulse_batch.py (firestore)           — Work item CRUD, no dependencies
A4. pulse_fetch_tools.py (orchestrator)  — Migrate fetchers from industry_plugins.py
                                            Add cache-through wrappers
A5. pulse_playbooks.py (orchestrator)    — Playbook registry + impact calculator
A6. gemini_batch.py (modify)             — Add tools field to JSONL builder
A7. industry_plugins.py (modify)         — Strip fetchers, keep type classification
```

**Verification A**: Run each fetch tool standalone against 07110, 07109, 07042. Confirm cache hits on second run.

### Phase B: Multi-Agent Interactive Pipeline

```
B1. pulse_data_gatherer.py (agent)       — Stage 1: custom BaseAgent + ResearchFanOut
B2. pulse_domain_experts.py (agent)      — Stage 2: Historian + Economist + Scout
B3. weekly_pulse_agent.py (agent)        — Stage 3: Synthesis with DEEP thinking
B4. pulse_critique_agent.py (agent)      — Stage 4: LoopAgent critique
B5. pulse_orchestrator.py (agent)        — Wire all 4 stages into SequentialAgent
B6. weekly_pulse.py (modify)             — Replace generate_pulse() with ADK runner
B7. config.py (modify)                   — Add WEEKLY_PULSE version
```

**Verification B**: `POST /api/weekly-pulse` with zip 07110 + "restaurants". Confirm:
- 3-5 insight cards returned
- No insight fails the "walking down the street" test
- Cross-signal sources cited in each card
- Critique loop triggered at least once (check logs)
- Raw signals archived in `pulse_signal_archive`
- Total time < 45s

### Phase C: Batch Mode

```
C1. pulse_batch_processor.py             — 5-stage pipeline using submit_vertex_batch()
C2. pulse_batch.py (router)              — Cron submission endpoint
C3. pulse_admin.py (router)              — Admin monitoring
C4. main.py (modify)                     — Register routers
C5. apps/batch/main.py (modify)          — Add pulse-batch command
```

**Verification C**: Submit Essex County batch (47 zips). Confirm:
- All work items reach COMPLETED or FAILED (no stuck items)
- request_id mapping is correct (spot-check 3 zips)
- Vertex batch jobs use grounding for Stage 1
- Failed zips get exactly 1 rewrite attempt
- Total time < 25 min
- Work item docs have `expireAt` set to 14 days

### Phase D: Hardening (after Phase C is stable)

```
D1. Add GCS lifecycle rule for batch JSONL cleanup (7 days)
D2. Configure Firestore TTL policy on pulse_batch_work_items.expireAt
D3. Build 10+ playbooks based on real pulse outputs
D4. Add pulse eval tests (judge quality of insight cards)
D5. Add batch monitoring to admin dashboard UI
```

---

## Part 10: Testing Strategy

| Test | What It Validates | Phase |
|------|------------------|-------|
| `test_pulse_outputs_schema` | WeeklyPulseOutput, InsightCard, CritiqueResult validate correctly, null safety | A |
| `test_signal_archive_crud` | Save/read archive roundtrip, version field preserved | A |
| `test_fetch_tools_cache` | Each fetch tool returns data, second call hits cache | A |
| `test_impact_multipliers` | Python arithmetic is correct (no LLM) | A |
| `test_playbook_matching` | Correct playbooks matched for known signal conditions | A |
| `test_gemini_batch_tools_field` | JSONL includes `tools` when provided, omits when not | A |
| `test_pulse_interactive_e2e` | Full pipeline for 07110 + restaurants, <45s, valid output | B |
| `test_critique_loop_triggers` | Deliberately bad input triggers rewrite, good input passes | B |
| `test_economist_agent` | Given BLS+Census JSON, produces coherent macro report | B |
| `test_local_scout_agent` | Given weather+news+catalysts, produces coherent local report | B |
| `test_batch_work_item_crud` | Create/update/query work items by status | C |
| `test_batch_id_mapping` | request_ids correctly map results back to zip codes | C |
| `test_batch_e2e_small` | 3-zip batch completes all stages | C |
| `test_pulse_quality_eval` | Evaluator scores pulse output >= 80 on relevance, actionability | D |
| `test_zipcode_profile_schema` | ZipcodeProfile, SourceEntry, SourceCandidate validate correctly, handles missing fields | E |
| `test_source_taxonomy_completeness` | All MASTER_SOURCE_TAXONOMY entries have required fields (description, search_template or check) | E |
| `test_source_enumerator` | Phase 1 enumerates all taxonomy categories for 07110, correctly flags exists/not_found | E |
| `test_source_verifier` | Phase 2 verifies a single source candidate, captures URL and subpages | E |
| `test_full_profile_discovery` | Full two-phase discovery for 07110 produces complete registry with verified URLs | E |
| `test_profile_aware_fetcher` | BaseLayerFetcher skips unavailable sources, uses discovered URLs directly | E |
| `test_profile_refresh_stale` | Profiles older than 90 days flagged as stale; single-source refresh works | E |

---

## Appendix: Key Design Decisions

### 1. Custom BaseAgent for Data Fetching (not LlmAgent)

Data fetching is deterministic. We know exactly which APIs to call for a given zip + business type. Using an LlmAgent to dispatch tool calls adds ~2s latency + ~500 tokens + unpredictable tool selection. A custom `BaseAgent` subclass calls all tools deterministically via `asyncio.TaskGroup` while still participating in ADK's session state and event system.

### 2. LoopAgent for Critique (not one-pass evaluation)

The existing evaluator pattern (score + store, no rewrite) is insufficient for Pulse. Business owners receiving obvious insights will dismiss Hephae permanently. The LoopAgent with max 2 iterations ensures every insight passes the three quality tests. Cost: ~1 additional LLM call for critique + 0-1 rewrite calls. Worth it.

### 3. Playbook Registry (not RAG)

RAG adds latency, embedding costs, and retrieval unpredictability. With ~20 playbooks, a simple Python dict with condition matching is deterministic, testable, and fast. When the playbook count exceeds ~100, reassess.

### 4. Pre-Computed Impact (not LLM math)

LLMs hallucinate arithmetic. All percentages, deltas, and multipliers are computed in Python and injected as facts. The LLM's job is narrative, not calculation.

### 5. Raw Signal Archive (not computed snapshots)

Storing pre-computed numbers (dairyYoY: 0.121) locks you into the current calculation method. Storing raw API responses lets you recompute with different formulas, add new signals retroactively, and A/B test synthesis prompts against real historical data. At ~50KB/zip/week, storage cost is negligible.

### 6. Google Search Grounding in Vertex Batch (not sequential ADK calls)

Research agents (social pulse, local catalyst) need Google Search. In interactive mode, ADK's `google_search` tool handles this natively. In batch mode, Vertex AI batch supports `google_search_retrieval` as a model configuration — no runtime tool execution needed. This lets all 100+ research prompts submit as ONE batch job instead of 100 sequential ADK calls.

### 7. Extend Existing Batch Infrastructure (not new state machine)

The codebase already has `gemini_batch.py`, `batch_runner.py`, `job_launcher.py`, and `workflow_dispatcher.py`. The pulse batch processor uses these directly rather than building a parallel system. The only new abstraction is the work item document for cross-stage state tracking.

### 8. Local Catalyst in Batch Mode (no crawl4ai)

In interactive mode, `LocalCatalystResearch` uses both `google_search` and `crawl4ai_advanced_tool`. In batch mode (Vertex AI), `crawl4ai` cannot run — it's a runtime tool that crawls live URLs. Two options:

- **Option A (recommended)**: In batch mode, local catalyst uses only `google_search_retrieval` grounding (same as social pulse). The grounding surfaces enough municipal data for synthesis. Accept slightly lower quality on catalyst signals in batch vs interactive.
- **Option B**: In Stage 0, pre-crawl known municipal URLs (town website, planning board page) via Python HTTP and inject the crawled text into the batch prompt as context. More complex, marginal benefit.

Start with Option A. If catalyst quality in batch mode is noticeably worse, implement Option B later.
