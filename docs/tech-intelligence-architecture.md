# Technology Intelligence Layer Architecture

## Vision

A shared knowledge base that answers: "What technology exists RIGHT NOW that could help this business owner save time, reduce costs, or grow revenue?"

This is NOT about BLS data. This is about knowing that SQUIRE just launched AI appointment scheduling, or that Toast released a new inventory feature, or that there's an open-source recipe costing tool on GitHub that a bakery owner should know about.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          TECHNOLOGY INTELLIGENCE LAYER               │
│                                                     │
│  Runs: Weekly (Sunday, before industry + zip pulses) │
│  Scope: Per vertical (restaurant, bakery, barber)    │
│  Storage: Firestore 'tech_intelligence' collection   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  TechScout ADK Pipeline (per vertical)         │  │
│  │                                               │  │
│  │  Stage 1: PlatformMonitor (ParallelAgent)     │  │
│  │    ├── BookingScout (google_search)            │  │
│  │    ├── POSScout (google_search)               │  │
│  │    ├── MarketingScout (google_search)          │  │
│  │    ├── AIToolScout (google_search)            │  │
│  │    └── CommunityScout (google_search)         │  │
│  │                                               │  │
│  │  Stage 2: TechSynthesizer (LlmAgent)          │  │
│  │    Evaluates all findings, scores relevance,   │  │
│  │    produces structured TechProfile              │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Output: TechProfile per vertical                   │
│    ├── platforms: current landscape + recent changes │
│    ├── aiOpportunities: new AI tools + capabilities  │
│    ├── communityRecommendations: what owners use     │
│    ├── emergingTrends: what's coming next            │
│    └── weeklyHighlight: the ONE thing to know        │
└──────────────────┬──────────────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   Industry Pulse       Zipcode Pulse
   (reads tech profile)  (reads tech profile)
```

## Tech Categories Per Vertical

### Universal (all verticals)
| Category | What to scout | Example queries |
|----------|--------------|-----------------|
| **POS/Payments** | New features, pricing changes, integrations | "[vertical] POS system new features 2026" |
| **Online Presence** | Website builders, Google Business, SEO tools | "[vertical] website builder online presence 2026" |
| **Marketing/CRM** | Email, SMS, review management, social | "[vertical] marketing automation small business 2026" |
| **AI Tools** | Any AI capability relevant to the vertical | "[vertical] AI tools automation 2026" |
| **Accounting** | Bookkeeping, payroll, tax, financial tools | "small business accounting software [vertical] 2026" |
| **Staff Management** | Scheduling, payroll, hiring, training | "[vertical] staff scheduling software 2026" |

### Restaurant-Specific
| Category | What to scout | Key platforms |
|----------|--------------|--------------|
| **Order Management** | Online ordering, delivery aggregation | DoorDash, ChowNow, BentoBox, Ordermark, Olo |
| **Table/Reservation** | Booking, waitlist, capacity management | OpenTable, Resy, Yelp Reservations, Tock |
| **Kitchen/Inventory** | Recipe costing, inventory tracking, waste | MarketMan, BlueCart, CookUnity, Galley |
| **Menu Engineering** | Digital menus, pricing optimization, upselling | Popmenu, MustHaveMenus, Presto |
| **Delivery Optimization** | Route planning, packaging, commission management | Cartwheel, Cuboh, ItsaCheckmate |

### Bakery-Specific
| Category | What to scout | Key platforms |
|----------|--------------|--------------|
| **Custom Orders** | Online cake ordering, custom order management | CakeBoss, OrderCake, BakerHQ |
| **Recipe/Ingredient** | Recipe scaling, ingredient costing, sourcing | CostBrain, RecipeCost, FlexiBake |
| **Pre-orders** | Holiday pre-order systems, deposit management | Square, Toast, Shopify POS |
| **Wholesale** | B2B ordering for wholesale accounts | BlueCart, FoodServiceDirect |
| **Allergen Management** | Labeling, allergen tracking, compliance | MenuCalc, Nutritics |

### Barber-Specific
| Category | What to scout | Key platforms |
|----------|--------------|--------------|
| **Booking/Scheduling** | Appointment booking, waitlist, walk-in management | SQUIRE, Booksy, Vagaro, Boulevard, Fresha |
| **Chair/Booth Rental** | Booth rental management, commission tracking | DaySmart Salon, Rosy Salon Software |
| **Client Management** | CRM, service history, preferences, loyalty | SQUIRE, Booksy, GlossGenius |
| **Retail/Products** | Product sales, inventory, supplier ordering | Shopify POS, Square, Booksy marketplace |
| **Education/Certification** | Online training, CE credits, licensing | Barber Blueprint, National Barber Board |

## Scout Agent Design

### Per-Category Scout Agent

Each scout is an LlmAgent with google_search grounding. Its instruction:

```
You are a Technology Scout for {vertical} businesses.

