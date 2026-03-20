# Zipcode Pulse: Business Overview

## Section 1: Business Logic & Data Strategy

*This document synthesizes two independent strategic plans into a single definitive business overview. Implementation details are deferred to a separate document.*

---

## 1. The Core Thesis: Analysis Over Information

A local business owner lives in their community. They already know it's raining Saturday, there's a street fair this weekend, and egg prices are up. **If the Pulse just reports facts they already know, it's worthless — and signals that Hephae doesn't understand their world.**

The value is exclusively in what they **can't** do on their own:

| Capability | What the Owner Sees | What Hephae Adds |
|-----------|-------------------|-----------------|
| **Quantification** | "Dairy is expensive lately" | "Dairy up 12.1% YoY while poultry DOWN 5.3%. A menu shift to chicken-forward specials recovers ~$200/mo" |
| **Cross-signal correlation** | "Street fair + warm Saturday" separately | "Street fair + 72°F + Saturday = historically 35% more foot traffic 5-8pm. But Oak St closure shifts parking east — Elm St businesses capture spillover" |
| **Competitive intelligence** | Knows the 2-3 restaurants on their block | "3 of the 14 restaurants in your zip added delivery this month — you're now one of only 4 without it" |
| **Market-level benchmarking** | Vague sense of competition | "Your zip has 2.3x more restaurants per capita than the adjacent zip. In saturated zips, the survivors all have strong digital presence." |
| **Consumer demand signals** | Never sees search data | "'Outdoor dining near me' searches up 40% in your DMA vs last month" |
| **Leading indicators** | Only knows about construction next door | "200-unit apartment complex approved 0.5mi from you. Based on comparable developments in 07109, nearby restaurants saw 18% revenue growth within 6 months of occupancy." |
| **Hidden opportunities** | Never reads planning board minutes | "Your town posted an RFP for event catering services. You're qualified. Deadline is Friday." |

**The test for every signal**: *"Does this tell the owner something they couldn't figure out by walking down the street?"* If no, it's a modifier at best. If yes, it's a core signal.

---

## 2. Data Sources: What Can Actually Be Collected

### The "Non-Obvious Value" Filter

Every data source is evaluated on 5 dimensions:
1. **Non-obvious to owner?** — Does it pass the "walking down the street" test?
2. **ToS-compliant?** — Can we legally use it in commercial outreach reports?
3. **API reliability** — Stable documented API, or fragile scraping?
4. **Signal freshness** — Weekly+ cadence, or too stale for a weekly report?
5. **Already built?** — What's the marginal engineering cost?

### P0 — Core Signals (already built or trivial to extend)

These form the backbone of every Weekly Pulse. All are public domain with stable APIs.

| Signal | Source | Already Built? | What It Provides | Non-Obvious Hook |
|--------|--------|---------------|-----------------|-----------------|
| **Commodity price *comparisons*** | USDA AMS + BLS CPI | YES — `usda_client.py`, `bls_client.py` | Weekly regional prices + MoM deltas | "Dairy up 12% but chicken DOWN 5.3% — here's the menu swap that recovers $200/mo" |
| **Consumer demand shifts** | Google Trends (BigQuery) | YES — `bigquery/reader.py` | DMA-level rising search terms | "'Meal prep delivery' searches up 40% in your DMA" |
| **Competitive landscape** | Census ZBP + OSM | YES — `osm_client.py`; Census needs direct API | Business establishment counts by NAICS per ZIP | "14 full-service restaurants in 07110 vs 6 in 07109 — 2.3x saturation" |
| **Supply chain / compliance** | FDA Enforcement API | YES — `fda_client.py` | Recall alerts by product category | "FDA recall on romaine affects your distributor — 3 alternative suppliers in region" |
| **Cross-zip benchmarking** | Hephae's own accumulated data | BUILDS OVER TIME | Historical pulse snapshots → pattern detection | "Restaurants in 07109 with outdoor seating saw 22% higher summer revenue" |

