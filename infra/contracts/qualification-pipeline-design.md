# Qualification Pipeline Design — 3-Tier Discovery Architecture

**Author**: Hephae Engineering
**Date**: 2026-03-14
**Status**: Draft v5 — Comprehensive design with all reviewer feedback

---

## 1. Problem Statement

In our current workflow, every discovered business immediately enters the full 12-agent deep discovery pipeline (~12 Gemini API calls each, ~$0.50/business). The canary run for 07110 Nutley NJ (26 restaurants) revealed:

- **14/26 businesses** failed viability AFTER running full discovery → ~168 wasted Gemini calls
- **12/26 businesses** stuck from 429 rate-limit avalanche
- **0/26 businesses** completed with capabilities
- No market context was used to decide which businesses were worth targeting

**Root cause**: We have no qualification layer. Every business, regardless of digital maturity, market fit, or reachability, gets the same expensive treatment.

---

## 2. Proposed Architecture: 3-Tier Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  TIER 0: RESEARCH (runs in parallel with Tier 1)               │
│  Area Research + Sector Research + Zipcode Research             │
│  → Market saturation, opportunity scores, demographics,        │
│    industry benchmarks, commodity pricing                       │
│  Both Tier 0 and Tier 1 must complete before Tier 2 starts     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  TIER 1: BROAD SCAN (~10s, existing)                           │
│  OSM + ADK Google Search + Municipal Hub directories           │
│  → 20-40 business candidates with name, address, maybe website │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │                            │
     Has website URL               No website URL
              │                            │
              ▼                            ▼
┌─────────────────────────┐    ┌──────────────────────┐
│  TIER 2: QUALIFICATION  │    │  "Digital Footprint  │
│  "The Sieve"            │    │   Proxy" Check       │
│  (~5-8s per biz)        │    │  Quick Yelp/Maps     │
│                         │    │  snippet check:      │
│  Step A → Step B → LLM  │    │  >4.5★ + 500+       │
│  (cascade)              │    │  reviews? → QUALIFY  │
│                         │    │  for "Get a Website" │
│                         │    │  outreach track.     │
│                         │    │  Otherwise → PARKED  │
└───────────┬─────────────┘
            │
   ┌────────┼─────────┐
   │        │         │
QUALIFIED  PARKED  DISQUALIFIED
   │
   ▼
┌─────────────────────────────────────────────────────────────────┐
│  TIER 3: DEEP DISCOVERY (existing pipeline, expensive)         │
│  Only QUALIFIED businesses, staggered Cloud Tasks              │
│  Probe data from Tier 2 reused → agents skip redundant work    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Tier 0: Research Context (Existing, Run First)

The workflow already produces rich research context. We require this to complete BEFORE qualification so we can make market-informed decisions.

### Available Research Signals

| Research Type | Key Signals for Qualification | Already Exists? |
|--------------|-------------------------------|-----------------|
| **Area Research** | `competitiveLandscape.saturationLevel` (low/moderate/high/saturated), `existingBusinessCount`, `marketOpportunity.score`, `competitiveLandscape.gaps` | Yes |
| **Sector Research** | `technologyAdoption` (what tech is typical), `benchmarks` (margins, failure rates), `synthesis.sectorHealthScore` | Yes |
| **Zipcode Research** | `demographics.key_facts` (income, population), `business_landscape`, `consumer_market`, `economic_indicators` | Yes |
| **BLS/USDA Data** | Commodity price inflation, labor market indicators | Yes (via integrations package) |

### How Research Informs Qualification

Research context drives two key decisions:

1. **Dynamic threshold calibration** — how selective to be
2. **Vertical-specific scoring** — what signals matter most for this market

---

## 4. Tier 2: The Qualification Sieve

### 4.1 Step A: Metadata Scan — Composable Tool Architecture

A single HTTP fetch feeds multiple specialized analyzers. Each analyzer is a pure function — testable, reusable, extensible.