Search for the LATEST news, updates, and launches in the {category} space.

Use these search strategies:
1. Platform-specific: "{platform_name} new features 2026" for each known platform
2. Vertical-specific: "{vertical} {category} software new 2026"
3. Community-sourced: "site:reddit.com/r/{subreddit} {category} recommendation"
4. Substack/blog: "site:substack.com {vertical} {category} tools"
5. Comparison/review: "best {category} software for {vertical} 2026"

For each finding, return JSON:
{
  "platform": "name",
  "category": "booking|pos|marketing|ai|operations|...",
  "update": "what's new or notable",
  "relevance": "HIGH|MEDIUM|LOW",
  "url": "source URL",
  "actionForOwner": "What should a {vertical} owner DO with this info?"
}

Return ONLY findings from the last 30 days. Skip anything older.
Prioritize: AI capabilities > new platform features > pricing changes > industry reports.
```

### TechSynthesizer Agent

Reads all scout outputs and produces the final TechProfile:

```
You are a Technology Advisor for {vertical} small businesses.

You've received findings from 5 technology scouts. Synthesize into a TechProfile.

Return JSON:
{
  "vertical": "{vertical}",
  "weekOf": "2026-W12",
  "platforms": {
    "booking": {"leader": "...", "recentUpdate": "...", "trend": "..."},
    "pos": {"leader": "...", "recentUpdate": "...", "trend": "..."},
    ...per category
  },
  "aiOpportunities": [
    {"tool": "...", "capability": "...", "relevance": "HIGH", "actionForOwner": "..."}
  ],
  "communityRecommendations": [
    {"source": "reddit/r/Barber", "tool": "...", "sentiment": "...", "quote": "..."}
  ],
  "emergingTrends": [
    {"trend": "...", "evidence": "...", "timeframe": "now|3months|6months"}
  ],
  "weeklyHighlight": {
    "title": "The ONE thing a {vertical} owner should know this week",
    "detail": "...",
    "action": "What to do about it"
  }
}

