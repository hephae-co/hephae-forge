# Hephae Intelligence Layers Architecture

## Core Insight

The zipcode profile is not just an inventory — it's the **instruction set** for what to crawl each week. Each confirmed source (municipal website, chamber of commerce, Patch, school district, etc.) becomes a target for weekly intelligence gathering.

## Two Intelligence Layers

### Layer 1: Industry Pulse (National/Regional)

Runs weekly per registered industry. Answers: "What's happening in my industry nationally?"

| Signal Category | Source | How We Get It | Status |
|----------------|--------|--------------|--------|
| **Cost dynamics** | BLS CPI (industry-specific series) | BLS API | ✅ Built + fixed |
| **Commodity prices** | USDA ERS | USDA API | ✅ Built |
| **Food safety** | FDA recalls | FDA RSS | ✅ Built |
| **Industry tech/AI** | Google Search grounding | ADK agent with targeted queries | 🔧 To build |
| **Regulatory (state)** | Google Search grounding | ADK agent: "NJ [industry] regulation 2026" | 🔧 To build |
| **Industry trends** | Google Search grounding | ADK agent with industry context | ✅ Built |
| **Trade insights** | Google Search grounding | ADK agent: queries from social_search_terms | ✅ Built |

**Tech/AI Opportunity Detection** (new agent in industry pulse):
```
For each industry, the agent searches with queries like:
- "[industry] AI tools new features 2026"
- "[industry] booking scheduling software new"
- "[industry] POS system new features"
- "[industry] automation technology small business"
- "site:substack.com [industry] technology tools"
- "site:reddit.com/r/[industry_subreddit] software OR app OR tool"
```
The LLM evaluates each result: "Is this relevant to a small [industry] business owner? Would it save them time or money?" Returns structured opportunities.