```
┌──────────────────┐
│  page_fetcher    │  HTTP GET → raw HTML (~1-2s, plain httpx)
│  (url) → HTML    │  No browser, no JavaScript rendering
└────────┬─────────┘
         │ raw HTML passed to all analyzers
         │
    ┌────┼─────────────┬───────────────┬──────────────────┐
    │    │             │               │                  │
    ▼    ▼             ▼               ▼                  ▼
┌──────┐┌───────────┐┌─────────────┐┌───────────────┐┌────────────┐
│domain││platform   ││pixel        ││contact_path   ││meta        │
│analyz││detector   ││detector     ││detector       ││extractor   │
│er    ││           ││             ││               ││            │
│      ││Shopify    ││FB Pixel     ││/contact links ││og:type     │
│custom││Wix        ││Google       ││mailto: links  ││description │
│vs    ││WordPress  ││Analytics    ││contact meta   ││generator   │
│social││Toast      ││GTM          ││               ││JSON-LD     │
│vs    ││MindBody   ││Hotjar       ││               ││SSL         │
│direc-││Square     ││             ││               ││            │
│tory  ││           ││             ││               ││            │
└──────┘└───────────┘└─────────────┘└───────────────┘└────────────┘
    │         │             │               │                │
    └─────────┴─────────────┴───────────────┴────────────────┘
                            │
                    ┌───────▼───────┐
                    │qualification  │  Orchestrates tools,
                    │scanner        │  aggregates signals,
                    │               │  computes score
                    └───────────────┘
```

#### Tool 0: Robots.txt Probe

**Input**: Base URL
**Output**: Crawl policy

A 0-cost HEAD/GET request to `/robots.txt` that tells us:
- Does the site block crawlers? (`Disallow: /` for common user agents)
- Is the site even responding? (Acts as a lightweight liveness check before full fetch)

If robots.txt blocks all crawlers, flag this early — it prevents "Parsing Failed" bugs in Tier 3 deep discovery. The business still gets scored on other signals, but we know to use search-based discovery instead of direct crawling.

#### Tool 1: Domain Analyzer

**Input**: URL string only (no HTTP needed)
**Output**: Domain classification

| Classification | Example | Meaning |
|---------------|---------|---------|
| `custom_domain` | `joespizza.com` | Strong web investment |
| `platform_subdomain` | `joespizza.wixsite.com` | Moderate — has presence but lower maturity |
| `social_page` | `facebook.com/joespizza` | No own website — treat as no-website |
| `directory_page` | `yelp.com/biz/joes-pizza` | Not own site — treat as no-website |
| `aggregator_page` | `doordash.com/store/joes-pizza` | Listed on aggregator only |

#### Tool 2: Platform Detector

**Input**: Raw HTML
**Output**: Detected platform(s)

Detects by looking for characteristic markers in scripts, stylesheets, and meta tags:

- **E-commerce/POS**: Shopify, Square Online, Toast, Clover
- **Website builders**: Wix, Squarespace, WordPress, Weebly, GoDaddy
- **Booking/Services**: MindBody, Vagaro, Acuity, Calendly
- **Restaurant-specific**: Toast, ChowNow, Olo, BentoBox

**Why this matters**: Platform detection reveals "digital DNA" — a Toast restaurant is tech-forward, a static HTML page from 2010 is not.

#### Tool 3: Pixel Detector

**Input**: Raw HTML
**Output**: Detected tracking/analytics

- Facebook Pixel (`fbq('init'` or `facebook.com/tr`)
- Google Analytics (`gtag` or `google-analytics.com`)
- Google Tag Manager (`googletagmanager.com`)
- Hotjar, Mixpanel, other analytics

**Why this matters**: Analytics pixels = the business is actively tracking visitors and likely running paid advertising. Strong commercial intent signal.

#### Tool 4: Contact Path Detector

**Input**: Raw HTML + base URL
**Output**: Detected contact paths

- Navigation links to `/contact`, `/about`, `/contact-us`, `/get-in-touch`
- `mailto:` links in `<head>` or early `<body>`
- `tel:` links
- Contact-related meta tags

**Why this matters**: A reachable contact path is the #1 qualification signal. If we can't reach them, deep discovery is wasted.

#### Tool 5: Meta Extractor

**Input**: Raw HTML + HTTP response headers
**Output**: Structured metadata

- Open Graph: `og:type`, `og:title`, `og:description`
- `<meta name="generator">` — reveals CMS/platform
- `<meta name="description">` — SEO awareness indicator
- JSON-LD hints in `<head>` — `@type: Restaurant`, `@type: LocalBusiness`
- HTTPS vs HTTP
- **SSL certificate status**: Expired SSL = immediate "low-hanging fruit" pitch signal. Detectable from HTTP response (certificate expiry in TLS handshake). A business with expired SSL is the easiest AI growth partner sell.

