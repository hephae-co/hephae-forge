# Hephae "Zipcode Pulse" Intelligence: Strategic Implementation Plan

**Objective**: Pivot from business-level analysis to high-velocity zipcode-level intelligence. Provide cross-signal analysis and quantified recommendations that local businesses can't produce themselves, delivered weekly to build trust and drive outreach conversion.

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

## 2. Data Strategy: The "Clean" Signal Stack

ToS-compliant, public government and media signals only. Every data source evaluated on: non-obvious to owner, ToS-compliant, API reliability, signal freshness, already built.

### P0 — BigQuery Intelligence Layer (The "Plumbing")

We will prioritize BigQuery public datasets over external APIs. This allows for spatial joins across search demand, demographics, and competitive density in a single query.

| Signal Domain | BigQuery Dataset | Strategic Value |
| :--- | :--- | :--- |
| **Search Demand** | `google_trends.top_terms` | DMA-level consumer interest shifts. |
| **Demographics** | `census_bureau_acs` | ACS 5-Year data by ZCTA (movers, income). |
| **Market Density** | `geo_openstreetmap` | POI-level business saturation and layout. |
| **Labor/Economy** | `bls.qcew` | County-level wage/employment shifts (NAICS). |
| **Weather/Climate**| `noaa_gsod` | Historical daily climate anomalies vs traffic. |
| **Investment** | `sba.7a_loans` | Local business funding and expansion activity. |
| **Geo-Bridging** | `geo_us_boundaries` | Zip-to-County-to-DMA spatial polygons. |

---

## 3. Architecture: From Data to Operational Advice

### Phase 1: The BQ Pulse Client
- **`bigquery_pulse_client.py`**: A unified service that joins the "Glue" datasets (boundaries) with "Signals" (Census, BLS, NOAA) to produce a per-zipcode economic snapshot.
- **`news_client.py`**: Supplemental tool for hyper-local media (Google News RSS).
- **`ZipCodeResearchAgent`**: Now acts as a **"Metadata Auditor"**, verifying BQ findings against real-time municipal notices and event calendars.

**NJ DOS Legal Notices**: NJ law S4654/A5878 (signed July 2025, effective March 2026) moved legal notice requirements to official government websites. This created a **centralized, machine-readable feed** of land use applications, budget hearings, procurement notices, and zoning changes. No other platform is indexing this yet.

### P2 — Supplemental (fragile, coarse, or infrequent)

| Signal | Source | Issue | Verdict |
|--------|--------|-------|---------|
| **Local news** | Google News RSS + Patch.com RSS | Google RSS is undocumented/fragile. Patch covers ~1,000 communities only. | Useful as input to LLM cross-referencing, never standalone. |
| **Air quality** | EPA AirNow API | Niche — outdoor dining/retail only | Build when core is stable |
| **SBA loan approvals** | data.sba.gov | 3-6 month lag | Quarterly competitive overlay |
| **Energy costs** | EIA API | State-level only | Too coarse to be personal |

### P3 — Do NOT Build

| Source | Why Not |
|--------|---------|
| **Yelp Fusion API** | ToS restricts aggregated data to "non-commercial analysis." **Use OSM + Census ZBP instead.** |
| **Google Places API** | $7-30/request. ToS restricts competitive analysis. **Use OSM instead.** |
| **Health inspection scores** | Fragmented across NJ's 21 counties. No unified API. Per-county scraping = brittle. |
| **Liquor license filings** | NJ has no clean API. |
| **County clerk records** | 21 systems, mostly scanned PDFs. Impractical at scale. |
| **Mobile foot traffic** (Placer.ai, XMAP) | Enterprise contracts ($$$). Not public API. |
| **Chamber of Commerce data** | Gated behind membership. Existing MunicipalHubAgent already handles discovery. |

### Hard Limits (physically cannot be done)

- **BLS CPI below metro level** — 23 metro areas is the finest grain
- **USDA prices below ~10 metro regions** — national/regional only
- **Google Trends below DMA** — BigQuery hard limit (~210 US regions)
- **Unified national event calendar API** — doesn't exist

---

## 3. Architecture: Base Layer + Industry Plugins

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

Base layer runs once per zip per week. Industry plugins run conditionally per business type. Adding a new industry = adding a plugin — the synthesis agent doesn't change.

### The Synthesis Formula

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