Rules:
- Only include VERIFIED findings (from scout results, not hallucinated)
- Prioritize what's ACTIONABLE for a small business owner
- weeklyHighlight should be the most impactful single finding
- If a platform raised prices, that's HIGH relevance
- If a new AI tool launched that saves time, that's HIGH relevance
- Generic "AI is transforming industry" statements are LOW relevance — skip them
```

## Firestore Schema

Collection: `tech_intelligence`
Document ID: `{vertical}-{weekOf}` (e.g., `barber-2026-W12`)

```json
{
  "vertical": "barber",
  "weekOf": "2026-W12",
  "generatedAt": "2026-03-22T...",
  "platforms": {
    "booking": {
      "leader": "SQUIRE",
      "alternatives": ["Booksy", "Vagaro", "Boulevard", "Fresha"],
      "recentUpdate": "SQUIRE launched AI-powered no-show prediction (March 2026)",
      "trend": "AI scheduling features becoming standard across all platforms"
    },
    "pos": {
      "leader": "Square",
      "alternatives": ["Toast", "Clover"],
      "recentUpdate": "Square added tap-to-pay on Android for booth renters",
      "trend": "Mobile-first POS replacing fixed terminals"
    }
  },
  "aiOpportunities": [
    {
      "tool": "SQUIRE AI Scheduler",
      "capability": "Predicts no-shows and auto-fills slots from waitlist",
      "relevance": "HIGH",
      "url": "https://...",
      "actionForOwner": "Enable no-show prediction in SQUIRE settings — could recover 3-5 lost appointments/week"
    }
  ],
  "communityRecommendations": [
    {
      "source": "reddit/r/Barber",
      "tool": "Booksy",
      "sentiment": "positive",
      "quote": "Switched from Vagaro to Booksy — the walk-in queue feature alone is worth it"
    }
  ],
  "emergingTrends": [
    {
      "trend": "AI-generated social media content for barbers",
      "evidence": "3 new tools launched in Q1 2026 (Lately, Jasper, Canva AI) with barber templates",
      "timeframe": "now"
    }
  ],
  "weeklyHighlight": {
    "title": "SQUIRE launches AI no-show prediction",
    "detail": "Analyzes booking history to predict which clients are likely to no-show, auto-fills from waitlist",
    "action": "If you use SQUIRE, enable this in Settings → AI Features. If not, this is a reason to consider switching."
  }
}
```

## How Industry + Zipcode Pulses Consume Tech Intelligence

### Industry Pulse
- Loads `tech_intelligence/{vertical}-{weekOf}` from Firestore
- Includes `weeklyHighlight` and `aiOpportunities` in the industry trend summary
- Industry playbooks can reference tech: "New AI scheduling tool available → promote to owners"

### Zipcode Pulse
- Loaded by BaseLayerFetcher alongside industry pulse
- `weeklyHighlight` injected into synthesis as a TECHNOLOGY section
- LocalScout uses platform names to check if local businesses are adopting them
- Synthesis agent can reference: "SQUIRE just launched AI scheduling — could save you 2 hours/week"

### State injection:
```python
# In BaseLayerFetcher, after loading industry pulse:
try:
    from hephae_db.firestore.tech_intelligence import get_tech_intelligence
    tech_profile = await get_tech_intelligence(industry.id, week_of)
    if tech_profile:
        state["techIntelligence"] = {
            "weeklyHighlight": tech_profile.get("weeklyHighlight"),
            "aiOpportunities": tech_profile.get("aiOpportunities", [])[:3],
            "platformUpdates": {
                cat: info.get("recentUpdate", "")
                for cat, info in tech_profile.get("platforms", {}).items()
                if info.get("recentUpdate")
            },
        }
except Exception as e:
    logger.warning(f"Tech intelligence load failed: {e}")
```

## Cron Schedule

```
Sunday 1:00 AM ET  → Tech Intelligence (all verticals)
Sunday 3:00 AM ET  → Industry Pulse (all industries) — reads tech intelligence
Monday 6:00 AM ET  → Zipcode Pulse (all zips) — reads industry pulse + tech intelligence
```

Tech Intelligence runs first because both Industry and Zipcode pulses consume it.

## Implementation Plan

### Phase 1: Firestore + Schema (30 min)
- Create `tech_intelligence` collection
- `get_tech_intelligence(vertical, week_of)` and `save_tech_intelligence(...)` functions
- Firestore index: vertical + weekOf

### Phase 2: TechScout ADK Pipeline (2-3 hours)
- Create `agents/hephae_agents/research/tech_scout.py`
- 5 parallel scout agents (booking, POS, marketing, AI, community)
- Each uses google_search with vertical-specific queries
- TechSynthesizer merges into TechProfile

### Phase 3: Runner + Cron (1 hour)
- `apps/api/hephae_api/workflows/orchestrators/tech_intelligence.py` — runner
- `apps/api/hephae_api/routers/batch/tech_intelligence_cron.py` — cron endpoint
- Cloud Scheduler: Sunday 1 AM ET

### Phase 4: Wire into Pulse Pipeline (1 hour)
- BaseLayerFetcher loads tech_intelligence from Firestore
- Synthesis instruction includes TECHNOLOGY section
- Industry pulse includes tech highlights in trend summary

### Phase 5: Per-Vertical Query Tuning (ongoing)
- Refine search queries per vertical based on results
- Add new verticals as they're onboarded
- Track which findings owners actually engage with