---

### 4.2 Step B: Full Probe (Conditional)

Only runs if Step A returns ambiguous results (e.g., has a custom domain but no analytics pixels, no contact path detected in head — could be a parked domain or a real site with a body-only contact form).

Uses the **existing `crawl_web_page()` tool** from the discovery pipeline. This is the same Playwright-based crawl that already extracts:

- Deterministic contact email/phone via regex
- Contact page URLs (auto-detected from all page links)
- Social anchors (Instagram, Facebook, Twitter, Yelp, TikTok)
- Delivery platform links (DoorDash, UberEats, Grubhub)
- Full JSON-LD parsing
- Body text sample (content depth)

**Step B is NOT new code** — it reuses an existing tool. The innovation is knowing WHEN to call it (only for ambiguous cases) vs calling it for every business.

---

### 4.3 Scoring Algorithm

#### Hard Requirement (Gate Before Scoring)

**Contact path is mandatory**: Even in underserved markets, a business must have at least one detectable contact path (email, contact form URL, mailto: link). A business with no way to reach them is never qualified regardless of score. Check this BEFORE computing the score — if no contact path exists, disposition is PARKED.

#### Base Scoring (from probe signals)

| Signal | Points | Source |
|--------|--------|--------|
| **Innovation Gap** (primary axis) | **up to +30** | Platform Detector + social/pixel absence |
| Has reachable contact (email/form/mailto) | **+20** | Step A or B |
| Has custom domain | **+15** | Domain Analyzer |
| Has analytics pixel (FB/GA/GTM) | **+10** | Pixel Detector |
| Has social presence (2+ links) | **+10** | Step A or B |
| Has JSON-LD structured data | **+5** | Meta Extractor |
| Not a chain/franchise | **+15** | Chain Detector (static list) |

**Innovation Gap scoring** (primary axis, replaces flat bonuses):
- Business uses a commercial platform (Toast, Shopify, Square, MindBody, Vagaro) BUT has zero or one of {analytics pixel, social presence, SEO meta description}
- This is the highest-propensity-to-buy segment: they've invested in operations but not marketing
- **+30 points** if platform detected + marketing gap identified
- **+15 points** if platform detected + partial marketing presence

#### Market-Context Adjustments (from Tier 0 research)

**Dynamic Threshold:**

```
Base threshold: 40

Saturated market (40+ competitors)     → threshold = 60
High competition (20-40 competitors)   → threshold = 50
Moderate market (10-20 competitors)    → threshold = 40
Underserved market (<10 competitors)   → threshold = 30
High market opportunity score (>70)    → threshold -= 10
```

**"Economic Delta" Bonus:**
- Wealthy zip (high disposable income from census data) + business has poor digital presence (no SEO, no social, no pixels)
- These businesses have a wealthy audience they're failing to reach → AI-driven SEO has highest ROI
- **Bonus +15 points**

**"Aggregator Escape" Bonus (Restaurants):**
- Business found on DoorDash/UberEats/Grubhub (from Tier 1 scan data)
- BUT has no own website, or dead/broken website
- Losing ~30% to aggregator commissions — highest-value target for direct ordering + SEO
- **Bonus +15 points**
- **"Menu Mismatch" upgrade**: If DoorDash menu exists AND official website has NO online ordering → this business is actively burning cash on every transaction. **Auto-qualify at +30 points** — this is the easiest pitch for AI-led direct ordering.

**Cross-Vertical Aggregator Detection**: The Aggregator Escape pattern isn't restaurants-only. Extend to detect:
- **Services**: Thumbtack, Angi, HomeAdvisor, Bark, Houzz
- **Beauty/Wellness**: Vagaro, StyleSeat, Booksy
- **Medical**: Zocdoc, Healthgrades
- If a business appears on 2+ aggregators but has no own website → same Aggregator Escape bonus applies. They're paying referral fees on every lead.

#### Vertical-Specific Scoring

| Vertical | Primary Signal | High-Value Pattern | Bonus |
|----------|---------------|-------------------|-------|
| **Dining** | Aggregator presence | On DoorDash but no own website | +15 |
| **Dining** | Margin compression | High commodity inflation area (BLS) + outdated site | +15 |
| **Retail** | Digital bridge gap | Wealthy zip + no e-commerce platform | +15 |
| **Services** | Intake friction | Has website but no booking/contact form | +10 |