1. **Cross-correlate** — What combinations of signals create opportunities or threats?
2. **Quantify impact** — Based on historical patterns, expected magnitude? (0-100 impact score + dollar estimates)
3. **Detect anomalies** — What's different this week vs trailing 4-week average?
4. **Generate recommendations** — What should the owner DO? Not "be aware of X" but specific actions.
5. **Prioritize** — Rank by actionability and time-sensitivity (`this_week` > `this_month` > `this_quarter`)

---

## 4. Output: Insight Cards, Not Data Dumps

Each Weekly Pulse produces **3-5 ranked insight cards**:

```json
{
  "zipCode": "07110",
  "businessType": "Restaurants",
  "weekOf": "2026-03-16",
  "headline": "Street fair + warm weekend = prime opportunity, but dairy costs are squeezing margins",
  "insights": [
    {
      "rank": 1,
      "title": "Saturday street fair: capture the 5-8pm dinner surge",
      "analysis": "Nutley Spring Fair (Sat 12-8pm, ~2,000 attendees) + 72°F forecast. In 6 similar past events, restaurants within 0.3mi saw 30-40% higher dinner covers. Oak St closure shifts parking to your side of town.",
      "recommendation": "Feature your 3 highest-margin items as a 'Fair Weekend Special'. Consider sidewalk seating if permitted. Peak window: 5:30-7:30pm.",
      "impactScore": 85,
      "impactLevel": "high",
      "timeSensitivity": "this_week",
      "signalSources": ["events", "weather", "road_closures"]
    },
    {
      "rank": 2,
      "title": "Dairy costs up 12% — menu margin alert",
      "analysis": "BLS CPI for dairy products rose 12.1% YoY (vs 3.2% overall food inflation). Cream-based dishes cost ~$0.40 more per plate. Meanwhile, poultry is DOWN 5.3%.",
      "recommendation": "Shift weekly special from cream-based to grilled chicken dishes. Consider a temporary price adjustment on cream-heavy items (+$0.50-1.00).",
      "impactScore": 65,
      "impactLevel": "medium",
      "timeSensitivity": "this_month",
      "signalSources": ["bls_cpi", "usda_commodities"]
    },
    {
      "rank": 3,
      "title": "New liquor license filed at 340 Franklin Ave",
      "analysis": "A new restaurant/bar permit filed 0.2mi from main corridor. Applicant: 'Franklin Social'. Expected opening: Q3 2026. 4th full-service restaurant within 2 blocks.",
      "recommendation": "Monitor — increasing competition on Franklin corridor. Strengthen unique positioning (family-friendly, cuisine specialty, etc.).",
      "impactScore": 30,
      "impactLevel": "low",
      "timeSensitivity": "this_quarter",
      "signalSources": ["permits", "market_density"]
    }
  ],
  "quickStats": {
    "trendingSearches": ["outdoor dining nutley", "brunch near me", "pizza delivery 07110"],
    "weatherOutlook": "Warm weekend (72°F Sat, 68°F Sun), rain Monday",
    "upcomingEvents": 3,
    "priceAlerts": 1
  }
}
```

---

## 5. Outreach Framework: ICS (Insight → Comparison → Strategy)

### Why Not "Threat → Quantification → Solution"?

The old TQS frame assumed the owner doesn't know the threat. They often do. Leading with "Main St is closing!" when they drive on it daily insults their intelligence. ICS leads with **insight they CAN'T get on their own**:

| Step | What It Does | Example |
|------|-------------|---------|
| **INSIGHT** | Data point they CANNOT get by walking down the street | "3 of the 14 restaurants in your zip added delivery this month — you're now one of only 4 without it." |
| **COMPARISON** | Benchmark vs comparable businesses, adjacent zips, or history | "In zips where delivery adoption passed 75%, the holdouts lost 12% of dine-in base within 6 months." |
| **STRATEGY** | Specific play — not "hire us" but "here's what to do" | "We built a launch-week delivery promotion template. Includes platform setup, social sequence, and margin calculator." |
| **CTA** | Low-friction value delivery, not a meeting request | "Reply 'DELIVERY' and we'll send it — free, no strings." |

### The Endowment Effect Conversion Loop

After 2-3 free Weekly Pulse reports, the owner feels ownership over the intelligence ("MY weekly briefing"). Losing access becomes more painful than paying. Use possessive language: "Your Nutley Dashboard," "Your weekly intel."

### Anti-Patterns

- **Telling them what they already know** — weather, nearby events, obvious news. **#1 risk.**
- **Generic industry stats** — "restaurant margins are thin"
- **Pure doom without strategy** — "costs are rising" with no actionable play
- **Asking for meetings** — CTA = value delivery, not sales call
- **Long emails** — hook must land in 2 sentences