**What it does NOT do:**
- Local competitor tracking (that's zipcode-level)
- Local events (that's zipcode-level)
- Weather (that's zipcode-level)

---

### Layer 2: Zipcode Pulse (Local)

Runs weekly per registered zipcode × business type. Answers: "What's happening in MY neighborhood THIS WEEK?"

#### Existing Signals (already built)

| Signal | Source | Status |
|--------|--------|--------|
| Weather forecast + baseline | NWS API | ✅ |
| Census demographics | BigQuery public data | ✅ |
| OSM business density | BigQuery public data | ✅ |
| Google Trends (local) | Google Search grounding | ✅ |
| Local news | Google Search grounding | ✅ |
| Community sentiment | Google Search grounding (Reddit, social) | ✅ |
| BLS CPI (from industry pulse) | Inherited | ✅ |
| QCEW employment | BLS QCEW | ✅ |
| IRS income data | IRS SOI | ✅ |

#### New: Source-Aware Intelligence Gathering

The zipcode profile tells us exactly which sources exist for each zip. The BaseLayerFetcher (or a new parallel agent) crawls them weekly for fresh intel.

**Municipal Sources** (from zipcode profile):
| Profile Source | What to Extract | Crawl Strategy |
|---------------|----------------|----------------|
| `municipal_website` | Building permits, certificates of occupancy, business licenses | Crawl4ai: look for "new business", "permit", "certificate" |
| `planning_zoning_board` | New development applications, zoning changes | Crawl4ai: latest agendas/minutes |
| `meeting_minutes` | Board decisions affecting businesses | Crawl4ai: latest minutes |
| `building_permits` | New construction, renovations | Crawl4ai: recent permits |

**Business Community Sources:**
| Profile Source | What to Extract | Crawl Strategy |
|---------------|----------------|----------------|
| `chamber_of_commerce` | New members = new businesses, events, promotions | Crawl4ai: member directory, events page |
| `economic_development_corp` | Business incentives, grants, programs | Crawl4ai: news/announcements |
| `downtown_development` | Revitalization projects, new tenants | Crawl4ai: news section |

**News & Community Sources:**
| Profile Source | What to Extract | Crawl Strategy |
|---------------|----------------|----------------|
| `local_newspaper` | Business openings/closings, local economic news | Crawl4ai: latest articles |
| `patch_com` | Hyperlocal business news, events | Crawl4ai: business section |
| `facebook_community_groups` | What locals are buzzing about | Google Search: "site:facebook.com [city] [business type]" |
| `state_subreddit` / `local_subreddit` | Community sentiment | Google Search: "site:reddit.com/r/[subreddit] [city]" |

**Events & Demand Sources:**
| Profile Source | What to Extract | Crawl Strategy |
|---------------|----------------|----------------|
| `community_calendar` | Upcoming events that drive foot traffic | Crawl4ai: calendar page |
| `recreation_events` | Parks & rec events, sports leagues | Crawl4ai: events page |
| `school_district` | School calendar (back-to-school, holidays, games) | Crawl4ai: calendar |
| `library_system` | Community events, programs | Crawl4ai: events page |

**Competitive Monitoring:**
| Signal | Source | How |
|--------|--------|-----|
| Competitor Google ratings | Google Places API | Fetch ratings for OSM nearby businesses weekly, detect changes |
| New openings near me | Municipal permits + Google Search | "new [business type] [city] [zip]" |
| Competitor closings | Google Places API status | Check if known competitors are still "OPERATIONAL" |
| Competitor promotions | Google Search grounding | "[competitor name] promotion deal special" |

---

## Source-Aware Crawling Architecture

### How it works

```
Zipcode Profile (Firestore)
    ├── sources.municipal_website: {url: "https://nutleynj.org", active: true}
    ├── sources.chamber_of_commerce: {url: "https://nutleychamber.com", active: true}
    ├── sources.patch_com: {url: "https://patch.com/new-jersey/belleville-nutley", active: true}
    ├── sources.school_district: {url: "https://nutleyschools.org", active: true}
    └── sources.community_calendar: {url: "https://nutleynj.org/calendar", active: true}
            │
            ▼
    SourceCrawler Agent (NEW — runs during weekly pulse)
        │
        ├── For each confirmed source with active=true:
        │     1. Crawl the URL via crawl4ai
        │     2. Extract relevant intelligence (LLM agent evaluates)
        │     3. Classify: opening/closing, event, regulation, competitor activity
        │
        ├── Parallel ADK fan-out:
        │     MunicipalCrawler (permits, licenses, board decisions)
        │     CommunityCrawler (chamber, events, calendar)
        │     NewsCrawler (patch, newspaper, social)
        │     CompetitorMonitor (Google Places ratings for OSM businesses)
        │
        └── Output: structured signals stored in session state
                │
                ▼
        Existing pipeline continues:
        PreSynthesis → DualModelSynthesis → CritiqueLoop
```

### ADK Agent Tree for Source-Aware Crawling

```
SourceIntelligenceGatherer (ParallelAgent)
    ├── MunicipalIntelAgent (LlmAgent + crawl4ai)
    │     instruction: "Crawl {municipal_website_url}. Find: new business permits,
    │                   certificates of occupancy, zoning decisions from the past 7 days.
    │                   Return JSON: [{type, business_name, address, date, details}]"
    │
    ├── CommunityIntelAgent (LlmAgent + crawl4ai)
    │     instruction: "Crawl {chamber_url} and {community_calendar_url}.
    │                   Find: new member businesses, upcoming events, promotions.
    │                   Return JSON: {newBusinesses: [...], events: [...], promotions: [...]}"
    │
    ├── LocalNewsAgent (LlmAgent + google_search)
    │     instruction: "Search for business news in {city}, {state} from the past 7 days.
    │                   Focus on: openings, closings, expansions, controversies.
    │                   Use: 'site:{patch_url} business' and '{city} new restaurant opening'
    │                   Return JSON: [{headline, source, url, relevance}]"
    │
    └── CompetitorPulseAgent (BaseAgent — deterministic)
          For each OSM competitor:
            Fetch Google Places details (rating, review count, status)
            Compare to last week's stored values
            Flag: new reviews, rating changes, status changes
            Return JSON: [{name, ratingChange, newReviews, status}]
```

### Data Flow: Source → Signal → Playbook → Insight

```
Source: nutleynj.org/permits
    → Crawl4ai extracts: "New certificate of occupancy: Jade Garden, 123 Franklin Ave, Chinese Restaurant"
        → Signal: {type: "new_competitor", name: "Jade Garden", address: "123 Franklin Ave", category: "Chinese Restaurant"}
            → Playbook trigger: "new_competitor_within_500m" = true
                → Play: "Jade Garden (Chinese restaurant) just opened at 123 Franklin Ave —
                         500m from you. Differentiate: highlight your BYOB policy and
                         Mediterranean focus. Post a 'welcome to the neighborhood' story
                         on Instagram this week."

Source: patch.com/new-jersey/nutley
    → Crawl4ai extracts: "Nutley Chamber hosts Spring Business Mixer, March 25"
        → Signal: {type: "networking_event", name: "Spring Business Mixer", date: "March 25"}
            → Playbook trigger: "chamber_event_this_week" = true
                → Play: "Nutley Chamber Spring Mixer is March 25. Bring 50 business cards
                         and a $10 coupon for first-time customers. Network with
                         complementary businesses (florists, event planners)."

Source: Google Places API (weekly competitor check)
    → Delta detected: "Luna Wood Fire Tavern: rating dropped from 4.4 to 4.1 (12 new reviews)"
        → Signal: {type: "competitor_rating_drop", name: "Luna Wood Fire Tavern", oldRating: 4.4, newRating: 4.1}
            → Playbook trigger: "competitor_weakening" = true
                → Play: "Luna Wood Fire Tavern dropped from 4.4 to 4.1 stars this week.
                         Their customers are looking for alternatives. Run a weekend
                         special targeting their usual crowd — Italian comfort food at
                         your BYOB advantage."
```

---

## Playbook Categories (Expanded)

### Per-Industry Playbooks

**Restaurant (15+ playbooks):**
| Category | Playbook | Trigger Type |
|----------|---------|-------------|
| Cost | dairy_margin_swap | numeric (BLS MoM%) |
| Cost | seafood_opportunity | numeric (BLS MoM%) |
| Cost | produce_spike | numeric (BLS MoM%) |
| Competitive | new_competitor_response | semantic (source crawl) |
| Competitive | competitor_weakening | numeric (rating delta) |
| Demand | event_staffing_surge | cross-signal (events + weather) |
| Demand | rain_delivery_push | numeric (weather modifier) |
| Demand | holiday_pre_booking | temporal (calendar) |
| Tech | new_pos_feature | semantic (search grounding) |
| Tech | ai_tool_opportunity | semantic (search grounding) |
| Regulatory | health_inspection_prep | semantic (source crawl) |
| Regulatory | minimum_wage_change | semantic (search grounding) |
| Community | chamber_event_networking | semantic (source crawl) |
| Community | local_festival_prep | semantic (source crawl) |
| Safety | fda_recall_alert | numeric (FDA count) |

**Barber (12+ playbooks):**
| Category | Playbook | Trigger Type |
|----------|---------|-------------|
| Cost | service_price_cover | numeric (BLS MoM%) |
| Cost | rent_squeeze | numeric (BLS MoM%) |
| Competitive | new_shop_response | semantic (source crawl) |
| Competitive | competitor_weakening | numeric (rating delta) |
| Demand | prom_wedding_prep | temporal (calendar + events) |
| Demand | back_to_school_push | temporal (calendar) |
| Demand | walk_in_weather_boost | numeric (weather) |
| Tech | booking_platform_update | semantic (search grounding) |
| Tech | ai_scheduling_tool | semantic (search grounding) |
| Regulatory | licensing_renewal | semantic (search grounding) |
| Community | event_upsell_package | semantic (source crawl) |
| Community | new_development_opportunity | semantic (source crawl) |

**Bakery (12+ playbooks):**
| Category | Playbook | Trigger Type |
|----------|---------|-------------|
| Cost | flour_spike | numeric (BLS MoM%) |
| Cost | egg_spike | numeric (BLS MoM%) |
| Cost | butter_squeeze | numeric (BLS MoM%) |
| Cost | sugar_seasonal_lock | cross-signal (temporal + numeric) |
| Competitive | new_bakery_response | semantic (source crawl) |
| Demand | wedding_season_pricing | temporal (calendar) |
| Demand | holiday_pre_order | temporal (calendar) |
| Demand | farmers_market_opportunity | semantic (source crawl) |
| Tech | online_ordering_platform | semantic (search grounding) |
| Tech | ai_menu_optimization | semantic (search grounding) |
| Regulatory | fda_allergen_alert | numeric (FDA count) |
| Community | school_event_catering | semantic (source crawl) |

---

## Implementation Phases

### Phase 1: ✅ DONE — Fix What's Broken
- BLS series per industry
- Playbook triggers MoM%
- Restaurant scout_context, critique_persona
- Alias coverage

### Phase 2: Source-Aware Crawling (NEXT — 2-3 weeks)
Build SourceIntelligenceGatherer as a new stage in the zipcode pulse pipeline.
- Add it as Stage 1.5 (after BaseLayerFetcher, before PreSynthesis)
- Reads zipcode profile sources, crawls active ones via crawl4ai
- Extracts structured intelligence (openings, closings, events, competitor activity)
- Stores in session state for the synthesis agents to consume

### Phase 3: Competitor Monitoring (1-2 weeks)
- Weekly Google Places check for OSM competitor ratings/reviews
- Store historical competitor data in Firestore (per-zip competitor tracker)
- Detect rating drops/spikes, new reviews, status changes
- Feed deltas into playbook engine

### Phase 4: Industry Tech/AI Scout (1 week)
- Add tech scouting agent to industry pulse pipeline
- Industry-specific Google Search queries for tools, platforms, AI features
- LLM evaluates relevance and extracts opportunities
- Stores as part of industry pulse (available to zipcode pulse synthesis)

### Phase 5: Semantic Playbook Engine (2 weeks)
- Implement semantic trigger evaluation (LLM reads signal, evaluates trigger prompt)
- Cross-signal correlation triggers
- Confidence + urgency scoring
- Expand playbook library to 12-15 per industry

### Phase 6: Historical Pattern Detection (2 weeks)
- Accumulate 8+ weeks of pulse data per zip
- Detect seasonal patterns, week-over-week trends
- Anomaly alerting: "Traffic is 25% below your 8-week average"
- Competitor trend lines: "Your area gained 3 competitors in 6 months"

---

## Key Design Principles

1. **Use what we already discovered** — the zipcode profile's 22+ confirmed sources are the crawl instruction set
2. **Google Search grounding is the universal scout** — don't build custom scrapers for every source, use the LLM's ability to search intelligently
3. **Crawl4ai for depth** — when Google Search finds something interesting, crawl4ai gets the full content
4. **Deterministic when possible, LLM when necessary** — BLS thresholds are deterministic; "did a new competitor open?" requires LLM evaluation
5. **Signal → Playbook → Insight** — every signal must either trigger a playbook or feed the synthesis. No orphan data.
6. **Weekly cadence, not real-time** — small business owners check in once a week. Batch intelligence, not streaming.
7. **No TOS violations** — no Yelp scraping, no LinkedIn scraping. Use official APIs and Google Search grounding.