#### Quadrant-Based Triage (Signal Weight Adaptation)

Rather than a single linear score, classify businesses into archetypes that map to different outreach strategies:

| Quadrant | Signals | Strategy |
|----------|---------|----------|
| **The Goldilocks** | High reputation, modern platform (Toast/Shopify), low social activity | Primary target: has the "plumbing", needs AI "brain" |
| **The Digital Laggard** | High reputation, no website/expired SSL, manual operations | Action Required: "Get a Website" track |
| **The Tech Sovereign** | Custom domain, GA4, FB Pixel, active SEO, modern booking | Secondary: requires specific "Margin Surgery" pitch |
| **The Ghost** | Low reputation, basic platform, low search volume | Parked: not worth deep discovery spend |

**Signal weight adaptation based on market context**:
- In a **saturated market**: weight "Contact Path" higher (reachability is king when there are many targets to choose from)
- In an **underserved market**: weight "Platform Type" higher (who is ready to scale matters more when choices are limited)

#### Instant Disqualification (score = 0)

- Chain/franchise name match (static list of ~50+ national chains)
- URL is a social media or directory page (not own domain)
- Site returns 404/410 (dead)

---

### 4.4 Classification: Hybrid Rules + LLM

```
┌─────────────────────────────────────────────────────────────┐
│  Rules Engine (~80% of businesses) — FREE                   │
│                                                             │
│  IF chain name match → DISQUALIFIED                         │
│  IF social/directory URL → PARKED (no own website)          │
│  IF site dead (404) → DISQUALIFIED                          │
│  IF score >= threshold → QUALIFIED                          │
│  IF score < (threshold - 20) → PARKED                       │
│                                                             │
│  ELSE → ambiguous, send to LLM                              │
└────────────────────────────┬────────────────────────────────┘
                             │ (~20% of businesses)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Lite LLM Classifier — ~$0.001 per business                │
│                                                             │
│  Model: gemini-3.1-flash-lite (cheapest tier)               │
│  Input: name, category, domain type, meta signals,          │
│         market context (saturation, opportunity)             │
│  Output: {is_hvt: bool, reason: str}                        │
│                                                             │
│  Uses an ADK LlmAgent with a focused instruction:           │
│  "You are a High-Value Target classifier. Given the         │
│   business signals and market context, determine if this    │
│   business would benefit from AI-led innovation."           │
│                                                             │
│  Decision logic:                                            │
│  - is_hvt: true if Independent + Commercially Active +     │
│    Digital Contact Path exists                              │
│  - is_hvt: false if Chain + Governmental + Residential +   │
│    Inactive                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.5 Robustness: Handling Missing Research Data

If area/sector research is incomplete (e.g., `marketOpportunity.score` is missing):
- Fall back to base threshold of 40 (standard selectivity)
- Log a warning but don't block qualification
- The scoring algorithm must handle `None` values gracefully for all research signals
- All market-context adjustments are additive — missing data means no adjustment, not a crash

### 4.6 "Digital Footprint Proxy" for No-Website Businesses

Not all no-website businesses should be blindly parked. Some of the best "Innovation Targets" (e.g., a highly-rated historic deli) may have zero website but massive Yelp/Instagram presence.

**Before parking**, run a quick check:
- If Tier 1 scan data includes Yelp/Google presence signals (name appeared in Google Search results with high ratings)
- Tiered thresholds (adapts to different market sizes):
  - 500+ reviews AND 4.5+ stars (major metros)
  - 200+ reviews AND 4.0+ stars (mid-size markets)
  - 50+ reviews AND 4.5+ stars (small towns)
- OR: business found on 2+ aggregators (DoorDash, Thumbtack, Vagaro, etc.) regardless of review count — they're already paying for digital lead gen through high-commission channels
- → Mark as **"Qualified - Get a Website"** outreach track (different from standard qualification)
- → These are high-priority leads for a "you need a website" pitch, not for deep discovery

This creates a second qualification track: businesses that are viable targets for a simpler outreach ("get a website") rather than the full capability suite.

---

## 5. ADK / Agent / Tool Design

### New ADK Tools

These are implemented as plain async Python functions (like the existing `crawl_web_page`, `validate_url`). They can be used both:
- Directly from the qualification pipeline (as function calls)
- As ADK `FunctionTool` wrappers if needed by agents in the future

| Tool | Type | ADK Integration |
|------|------|-----------------|
| `page_fetcher` | Async function | Plain httpx GET, no ADK wrapper needed |
| `domain_analyzer` | Sync function | Pure URL parsing, no ADK wrapper needed |
| `platform_detector` | Sync function | HTML pattern matching |
| `pixel_detector` | Sync function | HTML pattern matching |
| `contact_path_detector` | Sync function | HTML + URL parsing |
| `meta_extractor` | Sync function | HTML parsing |

### New ADK Agent (for LLM edge cases)

**HVTClassifierAgent** — an ADK `LlmAgent` for the ~20% of ambiguous cases:

- **Model**: `AgentModels.PRIMARY_MODEL` (gemini-3.1-flash-lite)
- **Instruction**: Focused on classifying business viability based on probe signals + market context
- **Tools**: None (pure analysis, no tool calls needed)
- **Output**: Structured JSON `{is_hvt: bool, score: int, reason: str}`
- **Fallback**: Uses existing `fallback_on_error` for 429 handling
- **Pattern**: Same as existing `QualityGateAgent` in `quality_gate.py` but with richer input signals
- **ADK Schema Note**: Keep output schema FLAT — `{is_hvt: bool, score: int, reason: str}`. Avoid nested Pydantic models in `output_schema` due to known ADK validation issues with complex nested structures.
- **Retry strategy**: On 429, retry 3x with exponential backoff (5s/15s/45s) on the SAME model. Do NOT fall back to a higher-tier model — for a binary classification task, the cheap model is sufficient. If all retries fail, return PARKED (not DISQUALIFIED) so the business gets re-evaluated in the next batch run.

### Structured Output: ProbeResult Model

All analyzer outputs flow into a single typed model (not raw dicts). This follows the codebase's Pydantic-first convention and ensures type safety between qualification and deep discovery:

- `ProbeResult` — aggregated output from all 6 analyzers (domain, platform, pixel, contact, meta, robots)
- `QualificationDecision` — final disposition: track, score, reason, signals
- `HVTClassifierOutput` — flat schema for LLM output: `{is_hvt: bool, score: int, reason: str}`

These models live in `packages/common-python/hephae_common/models.py` as the shared source of truth, consumable by both the qualification phase and deep discovery agents.

**Versioning**: `ProbeResult` must include a `schemaVersion` field. When v2 adds new signals (sentiment, review velocity), parked businesses probed under v1 can be identified and re-qualified under the new schema. This prevents "stale probe" drift where old businesses never get re-evaluated with improved qualification logic.

### Qualification Scanner (Orchestrator)

Not an ADK agent — a plain Python async function that orchestrates the tools:

1. Calls `page_fetcher` once per business
2. Runs all 5 analyzers on the HTML
3. Computes score using signals + market context
4. For clear cases: returns immediately (rules)
5. For ambiguous cases: calls `HVTClassifierAgent`
6. Returns disposition: QUALIFIED / PARKED / DISQUALIFIED

### Skill Organization

All qualification tools grouped under a `qualification` module in the capabilities package:

```
packages/capabilities/hephae_agents/qualification/
  ├── __init__.py
  ├── page_fetcher.py         — HTTP fetch
  ├── domain_analyzer.py      — URL classification
  ├── platform_detector.py    — Shopify/Wix/Toast detection
  ├── pixel_detector.py       — Analytics pixel detection
  ├── contact_path_detector.py — Contact reachability
  ├── meta_extractor.py       — Meta tags / JSON-LD
  ├── chain_detector.py       — Static chain name list
  ├── scorer.py               — Scoring algorithm + dynamic threshold
  └── hvt_classifier.py       — LLM agent for ambiguous cases
