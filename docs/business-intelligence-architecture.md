# Hephae Business Intelligence Architecture

## Vision

Transform Hephae from a "food price alert system" into a **comprehensive local business intelligence platform** that monitors 7 signal categories across any industry vertical. Every signal should answer: "What should this business owner do THIS WEEK?"

## The 7 Signal Categories

### 1. Cost Dynamics (existing, needs expansion)
**What it answers:** "Are my costs going up or down? Where's the opportunity?"

| Signal | Source | Frequency | Industries |
|--------|--------|-----------|-----------|
| BLS CPI by category | BLS API (free) | Monthly | All (industry-specific series) |
| USDA commodity prices | USDA ERS API (free) | Weekly | Food verticals |
| FDA recalls | FDA RSS (free) | Daily | Food verticals |
| Energy/utilities CPI | BLS SAH21 | Monthly | All (especially barber, salon) |
| Rent CPI | BLS SEHA | Monthly | All brick-and-mortar |

**Architecture:** Already built in `bls_client.py` + `pulse_fetch_tools.py`. Fixed in this session to be industry-aware.

---

### 2. Competitive Landscape
**What it answers:** "Who's opening/closing near me? Am I gaining or losing ground?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| Nearby business density | BigQuery OSM (free) | Weekly refresh | Already built |
| New business openings | Yelp Fusion API (free tier) | Weekly | API key needed |
| Business closings/status changes | Google Places API | Weekly | Already have key |
| Establishment birth/death rates | Census BDS API (free) | Annual | No auth needed |
| SBA loans in area | SBA API (free) | Monthly | No auth needed |
| QCEW employment dynamics | BLS QCEW (free) | Quarterly | Already built |
| Competitor ratings/reviews | Google Places API | Weekly | Already have key |