**New build needed at P0**: Only `weather_client.py` (Weather.gov NWS API — public domain, no key). But weather is a **modifier only**, never standalone. ("Rain + Street Fair" is valuable; "It will rain Saturday" is worthless.)

**Key insight**: ~70% of P0 data plumbing already exists. The main gap is not data collection — it's the **synthesis layer** that cross-correlates signals into insight cards.

### P1 — High-Value Additions (clean government APIs, need new clients)

| Signal | Source | ToS | API Quality | Freshness | Non-Obvious Hook | Build Effort |
|--------|--------|-----|-------------|-----------|-----------------|-------------|
| **Demographics (quantified)** | Census ACS 5-Year (`api.census.gov`) | Public domain | Stable REST, free key | Annual | "Median income in your zip rose 8% in 3 years — room for premium tier" | LOW — same API as ZBP |
| **Building permits (non-adjacent)** | NJ DCA Data Hub + HUD SOCDS | Public domain | ArcGIS REST / monthly DB | Monthly | "200-unit complex approved 0.5mi away → ~400 new customers in 18mo" | MEDIUM |
| **Municipal legal notices** | NJ DOS Portal (`nj.gov/state/statewide-legal-notices-list.shtml`) | Public domain (govt mandate) | Centralized HTML portal | Daily | "Town posted RFP for event catering. You qualify. Deadline Friday." | MEDIUM — HTML parsing |
| **Road closures (quantified)** | 511NJ / WZDx feeds | Public domain | Real-time JSON | Real-time | "Comparable closures in adjacent zips caused ~15% revenue dip" | MEDIUM — verify NJ availability |
| **Disaster declarations** | FEMA OpenFEMA (`api.fema.gov`) | Public domain | REST, no key | As-needed | "Disaster declaration unlocks SBA disaster loans — here's how to apply" | LOW — trivial REST |

**Critical note on NJ DOS Legal Notices**: NJ law S4654/A5878 (signed July 2025, effective March 2026) moved legal notice requirements from print newspapers to official government websites. This created a **centralized, machine-readable feed** of land use applications, budget hearings, procurement notices, and zoning changes from every public entity in NJ. This is the single biggest "hidden gem" — no other platform is indexing this yet. Risk: portal is brand new, structure may change. Build defensively.

**Critical note on road closures**: Owners usually *know* about closures on their block. The value is only in **quantified historical comparison** ("last time this stretch closed for 2 weeks, businesses in comparable locations lost ~15% revenue"). Without that context, road closure alerts tell them what they already know.

### P2 — Supplemental (fragile, coarse, or infrequent)