```

The qualification phase in the workflow calls `qualification_scanner()` which imports and orchestrates these tools.

---

## 6. Probe Data Reuse: Qualification → Deep Discovery

When a business passes qualification, the collected signals are persisted so deep discovery **skips redundant work**:

| Probe Signal | Reused By | Skip Logic |
|-------------|-----------|------------|
| Email found | ContactAgent | Already exists in discovery stage gating |
| Social links found | SocialMediaAgent | Already exists: `_should_skip_social()` |
| Contact page URL found | ContactAgent | Already exists: targeted crawl of contact page |
| Platform detected | Capability selection | Can skip Margin Surgeon for non-food businesses |
| JSON-LD data | EntityMatcherAgent | Can skip entity validation if JSON-LD confirms identity |

This means qualified businesses run through deep discovery FASTER because parts of the pipeline are already answered.

**"State-First" Agent Design**: Each deep discovery agent (SEO, Social, Contact, etc.) must strictly enforce a "check `session.state` first" pattern: "If `session.state['contactData']` already has an email from Tier 2 qualification, skip the tool call and just validate/format the existing data." This is already partially implemented via stage gating but must be made explicit and consistent across ALL Tier 3 agents to ensure probe data actually saves API calls. Without this enforcement, the cost savings from qualification are theoretical, not realized.

---

## 7. Workflow Phase Integration

### Current Flow

```
DISCOVERY → ANALYSIS → EVALUATION → APPROVAL → OUTREACH
```

### New Flow

```
DISCOVERY (scan + research, parallel) → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH
```

- **DISCOVERY**: Runs scan (Tier 1) + area/sector research in parallel. Both must complete.
- **QUALIFICATION**: New phase. Uses a dedicated Cloud Tasks queue (`hephae-qualification-queue`) for rate-limited fan-out. Produces QUALIFIED / PARKED / DISQUALIFIED dispositions.
- **ANALYSIS**: Unchanged, but now only processes QUALIFIED businesses. Uses Cloud Tasks with staggered scheduling.

### New Workflow Phase

`QUALIFICATION` added between `DISCOVERY` and `ANALYSIS` in the workflow phase enum.

### New Business Phases

| Phase | Meaning |
|-------|---------|
| `QUALIFIED` | Passed qualification — enters deep discovery |
| `PARKED` | Below threshold or no website — stored for future batch |
| `DISQUALIFIED` | Chain / closed / not a business — never process |

---

## 8. Cost Model

| Step | Cost per business | When runs |
|------|-------------------|-----------|
| Research (area + sector) | Shared (~$0.05 total) | Once per workflow |
| Broad scan (Tier 1) | ~$0.001 shared | Once per workflow |
| Step A: Metadata scan | $0 (HTTP only) | All with website |
| Step B: Full probe | $0 (existing tool) | ~30% ambiguous |
| LLM classifier | ~$0.001 each | ~20% ambiguous |
| **Total qualification** | **< $0.01 per business** | — |
| Deep discovery (Tier 3) | ~$0.50 each | Only qualified |

### Impact Estimate (07110 Nutley NJ, 26 restaurants)

| Metric | Before | After |
|--------|--------|-------|
| Businesses discovered | 26 | 26 |
| Enter deep discovery | 26 (100%) | ~8-10 (~35%) |
| Gemini calls (deep discovery) | 312 | ~96-120 |
| Viability failures post-discovery | 14 (54%) | ~1-2 (~15%) |
| Wasted deep discovery calls | 168 | ~12-24 |
| **Total cost** | ~$13.00 | ~$4-5 |
| **Savings** | — | **~60-70%** |

---

## 9. Future Enhancements (v2+)

### Deeper AI Readiness Signals

- **"Sentiment & Capacity" analysis**: Search snippets for customer pain points ("busy phone", "no one answered email", "hard to get a table") — direct operational friction indicators
- **"Lead Leakage" detection**: Review keywords about poor responsiveness + county labor shortage data (BLS) — businesses physically incapable of handling lead flow, perfect for AI communicator
- **"Retail Desynchronization"**: Wealthy zip + in-store only + no Google Merchant Center — invisible to modern search-to-shop behavior

### Innovation Readiness Matrix (v2)

Vertical-specific triage that goes beyond basic qualification:

| Industry | Primary Triage Filter | High-Value Signal |
|----------|----------------------|-------------------|
| Dining | Menu Freshness | High aggregator presence + old PDF menu |
| Services | Response Latency | High rating + "hard to reach" review keywords |
| Retail | Inventory Visibility | Wealthy zip + no e-commerce/catalog sync |
| Medical | Intake Friction | High volume + no digital booking/contact |

### Additional v2 Signals

- **"Menu Freshness" proxy**: Check `last-modified` header on PDF menus or "Special of the Week" strings — indicates operational activity
- **"Review Velocity"**: Frequency matters more than count. 50 reviews in 2 months with no website = "Local Legend" growth spurt
- **"Aggregator Price Delta"**: Compare DoorDash prices vs website prices to quantify commission loss — creates immediate "Value-First" pitch
- **"Search Engine Saturation" ratio**: High search mentions vs low domain authority = reputation exceeding digital presence
- **GMB "Unclaimed" detection**: Unclaimed Google Business Profile for a popular business = red alert outreach signal
- **Robots.txt "Developer Signatures"**: CMS platforms and specialized POS systems leave unique fingerprints in robots.txt that meta tags might miss

### Batch Operations

- **Batch website lookup**: Single LLM call to find websites for all parked businesses
- **Periodic re-qualification**: Cron job to re-check parked businesses as markets evolve
- **Parked business outreach**: Different, lighter outreach for parked businesses (just "get a website" recommendation)

---

## 10. Rate-Limit Mitigation: Cloud Tasks Fan-Out (GCP-Native)

Rather than custom semaphores or `asyncio.sleep` loops, use a **dedicated Cloud Tasks queue** for qualification probes. GCP handles staggering, retries, and backoff natively.

### Dedicated Qualification Queue

Create a `hephae-qualification-queue` with conservative rate limits:

- `maxDispatchesPerSecond`: 5 (safe for CDN/firewall avoidance)
- `maxConcurrentDispatches`: 3 (limits parallel HTTP probes)
- `minBackoff`: 10s, `maxBackoff`: 300s, `maxDoublings`: 4 (automatic exponential backoff on 429/503)
- `maxAttempts`: 3 (retry failed probes)

### How It Works

1. Tier 1 scan finds 40 businesses
2. Orchestrator pushes 40 individual "Qualify" messages to `hephae-qualification-queue`
3. GCP dispatches them at the configured safe rate (5/sec)
4. Cloud Run receives each task, runs the metadata scan (Step A → Step B), updates Firestore
5. If a website returns 429 or is slow → Cloud Tasks retries automatically with backoff

### Benefits Over Custom Code

- **Visibility**: Task status visible in GCP Console — in-flight, retrying, failed
- **Isolation**: One slow/aggressive website won't crash the entire qualification batch
- **Zero rate-limit logic**: No `asyncio.sleep`, no semaphores, no counters
- **Native retries**: Exponential backoff handled by infrastructure, not application code

### Barrier Pattern: Research Must Complete First

Since Tier 0 (Research) and Tier 1 (Scan) run in parallel, there's a risk qualification tasks execute with incomplete market context. Use a "Barrier Pattern":

- Qualification Cloud Tasks are created and queued immediately after Tier 1 completes
- BUT they include a `research_complete` prerequisite check — the task handler verifies that area/sector research is available in Firestore before proceeding
- If research is not yet available, the task returns a retriable status and Cloud Tasks re-dispatches after backoff
- This ensures qualification always has full market context for dynamic threshold calibration

### Task Timeout

Set Cloud Run instance timeout for qualification tasks to **60 seconds** — accounts for slow-loading websites, CDN challenges, or retries within the task. This is shorter than the 30-minute timeout used for deep discovery tasks.

### For LLM Calls (HVT Classifier)

The ~20% of businesses that need LLM classification use the existing `on_model_error_callback` (`fallback_on_error`) which already handles Gemini 429s by switching models. No additional infrastructure needed — ADK's built-in resilience handles this.

---

## 11. Enhanced Chain Detection

### Static List (v1)

A curated list of ~50+ national chains (from existing `quality_gate.py`). Covers major restaurants, retail, banks, gyms, hotels.

### Fuzzy Chain Matcher (v1 enhancement)

Beyond the static list, detect **regional/local chains** that the static list misses:

- **Cross-zipcode dedup signal**: If the same business name (normalized) appears in Tier 1 scans across MULTIPLE zip codes within the same county/area workflow, auto-flag it as a potential chain
- **Multi-location detection**: If the Tier 1 scan for a SINGLE zip code finds 2+ businesses with very similar names (e.g., "Joe's Pizza - Main St" and "Joe's Pizza - Oak Ave"), flag as potential multi-location operation
- These flagged businesses go to the LLM classifier for verification rather than auto-DQ — some multi-location businesses are still independently owned

This works with zero extra API calls — it's a pattern analysis on Tier 1 scan data that's already collected.

**Implementation note**: For county-level workflows that scan multiple zip codes, maintain a "seen names" index in the workflow state so the orchestrator can compare across zip codes within the same run. For cross-workflow detection, store normalized names in a lightweight lookup (Firestore collection or workflow state) that persists across runs.

---

## 12. Qualification Tracks (QUALIFIED vs PARKED vs ACTION_REQUIRED)

Not all qualified businesses enter the same pipeline. Three disposition tracks:

### Track 1: QUALIFIED (standard)

Businesses with website + contact reachability + positive signals. Enter full deep discovery (Tier 3).

### Track 2: QUALIFIED_ACTION_REQUIRED (high-reputation, no-website)

Businesses with **strong reputation but weak digital presence**:
- High Google/Yelp rating (>4.5 stars) AND 50+ reviews
- BUT no website
- These are the highest-value "digital gap" leads — proven demand, massive opportunity
- Enter a **"Get a Website" outreach track** — different from standard deep discovery
- Skip full capability suite, instead run targeted outreach: "You have 500 five-star reviews but no website — we can help"

### Track 3: PARKED

Businesses that don't meet any qualification criteria:
- No website, no strong online reputation
- Below dynamic threshold
- Stored for future batch processing (periodic re-qualification, batch website lookup)

### Track 4: DISQUALIFIED

Chain/franchise, permanently closed, not a real business. Never process.

---

## 13. Infrastructure: Separate Cloud Run Service

Deploy qualification as its own Cloud Run service (`hephae-qualification`) separate from deep discovery (`hephae-forge-api`):

- **Qualification tasks**: Fast (5-8s typical, 60s max timeout). High throughput, low memory.
- **Discovery tasks**: Slow (up to 30 min). Low throughput, high memory (Playwright, multi-agent pipelines).
- If they share a service, Cloud Run's autoscaler sees mixed latency and makes poor scaling decisions — holds instances open for 30 min that could be serving 5s qualification tasks.
- The `hephae-qualification-queue` targets the qualification service; the existing `hephae-agent-queue` targets the discovery service.

---

## 14. Qualification Feedback Loop

Track qualification accuracy over time to recalibrate scoring weights:

- After each deep discovery run, log: `{business_id, qualification_score, threshold_used, deep_discovery_outcome: "viable" | "failed", failure_reason}`
- Aggregate weekly: compute viability rate by score bucket (e.g., score 30-40: 45% viable, 50-60: 88% viable)
- **Target metric**: >80% viability rate for QUALIFIED businesses
- If a score bucket consistently falls below 60% viability, either raise its threshold or investigate which signals are misleading
- This creates a self-improving system: qualification gets smarter over time based on actual outcomes

---

## 15. Research Staleness Guard

For long-running multi-zipcode workflows:
- Track `research_generated_at` timestamp on research context
- If research is >30 min old at time of qualification, log a warning
- If >60 min old, fall back to base threshold (40) instead of stale market adjustments
- Prevents qualification decisions based on outdated market context in multi-hour county workflows

---

## 16. Menu Freshness Tool (Dedicated)

A lightweight tool that checks whether a restaurant's menu is actively maintained:
- Check `last-modified` HTTP header on PDF menu links
- Detect "Special of the Week", "Today's Special", date-stamped content in HTML
- A restaurant that updates its menu digitally is operationally active and tech-engaged
- **Scoring**: Fresh/active menu → +10 points. Stale/PDF-only menu → neutral. No menu online → -5 points.

This is a dedicated tool under the qualification skill, not part of the general meta_extractor, because menu freshness is a vertical-specific (dining) signal with distinct detection logic.

---

## 17. Verification Plan

1. Deploy as canary Cloud Run service for A/B testing
2. Run workflow for 07110 Restaurants
3. Verify research completes before qualification starts
4. Verify qualification threshold adapts to market saturation
5. Verify no-website businesses → PARKED
6. Verify chains → DISQUALIFIED
7. Verify only strong digital-presence businesses → QUALIFIED
8. Verify probe data reused by deep discovery (agents skipped)
9. Compare Gemini API call count vs production: target 60%+ reduction
10. Compare qualified business viability pass rate: target >80%