**New to build:**
- Yelp Fusion integration: search for recent openings by category + zip
- Google Places "recently opened" filter
- Census BDS loader for annual establishment dynamics
- Competitor rating tracker (detect when a competitor's rating changes significantly)

---

### 3. Technology & AI Opportunities
**What it answers:** "Is there a new tool that could save me money or grow revenue?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| Industry-specific product launches | Product Hunt RSS (free) | Daily | RSS feed |
| Startup funding rounds | Crunchbase API (paid) or TechCrunch RSS (free) | Weekly | RSS free, API paid |
| AI tool announcements | Google Search grounding | Weekly | Already built |
| Industry tech adoption trends | Trade publication RSS | Weekly | RSS feeds |
| Booking/POS platform updates | Platform blogs RSS | Weekly | RSS feeds |

**Industry-specific tech sources:**
- **Restaurant:** Toast blog, Square for Restaurants, DoorDash Merchant blog, OpenTable insights
- **Bakery:** Toast, Square, BentoBox, Ordermark
- **Barber:** SQUIRE blog, Booksy blog, Vagaro, Boulevard

**New to build:**
- RSS feed aggregator agent (ADK agent with crawl4ai that checks 5-10 RSS feeds per industry)
- Tech opportunity classifier (LLM agent that reads tech news and determines: "Is this relevant to a barber shop owner in NJ?")
- Google Search grounding query per industry: "[industry] AI tools 2026" + "[industry] booking platform new features"

---

### 4. Startup Ecosystem
**What it answers:** "Are new companies building tools for my industry? What's coming?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| Vertical-specific funding | TechCrunch RSS (free) | Daily | RSS |
| New products in category | Product Hunt RSS (free) | Daily | RSS |
| Hiring trends (are startups hiring for my vertical?) | LinkedIn (limited free) | Monthly | API |
| Industry conference announcements | Google Search grounding | Monthly | Already built |

**This overlaps with Category 3.** Merge into a single "Innovation & Technology" signal that the LLM agent researches weekly via Google Search grounding + RSS feeds.

---

### 5. Regulatory & Compliance
**What it answers:** "Is there a new regulation I need to comply with? Am I at risk?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| NJ state regulations | data.nj.gov API (free) | As published | REST API |
| NJ licensing changes | NJ Consumer Affairs | Monthly | Web scrape |
| FDA food safety updates | FDA RSS (free) | Daily | RSS |
| Minimum wage changes | DOL (free) | Annual + legislative | Manual + news |
| Health inspection results | County health dept | Varies | Some have APIs |
| AHP legislative updates (barber) | AHP website | Bi-weekly | Web scrape |
| NJ labor law changes | NJBIZ RSS (free) | Weekly | RSS |

**New to build:**
- NJ regulatory monitor agent (Google Search grounding: "NJ [industry] regulation 2026")
- FDA RSS parser (already have recall data, add safety alerts)
- Minimum wage tracker (simple: store current rate, alert on legislative changes)

---

### 6. Local Demand Signals
**What it answers:** "Is demand going up or down THIS WEEK? Why?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| Weather forecast + impact | NWS API (free) | Daily | Already built |
| Local events | Google Search grounding | Weekly | Already built |
| Google Trends (local) | Google Trends API (alpha) or grounding | Weekly | Grounding works |
| Seasonal patterns | Historical pulse data | Weekly | Already collecting |
| Community sentiment | Reddit RSS, Patch.com | Weekly | Already built |
| School calendar | School district websites | Seasonal | Crawl4ai |
| Holiday calendar | Deterministic | Annual | Hardcoded |

**Already mostly built** in the pulse pipeline (weather, events, social pulse, local catalysts). The gap is:
- PredictHQ integration for event impact scoring (paid but powerful)
- Google Trends integration for local search interest shifts
- Historical pattern detection from accumulated pulse data

---

### 7. Industry-Specific Economics
**What it answers:** "How is my industry doing nationally/regionally?"

| Signal | Source | Frequency | Access |
|--------|--------|-----------|--------|
| Industry employment trends | BLS QCEW (free) | Quarterly | Already built |
| Industry revenue benchmarks | Census Annual Business Survey | Annual | Free API |
| Trade publication insights | Industry RSS feeds | Weekly | RSS |
| Industry sentiment | Reddit communities | Weekly | RSS |
| Public company earnings (proxy) | SEC EDGAR (free) | Quarterly | Free API |

**New to build:**
- Industry RSS aggregator (per-industry feed list from the audit findings)
- SEC EDGAR integration for publicly traded industry leaders (e.g., track Dine Brands for restaurant trends)
- Census Annual Business Survey loader

---

## Architecture: Signal → Playbook → Insight

```
┌─────────────────────────────────────────────┐
│         SIGNAL COLLECTION LAYER             │
│                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ BLS CPI  │ │ OSM/BQ   │ │ Google   │   │
│  │ USDA     │ │ Yelp     │ │ Search   │   │
│  │ FDA RSS  │ │ Census   │ │ Grounding│   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       │             │             │         │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐   │
│  │ RSS Feeds│ │ NJ Data  │ │ Weather  │   │
│  │ Tech/AI  │ │ Regulatory│ │ Events  │   │
│  │ Industry │ │ Licensing │ │ Trends  │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       └─────────────┼─────────────┘         │
│                     ▼                       │
│         ┌───────────────────┐               │
│         │  SIGNAL STORE     │               │
│         │  (Firestore)      │               │
│         └─────────┬─────────┘               │
└───────────────────┼─────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│         PLAYBOOK ENGINE                     │
│                                             │
│  For each industry:                         │
│    1. Deterministic triggers (thresholds)   │
│    2. LLM-evaluated triggers (semantic)     │
│    3. Cross-signal correlation triggers     │
│                                             │
│  Trigger types:                             │
│    NUMERIC: "dairy_mom_pct > 1.0"          │
│    SEMANTIC: "new competitor opened nearby" │
│    TEMPORAL: "wedding season + ingredient   │
│               price spike"                  │
│    TECHNOLOGY: "new AI scheduling tool      │
│                 launched for barbers"        │
│                                             │
│  Output: list[TriggeredPlaybook]            │
│    - name, category, play_text, data_points │
│    - confidence: HIGH/MEDIUM/LOW            │
│    - urgency: THIS_WEEK / THIS_MONTH /      │
│               INFORMATIONAL                  │
└─────────────────┬───────────────────────────┘
                  ▼
┌─────────────────────────────────────────────┐
│         SYNTHESIS LAYER (existing)          │
│                                             │
│  ADK agents combine:                        │
│    - Triggered playbooks                    │
│    - Raw signal data                        │
│    - Industry context                       │
│    - Local/zipcode context                  │
│                                             │
│  Output: Weekly pulse with insights         │
└─────────────────────────────────────────────┘
```

## Playbook Types (New)

### Type 1: Numeric Threshold (existing, fixed)
```python
{
    "name": "dairy_margin_swap",
    "type": "numeric",
    "trigger": "dairy_mom_pct > 1.0 and poultry_mom_pct < 0",
    "play": "Swap cream dishes for grilled proteins...",
    "category": "cost_dynamics",
    "urgency": "this_week",
}
```

### Type 2: Semantic (NEW — LLM-evaluated)
```python
{
    "name": "new_competitor_response",
    "type": "semantic",
    "signal_source": "competitive_landscape",
    "trigger_prompt": "Has a new business opened within 500m that competes directly with this business type?",
    "play": "New {competitor_name} opened at {address}. Differentiate: ...",
    "category": "competitive",
    "urgency": "this_week",
}
```
The LLM agent evaluates whether the signal data matches the trigger prompt and returns true/false + extracted variables.

### Type 3: Technology Opportunity (NEW — LLM-evaluated)
```python
{
    "name": "ai_scheduling_tool",
    "type": "technology",
    "signal_source": "tech_innovation",
    "trigger_prompt": "Is there a new AI or technology tool relevant to {industry} that could save time or increase revenue?",
    "play": "{tool_name} just launched — it {value_prop}. Check it out at {url}.",
    "category": "technology",
    "urgency": "informational",
}
```

### Type 4: Cross-Signal Correlation (NEW)
```python
{
    "name": "event_plus_weather_staffing",
    "type": "cross_signal",
    "triggers": [
        "event_count > 0",
        "weather_traffic_modifier > 0",
    ],
    "play": "Good weather + local events = spike incoming. Staff up Saturday.",
    "category": "demand",
    "urgency": "this_week",
}
```

## Implementation Phases

### Phase 1: Fix What's Broken (DONE ✓)
- ✓ BLS series per industry (barber gets services, not food)
- ✓ Playbook triggers use MoM% (actually populated)
- ✓ Restaurant scout_context and critique_persona
- ✓ Alias coverage for all 3 industries

### Phase 2: RSS + News Intelligence Layer (1-2 weeks)
- Build RSS feed aggregator ADK agent
- Configure per-industry feed lists (from audit findings)
- Tech/AI opportunity detection via Google Search grounding per industry
- Store aggregated intelligence in Firestore (per-industry, weekly)
- Wire into existing pulse pipeline as a new signal source

### Phase 3: Competitive Intelligence Layer (1-2 weeks)
- Yelp Fusion API integration (new openings, rating changes)
- Google Places competitor monitoring (rating/review count tracking over time)
- Census BDS annual establishment dynamics loader
- Competitor change detection (new, closed, rating drop/spike)

### Phase 4: Semantic Playbook Engine (2-3 weeks)
- New playbook types: semantic, technology, cross-signal
- LLM-evaluated triggers (ADK agent reads signals, evaluates trigger prompts)
- Confidence scoring (HIGH/MEDIUM/LOW)
- Urgency classification (this_week/this_month/informational)
- Per-industry playbook library expansion (10-15 playbooks per industry)

### Phase 5: Regulatory Monitor (1 week)
- NJ regulatory Google Search grounding queries per industry
- FDA RSS parser for food safety alerts
- Minimum wage / labor law tracker
- Licensing change detector

### Phase 6: Historical Pattern Detection (2-3 weeks)
- Analyze accumulated pulse data for seasonal patterns
- Predict demand based on historical same-week data
- Anomaly detection: "This week's foot traffic is 30% below the same week last year"
- Trend lines: "Your area has gained 3 competitors in 6 months"

## Data Source Priority Matrix

| Source | Cost | Setup Effort | Signal Value | Priority |
|--------|------|-------------|-------------|----------|
| Google Search grounding | Free (already have) | None | HIGH | P0 |
| BLS API | Free | Already built | HIGH | P0 ✓ |
| OSM via BigQuery | Free (1TB/mo) | Already built | HIGH | P0 ✓ |
| RSS feeds (trade pubs) | Free | 1 day | HIGH | P1 |
| Product Hunt RSS | Free | 1 hour | MEDIUM | P1 |
| TechCrunch RSS | Free | 1 hour | MEDIUM | P1 |
| Yelp Fusion API | Free tier | 1 day | HIGH | P1 |
| FDA RSS | Free | Already built | MEDIUM | P1 |
| Census BDS API | Free | 1 day | MEDIUM | P2 |
| NJ data.nj.gov | Free | 2 days | MEDIUM | P2 |
| FRED API | Free | Already built | MEDIUM | P2 |
| Google Trends Alpha | Free (limited) | Unknown | HIGH | P2 |
| PredictHQ | Paid | 1 week | HIGH | P3 |
| Crunchbase API | Paid ($49+/mo) | 2 days | MEDIUM | P3 |
| Zillow API | Free (limited) | 2 days | LOW | P3 |
| SEC EDGAR | Free | 3 days | LOW | P3 |