| Signal | Source | Issue | Verdict |
|--------|--------|-------|---------|
| **Local news** | Google News RSS + Patch.com RSS | Google RSS is undocumented/fragile (`gpc=ZIPCODE` boosts but doesn't filter). Patch.com covers ~1,000 US communities only. | Useful as input to LLM cross-referencing, never as standalone output. Layer both for redundancy. |
| **Air quality** | EPA AirNow API | Niche — only affects outdoor dining/retail | Low effort, build when core is stable |
| **SBA loan approvals** | data.sba.gov (Socrata) | 3-6 month lag | Quarterly competitive overlay, not weekly signal |
| **Energy costs** | EIA API | State-level only (no zip/county) | Too coarse to be personal |
| **Municipal RSS** | NJLM RSS feeds | Job listings, legal notices, RFPs — useful but niche | Weekly scan for procurement signals |

### P3 — Do NOT Build (ToS violations, fragmented, or prohibitively expensive)

| Source | Why Not |
|--------|---------|
| **Yelp Fusion API** | ToS explicitly restricts aggregated data to "non-commercial analysis." Using in outreach reports = commercial use. 24-hour cache limit. **Use OSM + Census ZBP instead.** |
| **Google Places API** | $7-30/request. No native zip filter. ToS restricts competitive analysis. **Use OSM instead.** |
| **Health inspection scores** | Fragmented across NJ's 21 counties. No unified API. Per-county scraping = brittle. |
| **Liquor license filings** | NJ has no clean API. NY/MO via Socrata but out of initial market. |
| **County clerk records** | 21 systems, mostly scanned PDFs. Impractical at scale. |
| **NJ business registry** | No public API. Web portal only. |
| **Mobile foot traffic** (Placer.ai, XMAP) | Enterprise contracts ($$$). Not public API. |
| **FBI crime data** | County-level only, significant lag, documented quality issues. |
| **Chamber of Commerce data** | Gated behind membership. No standard API. Existing MunicipalHubAgent already handles directory discovery. |

### What Physically Cannot Be Done

- **BLS CPI below metro level** — 23 metro areas is the finest grain. Period.
- **USDA prices below ~10 metro regions** — national/regional only.
- **Google Trends below DMA** — BigQuery dataset hard limit. DMA (~210 US regions) is sufficient.
- **Unified national event calendar API** — doesn't exist. Must aggregate from fragments.
- **Real-time utility shut-off data** — not publicly available anywhere.

---

## 3. How the Data Becomes Differentiated Intelligence

### The Synthesis Formula

Raw data is commodity. Every consultant can pull BLS numbers. The differentiation is in **three layers of analysis** that require data infrastructure no local owner has:

```
RAW DATA (table stakes)              INSIGHT (differentiator)                    MOAT (accumulates over time)
─────────────────────────           ────────────────────────                    ──────────────────────────

"Dairy up 12%"                      "Dairy up 12% while chicken                "Last time dairy spiked 10%+
                                     down 5.3%. 3 pizzerias in                  in Q1, 3 of 14 restaurants
                                     your zip already shifted to                in this zip adjusted menus
                                     chicken specials this week.                within 2 weeks. The 2 that
                                     Here's the menu optimization               didn't both closed by June."
                                     playbook."

Single signal.                       Cross-signal + competitive                 Longitudinal pattern from
Anyone can look this up.             + actionable recommendation.               accumulated weekly snapshots.
                                     Requires multiple data sources              ONLY Hephae has this data.
                                     + LLM synthesis.
```

### The Five Analysis Tasks

The `WeeklyPulseAgent` doesn't just report data. It performs:

1. **Cross-correlate** — What combinations of signals create opportunities or threats? (e.g., "Street fair + warm weather + road closure on Oak St = parking shift to Elm St corridor")
2. **Quantify impact** — Based on historical patterns, what's the expected magnitude? (0-100 impact score, with dollar estimates where possible)
3. **Detect anomalies** — What's different *this week* vs trailing 4-week average? (e.g., "Dairy spiked 12% — this is 3x the normal monthly variance")
4. **Generate recommendations** — What should a `{business_type}` owner DO? Not "be aware of X" but "shift your weekly special from cream-based to grilled chicken"
5. **Prioritize** — Rank by actionability and time-sensitivity (`this_week` > `this_month` > `this_quarter`)

### The Output: Insight Cards, Not Data Dumps

Each Weekly Pulse produces **3-5 ranked insight cards**, not a wall of numbers. Each card has:
- **Title**: 1-line summary
- **Analysis**: Cross-signal reasoning (which data points were correlated, what the pattern means)
- **Recommendation**: Specific action for the business type
- **Impact score**: 0-100
- **Time sensitivity**: `this_week` / `this_month` / `this_quarter`

Plus a **quickStats** sidebar: trending searches, weather outlook, upcoming event count, active price alerts.

### Industry-Specific Pluggability

Not every signal matters to every business. The architecture separates:

**Base layer** (runs once per zip, all industries):
- Events, weather, road closures, permits/zoning, local news, Google Trends, demographics

**Industry plugins** (run conditionally per business type):
- **Food/Restaurant**: BLS CPI deltas, USDA commodity prices, FDA recalls, menu cost implications
- **Services/Salon**: Beauty industry licensing, regulatory updates
- **Retail**: Consumer spending trends, supply chain alerts

Adding a new industry = adding a plugin. The synthesis agent doesn't change.

---

## 4. The Competitive Moat: What Accumulates

### Short-Term Differentiator (Day 1)

- **Cross-signal correlation** that no owner can do manually
- **Census-level competitive landscape** (establishment counts by NAICS per zip)
- **Consumer search intent** (Google Trends rising terms invisible to owners)
- **Municipal legal notice indexing** (NJ DOS portal — no one else is doing this)

### Medium-Term Differentiator (3-6 months)

- **Longitudinal pattern detection**: "6 similar weather+event combos in this zip → 30-40% traffic lift"
- **Anomaly detection vs trailing average**: "This week's dairy spike is 3x the normal monthly variance"
- **Seasonal calibration**: "What worked last March in this zip?"
- **Delta reporting**: "Dairy prices up 3% vs last week's briefing"

### Long-Term Moat (12+ months)

- **Cross-zip benchmarking**: "Restaurants in zips where delivery adoption passed 75% saw the holdouts lose 12% of dine-in base within 6 months"
- **Predictive models**: "Based on 52 weeks of data across 200 zips, when dairy spikes >10% in Q1, menu adjustment within 2 weeks correlates with 3x higher survival rate"
- **Proprietary economic history per zip**: No government dataset, no competitor has this. It can only be built by running the Pulse weekly for months.

### Why This Moat Is Real

| Dimension | Business-First (Current) | Zipcode-First (Pulse) |
|-----------|------------------------|-----------------------|
| **Research cost** | 1 business = 1 full pipeline run | 1 zip = 50+ businesses served |
| **Outreach frame** | "Your SEO is bad" (critique) | "Your zip's costs are shifting" (intelligence) |
| **Owner perception** | "Another agency cold-pitching me" | "Someone is looking out for me" |
| **Conversion mechanism** | Demo → proposal → close | Free Pulse → endowment effect → paid |
| **Data moat** | Ephemeral (each report is one-off) | Cumulative (weekly history = proprietary) |
| **Scalability** | Linear (more biz = more cost) | Sublinear (more biz per zip = lower marginal cost) |

---

## 5. The Outreach Framework: Insight → Comparison → Strategy (ICS)

### Why Not "Threat → Quantification → Solution"?

The old TQS frame assumed the owner doesn't know the threat. They often do. Leading with "Main St is closing!" when they drive on it daily insults their intelligence. The ICS frame leads with **insight they CAN'T get on their own**:

| Step | What It Does | Example |
|------|-------------|---------|
| **INSIGHT** (1 sentence) | Data point they CANNOT get by walking down the street | "3 of the 14 restaurants in your zip added delivery this month — you're now one of only 4 without it." |
| **COMPARISON** (1 sentence) | Benchmark vs comparable businesses, adjacent zips, or history | "In zips where delivery adoption passed 75%, the holdouts lost 12% of their dine-in base within 6 months." |
| **STRATEGY** (1-2 sentences) | Specific play — not "hire us" but "here's what to do" | "We built a launch-week delivery promotion template for restaurants in your category. Includes platform setup, social sequence, and margin calculator." |
| **CTA** (1 line) | Low-friction value delivery, not a meeting request | "Reply 'DELIVERY' and we'll send it — free, no strings." |

### The Endowment Effect Conversion Loop

After 2-3 free Weekly Pulse reports, the owner feels ownership over the intelligence ("MY weekly briefing"). Losing access becomes more painful than paying. Use possessive language: "Your Nutley Dashboard," "Your weekly intel," "Your competitive report."

### Anti-Patterns

- **Telling them what they already know** — weather, nearby events, obvious local news. **#1 risk.**
- **Generic industry stats** — "restaurant margins are thin" (every owner knows this)
- **Pure doom without strategy** — "costs are rising" with no actionable play
- **Overpromising** — "we'll 10x your revenue"
- **Long emails** — hook must land in 2 sentences
- **Asking for meetings** — CTA = value delivery, not sales call

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Pulse tells owners what they already know** | HIGH — kills credibility | Every insight card must pass the "walking down the street" test. Weather/events/closures are modifiers only, never standalone. |
| **Google News RSS breaks** | MEDIUM | Patch.com + NJLM as fallbacks; never sole dependency |
| **NJ DOS Legal Notice portal changes structure** | MEDIUM | Build HTML parser defensively with fallbacks; monitor for changes |
| **Census data is 18 months stale** | LOW | Acceptable for structural context (demographics don't shift weekly); label clearly |
| **NJ-specific sources don't generalize** | MEDIUM | Design all clients with state-agnostic interfaces; NJ is pilot market |
| **Event scoring inaccurate early on** | MEDIUM | Start with keyword fallback → graduate to LLM extraction; track actual outcomes |
| **Owner perceives Pulse as spam** | MEDIUM | Genuine value in every issue; 1-click unsubscribe; max 1x/week |
| **Cross-signal correlation produces hallucinated insights** | HIGH | Use Gemini's structured output + DEEP thinking mode; human QA on first 10 zips |

---

## Section 2: Implementation Plan

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              WeeklyPulseAgent (synthesis)                │
│   Cross-correlates signals → 3-5 ranked insight cards    │
│   Uses DEEP thinking mode (10k+ tokens)                 │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
    ┌──────────▼──────────┐    ┌─────▼──────────────────────┐
    │    BASE LAYER        │    │   INDUSTRY PLUGINS          │
    │    (all zip codes)   │    │   (conditional per type)    │
    │                      │    │                             │
    │ • Events (next 7d)   │    │ 🍽 Food/Restaurant:          │
    │ • Weather (modifier) │    │   BLS CPI deltas            │
    │ • Permits/zoning     │    │   USDA commodity prices     │
    │ • Municipal notices   │    │   FDA recalls               │
    │ • Local news         │    │   Menu cost implications    │
    │ • Google Trends      │    │                             │
    │ • Demographics       │    │ 💈 Services: licensing       │
    │ • Market density     │    │ 🏪 Retail: consumer trends   │
    │                      │    │                             │
    │ (runs for ALL types) │    │ (only runs if relevant)     │
    └──────────────────────┘    └─────────────────────────────┘
```

### Existing Code to Reuse

| Component | Existing File | What It Does | Pulse Reuse |
|-----------|--------------|-------------|-------------|
| BLS CPI data | `lib/integrations/hephae_integrations/bls_client.py` | 2-year CPI history by food category | Extend: add MoM delta calculation |
| USDA commodity prices | `lib/integrations/hephae_integrations/usda_client.py` | Agricultural price data | Use as-is for food industry plugin |
| FDA recalls | `lib/integrations/hephae_integrations/fda_client.py` | Food safety enforcement | Use as-is for food industry plugin |
| OSM business counts | `lib/integrations/hephae_integrations/osm_client.py` | `discover_businesses(zip_code, category)` | Use for market density (NAICS-like counts) |
| Google Trends | `lib/db/hephae_db/bigquery/reader.py` | `query_google_trends(dma)`, `query_industry_trends(industry, dma)` | Use as-is; add "rising terms" extraction |
| Weather forecast | `agents/hephae_agents/traffic_forecaster/tools.py` | `get_weather_forecast(lat, lon)` → NWS 3-day | Use as modifier input |
| Zipcode research | `agents/hephae_agents/research/zipcode_research.py` | 9-category Google Search research | Reuse for events, infrastructure, seasonal patterns |
| Demographics | `agents/hephae_agents/research/demographic_expert.py` | Census/ACS data via search | Replace with direct Census API client |
| Local catalyst | `agents/hephae_agents/research/local_catalyst.py` | Town council, planning board, zoning | Extend: add DPW road closures |
| Area summary | `agents/hephae_agents/research/area_summary.py` | Multi-zip synthesis | Reference pattern for Pulse synthesis |
| Output schemas | `lib/db/hephae_db/schemas/agent_outputs.py` | `_NullSafeModel` base, 8+ Pydantic models | Follow pattern for new `WeeklyPulseOutput` |
| ADK helpers | `lib/common/hephae_common/adk_helpers.py` | `run_agent_to_json()` with `response_schema` | Use for all new agents |
| Firestore CRUD | `lib/db/hephae_db/firestore/businesses.py` | Async wrappers over sync Firestore | Follow pattern for `briefings.py` |
| Admin router | `apps/api/hephae_api/routers/admin/area_research.py` | POST + SSE stream + Depends(verify_admin_request) | Follow pattern for `briefings.py` router |
| Config/versions | `apps/api/hephae_api/config.py` | `AgentVersions` + `Settings` | Add `WEEKLY_PULSE = "1.0.0"` |

---

### Phase 1: Data Plumbing (extend existing clients)

| # | Task | File | Details |
|---|------|------|---------|
| 1a | BLS delta calculation | `lib/integrations/.../bls_client.py` | Add `query_bls_cpi_deltas()` → returns MoM and YoY % change per food category. Wraps existing `query_bls_cpi()`. |
| 1b | News client | `lib/integrations/.../news_client.py` | **NEW.** Google News RSS (`q={city}+{state}&gpc={zip}`) + Patch.com RSS. Returns `[{title, source, url, date, snippet}]`. Both are simple HTTP GET → RSS parse. |
| 1c | Local catalyst DPW | `agents/.../research/local_catalyst.py` | Extend instruction prompt to explicitly search for: road closures, paving schedules, utility shutoffs, DPW bulletins. Add targeted search queries. |
| 1d | Census API client | `lib/integrations/.../census_client.py` | **NEW.** Direct REST calls to `api.census.gov` for ZBP (establishment counts by NAICS per ZIP) and ACS 5-Year (income, population, age). Cache annually in Firestore. Replaces agent-based Google Search approach. |

**Verification**: Run each client standalone against 3 test zipcodes (07110, 07109, 07042). Confirm structured data returns.

---

### Phase 2: Intelligence Layer (core build)

| # | Task | File | Details |
|---|------|------|---------|
| 2a | `WeeklyPulseOutput` schema | `lib/db/.../schemas/briefing_outputs.py` | **NEW.** Pydantic v2 model extending `_NullSafeModel`. Fields: `zipCode`, `businessType`, `weekOf`, `headline`, `insights: list[InsightCard]`, `quickStats`. `InsightCard` has: `rank`, `title`, `analysis`, `recommendation`, `impactScore` (0-100), `impactLevel`, `timeSensitivity`, `signalSources: list[str]`. |
| 2b | Industry plugin registry | `agents/.../research/industry_plugins.py` | **NEW.** Maps business types → data fetcher functions. Pattern: `INDUSTRY_PLUGINS = {"food": [IndustryPlugin("food_prices", fetch_bls_cpi_deltas), ...], "services": [...], "retail": [...]}`. Gate with `get_industry_type(naics_or_category) → "food" | "services" | "retail" | None`. |
| 2c | `WeeklyPulseAgent` | `agents/.../research/weekly_pulse.py` | **NEW.** `LlmAgent` with DEEP thinking mode. Instruction prompt performs the 5 synthesis tasks: cross-correlate, quantify impact, detect anomalies, generate recommendations, prioritize. Uses `response_schema=WeeklyPulseOutput` for native structured output. |
| 2d | `run_weekly_pulse()` runner | `agents/.../research/weekly_pulse_runner.py` | **NEW.** Stateless async runner. Orchestrates: (1) fetch base layer signals in parallel (weather, events, permits, news, trends, demographics, market density), (2) fetch industry plugin data if applicable, (3) load prior week's pulse for delta detection, (4) call `WeeklyPulseAgent` with all signals, (5) return `WeeklyPulseOutput`. |
| 2e | Firestore CRUD | `lib/db/.../firestore/briefings.py` | **NEW.** `save_weekly_pulse(zip_code, business_type, week_of, data)`, `get_weekly_pulse(zip_code, business_type, week_of)`, `get_pulse_history(zip_code, business_type, weeks=4)`. Collection: `zipcode_weekly_pulse`. Doc ID: `{zipCode}-{businessType}-{weekOf}`. Follow `businesses.py` async pattern. |
| 2f | Admin API endpoints | `apps/api/.../routers/admin/briefings.py` | **NEW.** `POST /api/briefings/generate` (trigger pulse for zip + business type), `GET /api/briefings/{zip}/{type}/latest` (get latest), `GET /api/briefings/{zip}/{type}/history` (get last N weeks). Follow `area_research.py` pattern with `Depends(verify_admin_request)`. |
| 2g | Wire up | `config.py`, `main.py` | Add `WEEKLY_PULSE = "1.0.0"` to `AgentVersions`. Register briefings router in `main.py`. |

**Verification**: Generate a pulse for zipcode 07110 + "restaurants" via admin endpoint. Manually review the 3-5 insight cards for quality. Check that cross-signal correlation is actually happening (not just listing signals independently).

---

### Phase 3: Automation (deferred)

- Weekly Cloud Scheduler cron: `POST /api/cron/weekly-pulse` (Monday 6am ET)
- Iterates all active zip codes from `zipcode_weekly_pulse` collection
- Generates pulse per zip + business type combo
- Stores results, computes deltas vs prior week

### Phase 4: Outreach Integration (deferred)

- Cross-reference pulse insights with per-business capability outputs (SEO audit, competitive analysis)
- Generate ICS-framed outreach per business using `OutreachAgent`
- Email delivery via existing `hephae_common/email.py`
- Track opens/clicks in `outreachBatch` field

---

### File Tree (new files only)

```
lib/integrations/hephae_integrations/
├── news_client.py                    # NEW — Google News RSS + Patch.com
├── census_client.py                  # NEW — Census ZBP + ACS direct API

agents/hephae_agents/research/
├── weekly_pulse.py                   # NEW — WeeklyPulseAgent (synthesis LLM)
├── weekly_pulse_runner.py            # NEW — Stateless orchestrator runner
├── industry_plugins.py               # NEW — Industry plugin registry

lib/db/hephae_db/
├── schemas/briefing_outputs.py       # NEW — WeeklyPulseOutput Pydantic model
├── firestore/briefings.py            # NEW — Firestore CRUD for weekly_pulse

apps/api/hephae_api/routers/admin/
├── briefings.py                      # NEW — Admin API endpoints

# Modified files:
lib/integrations/.../bls_client.py    # EXTEND — add delta calculation
agents/.../research/local_catalyst.py # EXTEND — add DPW search
apps/api/hephae_api/config.py        # EXTEND — add WEEKLY_PULSE version
apps/api/hephae_api/main.py          # EXTEND — register briefings router
```

---

### Testing Strategy

| Test | What It Validates | Location |
|------|------------------|----------|
| `test_bls_deltas` | MoM/YoY delta calculation returns correct percentages | `tests/integrations/` |
| `test_news_client` | Google News RSS + Patch.com returns structured results for 3 test zips | `tests/integrations/` |
| `test_census_client` | ZBP returns establishment counts, ACS returns demographics for 3 test zips | `tests/integrations/` |
| `test_weekly_pulse_output_schema` | `WeeklyPulseOutput` validates correctly, handles nulls via `_NullSafeModel` | `tests/schemas/` |
| `test_industry_plugins` | Plugin registry returns correct fetchers for "food", "services", "retail" | `tests/agents/` |
| `test_run_weekly_pulse` | End-to-end runner for 07110 + "restaurants" produces valid insight cards | `tests/capabilities/` |
| `test_briefings_crud` | Save/read/history Firestore operations work correctly | `tests/db/` |
| `test_briefings_api` | Admin endpoints return correct responses, auth gate works | `tests/api/` |
| `test_pulse_quality_eval` | Evaluator agent scores pulse output ≥80 on relevance, actionability, cross-signal usage | `tests/evals/` |
