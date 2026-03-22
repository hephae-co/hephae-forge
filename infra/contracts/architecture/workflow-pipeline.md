# Workflow Pipeline
> Auto-generated from codebase on 2026-03-22. Do not edit manually — run `/hephae-refresh-docs` to update.

## 1. Phase Transitions (WorkflowPhase)

```
                          +--------+
                          | QUEUED |
                          +---+----+
                              |
                              v
                        +-----------+
                        | DISCOVERY |
                        +-----+-----+
                              |
                              v
                      +---------------+
                      | QUALIFICATION |
                      +-------+-------+
                              |
                              v
                        +----------+
                        | ANALYSIS |
                        +-----+----+
                              |
                              v
                       +------------+
                       | EVALUATION |
                       +------+-----+
                              |
                              v
                        +----------+
                        | APPROVAL |  <-- pauses for human review
                        +-----+----+
                              |
                              v
                        +----------+
                        | OUTREACH |
                        +-----+----+
                              |
                              v
                       +-----------+
                       | COMPLETED |
                       +-----------+

           (any phase)
               |
               v         on unhandled exception
            +--------+
            | FAILED |
            +--------+
```

**Enum values** (source: `lib/common/hephae_common/models.py`):

| Value | Description |
|-------|-------------|
| `queued` | Workflow created, waiting to start |
| `discovery` | Scanning zip codes for businesses |
| `qualification` | Scoring and classifying discovered businesses |
| `analysis` | Running capability agents (SEO, traffic, competitive, margin, social) |
| `evaluation` | Running evaluator agents on capability outputs |
| `approval` | Paused — waiting for human approval before outreach |
| `outreach` | Generating and sending outreach content |
| `completed` | All phases finished successfully |
| `failed` | Unrecoverable error — `lastError` field contains details |

The engine resumes from the current phase on restart. The `APPROVAL` phase returns early without advancing, requiring an explicit `resume_from_outreach()` call.

> Source: `apps/api/hephae_api/workflows/engine.py`

---

## 2. Business Phase (BusinessPhase)

Each business within a workflow tracks its own phase independently:

```
PENDING → ENRICHING → ANALYZING → ANALYSIS_DONE → EVALUATING → EVALUATION_DONE → APPROVED / REJECTED → OUTREACHING → OUTREACH_DONE / OUTREACH_FAILED
```

| Value | Description |
|-------|-------------|
| `pending` | Discovered, awaiting enrichment |
| `enriching` | Discovery pipeline running |
| `analyzing` | Capability agents running |
| `analysis_done` | All capabilities complete |
| `evaluating` | QA evaluators running |
| `evaluation_done` | Evaluation complete, `qualityPassed` set |
| `approved` | Human-approved for outreach |
| `rejected` | Human-rejected |
| `outreaching` | Outreach content being generated/sent |
| `outreach_done` | Outreach complete |
| `outreach_failed` | Outreach failed |

Non-qualified businesses (parked/disqualified) are set to `analysis_done` and skipped during the analysis phase.

> Source: `lib/common/hephae_common/models.py`

---

## 3. Capability Registry

Five capabilities are registered. Each has a runner function, a Firestore output key, a response adapter, and optionally an evaluator and a `should_run` gate.

| Name | Display Name | Firestore Key | Evaluator | `should_run` Gate |
|------|-------------|---------------|-----------|-------------------|
| `seo` | SEO Audit | `seo_auditor` | `SeoEvaluatorAgent` | `officialUrl` must be truthy |
| `traffic` | Traffic Forecast | `traffic_forecaster` | `TrafficEvaluatorAgent` | Always runs |
| `competitive` | Competitive Analysis | `competitive_analyzer` | `CompetitiveEvaluatorAgent` | Always runs |
| `margin_surgeon` | Margin Surgeon | `margin_surgeon` | `MarginSurgeonEvaluatorAgent` | `menuScreenshotBase64` or `menuUrl` must be truthy |
| `social` | Social Media Insights | `social_media_auditor` | None (no evaluator) | Always runs |

**Eval compressors** strip large fields before sending to evaluators:
- `seo`: Removes `rawPageSpeed`, `pagespeedData`, `lighthouseData`; truncates recommendations to 3 per section
- `competitive`: Strips full competitor profiles, keeps only `name`, `threat_level`, `summary`, `score`

> Source: `apps/api/hephae_api/workflows/capabilities/registry.py`

---

## 4. Qualification Scoring Weights

The qualification scanner uses a two-step process: **Step A** (metadata scan, no LLM) classifies ~80% of businesses; **Step B** (full probe + batched LLM) handles the remaining ~20% ambiguous cases.

### Step A — Metadata Scan Weights