---

## 6. Competitive Moat: What Accumulates

| Timeframe | Differentiator |
|-----------|---------------|
| **Day 1** | Cross-signal correlation, Census market density, Google Trends demand signals, NJ DOS legal notice indexing |
| **3-6 months** | Longitudinal pattern detection, anomaly detection vs trailing average, seasonal calibration, delta reporting |
| **12+ months** | Cross-zip benchmarking ("zips where delivery adoption passed 75%..."), predictive models from 52 weeks × 200 zips, proprietary economic history per zip |

| Dimension | Business-First (Current) | Zipcode-First (Pulse) |
|-----------|------------------------|-----------------------|
| **Research cost** | 1 business = 1 full pipeline | 1 zip = 50+ businesses served |
| **Outreach frame** | "Your SEO is bad" (critique) | "Your zip's costs are shifting" (intelligence) |
| **Owner perception** | "Another agency cold-pitching me" | "Someone is looking out for me" |
| **Data moat** | Ephemeral (each report is one-off) | Cumulative (weekly history = proprietary) |
| **Scalability** | Linear (more biz = more cost) | Sublinear (more biz per zip = lower marginal cost) |

---

## 7. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Pulse tells owners what they already know** | HIGH | Every insight card must pass the "walking down the street" test. Weather/events/closures are modifiers only. |
| **Cross-signal correlation produces hallucinated insights** | HIGH | Gemini structured output + DEEP thinking; human QA on first 10 zips |
| **Google News RSS breaks** | MEDIUM | Patch.com + NJLM as fallbacks; never sole dependency |
| **NJ DOS Legal Notice portal changes structure** | MEDIUM | Build parser defensively; monitor for changes |
| **NJ-specific sources don't generalize** | MEDIUM | State-agnostic interfaces; NJ is pilot market |
| **Owner perceives Pulse as spam** | MEDIUM | Genuine value in every issue; 1-click unsubscribe; max 1x/week |

---

## 8. Implementation Roadmap

### Phase 1: Data Plumbing (extend existing clients)

| # | Task | File | Details |
|---|------|------|---------|
| 1a | BLS delta calculation | `lib/integrations/.../bls_client.py` | Add `query_bls_cpi_deltas()` → MoM and YoY % change per food category |
| 1b | News client | `lib/integrations/.../news_client.py` | **NEW.** Google News RSS + Patch.com RSS |
| 1c | Local catalyst DPW | `agents/.../research/local_catalyst.py` | Extend: road closures, paving schedules, utility shutoffs |
| 1d | Census API client | `lib/integrations/.../census_client.py` | **NEW.** Direct `api.census.gov` for ZBP + ACS 5-Year |

### Phase 2: Intelligence Layer (core build)

| # | Task | File | Details |
|---|------|------|---------|
| 2a | `WeeklyPulseOutput` schema | `lib/db/.../schemas/briefing_outputs.py` | **NEW.** Pydantic v2 model with insight cards |
| 2b | Industry plugin registry | `agents/.../research/industry_plugins.py` | **NEW.** Maps business types → data fetchers |
| 2c | `WeeklyPulseAgent` | `agents/.../research/weekly_pulse.py` | **NEW.** LlmAgent with DEEP thinking + `response_schema` |
| 2d | Runner | `agents/.../research/weekly_pulse_runner.py` | **NEW.** Orchestrates data gathering → synthesis |
| 2e | Firestore CRUD | `lib/db/.../firestore/briefings.py` | **NEW.** `zipcode_weekly_pulse` collection |
| 2f | Admin API | `apps/api/.../routers/admin/briefings.py` | **NEW.** Generate, preview, history endpoints |
| 2g | Wire up | `config.py`, `main.py` | Add version, register router |

### Phase 3: Automation (deferred)

- Weekly Cloud Scheduler cron: Monday 6am ET
- Iterates active zip codes, generates pulse per zip + business type

### Phase 4: Outreach Integration (deferred)

- Cross-reference pulse with per-business capabilities (SEO, competitive)
- ICS-framed outreach per business
- Email delivery via Resend
- Endowment effect conversion loop

---

### Data Persistence

**Collection**: `zipcode_weekly_pulse`
**Doc ID**: `{zipCode}-{businessType}-{weekOf}` (e.g., `07110-restaurants-2026-03-16`)

Weekly snapshots → proprietary historical record. Firestore initially, BigQuery when cross-zip analysis needed.

---

**Current Phase**: Phase 1-2 (generate + store + admin preview). Outreach deferred until manual quality review confirms briefing quality.