| Signal | Points | Condition |
|--------|--------|-----------|
| Custom domain | +15 | `is_custom_domain` |
| Platform subdomain | +8 | Shopify/Wix/etc subdomain |
| HTTPS | +3 | Site uses HTTPS |
| Platform detected | +10 | Known platform (Toast, Shopify, Square, etc.) |
| Multiple analytics pixels | +10 | 2+ pixels found |
| Single analytics pixel | +5 | Exactly 1 pixel |
| Contact path found | +8 | `/contact`, booking form, etc. |
| Mailto link | +5 | `mailto:` anchor found |
| Tel link | +3 | `tel:` anchor found |
| Strong social presence | +8 | 3+ social links |
| Some social presence | +4 | 1-2 social links |
| JSON-LD structured data | +5 | `@type` in JSON-LD |
| Has page title | +2 | Title tag > 3 chars |

### Bonus Patterns

| Pattern | Points | Condition |
|---------|--------|-----------|
| Innovation Gap | +20 | Modern platform (Toast/Shopify/Square/etc.) but zero social links |
| Aggregator Escape | +20 | On DoorDash/Grubhub/UberEats but weak/no own website (dining verticals) |
| Economic Delta | +15 | Wealthy area + custom domain + no analytics |
| Services no booking | +10 | Service business with website but no contact/booking path |
| Retail no e-commerce | +8 | Retail with custom domain but no e-commerce platform detected |
| Dining pricing env | +5 | Dining business in tracked pricing environment |
| Tech-forward for sector | +5 | Platform detected + sector research indicates tech-forward industry |

### Rule-Based Fast Paths (skip scoring)

| Rule | Outcome |
|------|---------|
| Chain/franchise detected | DISQUALIFIED |
| No URL | PARKED |
| URL is social/directory page | DISQUALIFIED |
| HTTP 404 or dead site | DISQUALIFIED |
| Site unreachable (no HTML) | PARKED (needs full probe) |
| Custom domain + analytics + contact path | QUALIFIED |
| Platform site + contact path | QUALIFIED |

### Step B — Full Probe (crawl + optional LLM)

| Signal | Points |
|--------|--------|
| Email found via crawl | +10 |
| Phone found via crawl | +5 |
| Social links found (2+) | +8 |
| Delivery platforms found | +5 |
| JSON-LD from crawl | +3 |

If score is within 10 points of threshold after full probe, a batched LLM classifier decides. All LLM calls across ambiguous businesses are submitted as a single batch.

> Source: `agents/hephae_agents/qualification/scanner.py`

---

## 5. Dynamic Threshold Formula

The base threshold is **40**. It adapts based on area research context:

```python
BASE_THRESHOLD = 40

# Saturation adjustments
if saturation == "saturated" or biz_count >= 40:  threshold = 60
elif saturation == "high" or biz_count >= 20:      threshold = 50
elif saturation == "low" or biz_count < 10:        threshold = 30

# Market opportunity discount
if opp_score > 70:  threshold -= 10

# Clamped to [20, 70]
threshold = max(20, min(70, threshold))
```

**Inputs** (from `extract_research_context()`):
- `area_summary.competitiveLandscape.saturationLevel` — "saturated" / "high" / "moderate" / "low"
- `area_summary.competitiveLandscape.existingBusinessCount` — integer
- `area_summary.marketOpportunity.score` — 0-100

| Market Condition | Resulting Threshold |
|------------------|-------------------|
| Low saturation, high opportunity | 20 |
| Low saturation, normal opportunity | 30 |
| Moderate saturation | 40 (base) |
| High saturation | 50 |
| Saturated market, high opportunity | 50 |
| Saturated market, normal opportunity | 60 |

> Source: `agents/hephae_agents/qualification/threshold.py`

---

## 6. Parallel Research Pipeline

During the `DISCOVERY` phase, research runs in parallel with the business scan:

```
asyncio.gather(
    _zip_research(),      # Zipcode research (staleness: <24h reuse, <7d refresh volatile, >7d full)
    _sector_research(),   # Sector research (staleness: <7d reuse)
    _area_research(),     # Area research (staleness: <7d reuse)
)
```

**Staleness policy:**
- **Zipcode research**: Reuse if < 24 hours old. Refresh only volatile sections (weather, events, trending) if 24h-7d old. Full refresh if > 7 days old.
- **Sector research**: Reuse if < 7 days old.
- **Area research**: Reuse if < 7 days old.

All research failures are non-fatal — they do not block the discovery phase.

> Source: `apps/api/hephae_api/workflows/engine.py` lines 143-238

---

## 7. PROMOTE_KEYS

Source: `apps/api/hephae_api/workflows/phases/analysis.py`

After enrichment, these keys are promoted from the enriched identity to the top-level business document in Firestore:

```python
PROMOTE_KEYS = [
    "phone", "email", "emailStatus", "contactFormUrl", "contactFormStatus",
    "hours", "googleMapsUrl", "socialLinks",
    "logoUrl", "favicon", "primaryColor", "secondaryColor",
    "persona", "menuUrl", "competitors", "news", "validationReport",
]
```

An identical list exists in `apps/api/hephae_api/routers/admin/tasks.py` for the task-based enrichment path.

---

## 8. Batch Synthesis

After all capabilities complete, the engine runs batch synthesis for traffic forecaster and competitive positioning outputs. This collects deferred intel from task metadata and submits all prompts as a single batch.

```
analysis phase complete
    └── batch_synthesis()
         ├── collect deferredSynthesis from task metadata
         ├── build_traffic_synthesis_prompt() for each slug
         ├── build_competitive_positioning_prompt() for each slug
         └── run_synthesis_batch() → write results to latestOutputs
```

> Source: `apps/api/hephae_api/workflows/engine.py` lines 373-464

---

## 9. NEW: Two-Layer Pulse Architecture (Industry Cron → Zip Cron)

The pulse system uses a two-layer architecture where national industry-level data is pre-computed before zip-level pulses run.

### Layer 1: Industry Pulse (national)

**Schedule**: Sunday 3:00 AM ET (08:00 UTC) — runs BEFORE zip-level pulses.

**Pipeline per industry**:
1. Check cache — skip if pulse exists for this ISO week (unless `force=True`)
2. Fetch national signals (BLS CPI series, USDA commodity prices, FDA recalls)
3. Compute impact multipliers from national data
4. Match industry-specific playbooks against computed impact variables
5. Generate 2-3 paragraph trend summary via `industry_trend_summarizer` LLM agent
6. Save to Firestore (`industry_pulses` collection)

**Cron endpoint**: `GET /api/cron/industry-pulse`

The cron iterates all active registered industries, generates a pulse for each, sends a summary email to admins, and is fully idempotent (cache check per week).

> Source: `apps/api/hephae_api/routers/batch/industry_pulse_cron.py`, `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py`

### Layer 2: Zip-Level Pulse

**Schedule**: Monday 11:00 UTC — runs AFTER industry pulses.

Zip-level pulses load the pre-computed industry pulse instead of re-fetching BLS/USDA/FDA data. They add local signals (weather, events, traffic modifiers) on top of the national data.

### IndustryConfig Verticals

Each vertical is a frozen dataclass (`IndustryConfig`) that drives the entire pulse pipeline:

| Vertical | ID | BLS Series Count | USDA Commodities | Playbook Count |
|----------|----|-------------------|------------------|----------------|
| Restaurants & Cafes | `restaurant` | 20 | CATTLE, HOGS, CHICKENS, EGGS, MILK, WHEAT | 3 |
| Bakeries & Patisseries | `bakery` | 11 | WHEAT, EGGS, MILK, SUGAR | 6 |
| Barber Shops & Men's Grooming | `barber` | 6 | None | 6 |

**IndustryConfig fields**:
- `bls_series` — `{label: series_id}` for CPI data
- `usda_commodities` — commodity keys for food verticals
- `extra_signals` — additional signal sources (e.g., `fdaRecalls`, `usdaPrices`)
- `track_labels` — maps CPI label substrings to named impact variables
- `playbooks` — list of `{name, trigger, play}` with templated action text
- `economist_context` / `scout_context` / `synthesis_context` — prompt context for LLM agents
- `critique_persona` — persona for the critique agent
- `social_search_terms` — keywords for social signal gathering

**Lookup**: `resolve(business_type)` does exact alias match, then fuzzy substring match, with RESTAURANT as fallback.

> Source: `apps/api/hephae_api/workflows/orchestrators/industries.py`

### Example Playbook Triggers

**Restaurant**:
- `dairy_margin_swap`: dairy up > 5% AND poultry down → shift to grilled proteins
- `fda_recall_alert`: > 5 FDA recalls → audit supplier chain
- `weather_rain_prep`: weather modifier < -0.1 → push delivery specials

**Bakery**:
- `flour_cost_alert`: flour up > 3% → promote non-flour items
- `egg_spike_response`: eggs up > 8% → switch to pastry cream (fewer eggs)
- `butter_margin_squeeze`: butter up > 4% → reserve real butter for premium items
- `wedding_season_lock`: months 2-4 AND sugar up > 2% → lock custom cake pricing

**Barber**:
- `service_price_cover`: haircut CPI up > 3% → raise base cut $3-5
- `rent_squeeze_response`: rent CPI up > 5% → add $15 beard trim add-on
- `slow_season_fill`: Jan/Feb → text client list with $5 off promo
