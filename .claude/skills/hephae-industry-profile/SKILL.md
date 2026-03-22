---
name: hephae-industry-profile
description: Deep research and onboarding of a new industry vertical for the Hephae Weekly Pulse. Discovers data sources, validates them via live API calls, crawls news/social sites, critiques its own findings, and registers the industry with a production-ready IndustryConfig.
argument-hint: [industry-name e.g. "bakery" | "barber shops" | "auto repair"]
---

# Industry Onboarding — Deep Research + Registration

You are an industry research analyst onboarding a new business vertical into the Hephae Weekly Pulse pipeline. Your job is to:

1. **Discover** every relevant data source through web research
2. **Validate** each source actually works by calling APIs, fetching RSS feeds, crawling sites
3. **Critique** your own findings — would a real owner in this industry find them useful?
4. **Build** a production-ready `IndustryConfig` dataclass
5. **Register** the industry in Firestore so the cron picks it up

**This is NOT a desk research exercise.** You must actively fetch URLs, call APIs, search Reddit, crawl trade sites, and verify everything works before including it.

## Input

Arguments: $ARGUMENTS

## Tools You MUST Use

| Tool | When |
|------|------|
| **WebSearch** | Discover trade publications, Reddit communities, cost data, seasonal patterns |
| **WebFetch** | Crawl specific trade publication pages, Reddit threads, regulatory sites |
| **Bash (curl)** | Validate BLS API, Google News RSS, FDA API, NWS API |
| **Bash (python)** | Parse API responses, compute MoM% from BLS data |
| **WebSearch** | Verify named businesses, events, platforms exist |

---

## PHASE 1: UNDERSTAND THE INDUSTRY (15 min)

### 1a. Classify

Assign to: **food** | **beauty** | **service** | **retail**

### 1b. Discover All Aliases

Use WebSearch to find every name variant:
```
WebSearch: "types of {industry} businesses" categories subtypes
```

Then use WebFetch on the top result to extract a comprehensive list of business subtypes. Be exhaustive — these become the `aliases` frozenset that determines which businesses match this vertical.

### 1c. Understand the Owner's World

Use WebSearch + WebFetch to answer:
- What does an owner in this industry worry about day-to-day?
- What are their top 3-5 costs?
- What's their typical profit margin?
- What makes a good week vs a bad week?

```
WebSearch: "{industry}" owner biggest challenges 2026
WebSearch: "{industry}" profit margin cost breakdown operating expenses
```

Fetch at least one detailed article (WebFetch) to get specific numbers, not just summaries.

---

## PHASE 2: DATA SOURCE DISCOVERY (Launch in parallel)

### 2a. BLS CPI Series — VALIDATE VIA API

Search for relevant series:
```
WebSearch: BLS CPI "{industry}" consumer price index series
```

Then validate EVERY candidate via the BLS API. Use ONE Bash call with all series:
```bash
curl -s -X POST "https://api.bls.gov/publicAPI/v2/timeseries/data/" \
  -H "Content-Type: application/json" \
  -d '{"seriesid":["SID1","SID2",...],"startyear":"2025","endyear":"2026"}'
```

Parse the response to extract: series ID, label, latest value, month, MoM% change. **Drop any series that returns empty data.**

Split validated series into:
- **Input cost series** — what the business BUYS
- **Consumer price series** — what the business CHARGES (pricing power)
- **Context series** — broad economic indicators

**Key series by category:**

| Category | Series to Check |
|----------|----------------|
| Food | CUUR0000SAF1 (food all), SAF111 (cereals/bakery), SAF112 (meats), SAF113 (dairy), SAF114 (fruits/veg), SEFA01 (flour), SEFH (eggs), SS5702 (butter), SEFR01 (sugar), SEFB (bakery products), SEFC01 (beef), SEFC02 (pork), SEFD (poultry), SEFE (fish), SEFG (eggs detailed) |
| Beauty | CUUR0000SEGL01 (haircuts), SEGP01 (personal care products), SASLE (services less energy) |
| Service | CUUR0000SETD (motor vehicle maintenance), SETB (motor fuel), SAM1 (medical care), SEMD01 (physicians services) |
| Retail | CUUR0000SAA (apparel), SEAE (footwear), SAH3 (household furnishings) |

### 2b. USDA Commodities (food only)

If food vertical, identify 4-6 key raw materials and verify they exist in USDA NASS.

### 2c. News Sources — ACTUALLY CRAWL THEM

**Step 1: Find trade publications**
```
WebSearch: "{industry}" trade publication magazine news
WebSearch: "{industry}" industry news newsletter weekly
```

**Step 2: For each publication, use WebFetch to crawl its homepage:**
```
WebFetch: "https://www.{publication}.com" — "What topics does this site cover? Is it business-operations focused or consumer-focused? Does it have an RSS feed? List the main sections/categories."
```

This tells us if it's actually useful (business ops vs consumer content).

**Step 3: Validate Google News RSS queries** (our actual automated feed):
```bash
curl -s 'https://news.google.com/rss/search?q=ENCODED_QUERY&hl=en-US&gl=US&ceid=US:en' | python3 -c "
import sys, xml.etree.ElementTree as ET
tree = ET.parse(sys.stdin)
items = tree.findall('.//item')
print(f'{len(items)} articles')
for item in items[:3]:
    title = item.find('title')
    pub = item.find('pubDate')
    print(f'  [{pub.text[:16] if pub is not None else \"?\"}] {title.text[:80]}')
"
```

Design 6-8 queries covering: industry news, input costs, regulatory, seasonal, trends, local business.

### 2d. Reddit & Social — ACTUALLY SEARCH THEM

**Step 1: Find communities**
```
WebSearch: reddit "{industry}" business owner pricing subreddit
WebSearch: "{industry}" owner community Facebook group forum
```

**Step 2: For promising subreddits, use WebSearch to find actual business threads:**
```
WebSearch: site:reddit.com r/{subreddit} "pricing" OR "costs" OR "profit" OR "business"
```

**Step 3: Use WebFetch on 1-2 actual Reddit threads** to see if the discussions are business-quality:
```
WebFetch: "https://www.reddit.com/r/{sub}/comments/{id}/" — "Is this thread about business operations (pricing, costs, margins)? Or is it consumer content? Summarize the key business insights discussed."
```

This prevents listing dead or consumer-only subreddits.

**Step 4: For forums/Facebook groups, use WebFetch on their about pages:**
```
WebFetch: "{forum_url}" — "What is this community about? How many members? Is it focused on business operations?"
```

### 2e. Regulatory & Government Data — VERIFY SOURCES

```
WebSearch: "{industry}" licensing requirements regulations compliance
WebSearch: "{industry}" health inspection open data API
```

For food verticals, verify FDA enforcement API:
```bash
curl -s "https://api.fda.gov/food/enforcement.json?search=reason_for_recall:%22{keyword}%22&limit=3&sort=report_date:desc"
```

For beauty/service verticals, check if state licensing boards have searchable databases:
```
WebSearch: "{state}" cosmetology barber license lookup database
```

### 2f. Technology Platforms

```
WebSearch: best "{industry}" POS software management system 2026
```

Use WebFetch on the top list article to extract the actual platform names, pricing, and key features.

### 2g. Seasonal Patterns

```
WebSearch: "{industry}" seasonal trends peak months busy dead season
```

Build a 12-month demand calendar.

---

## PHASE 3: SELF-CRITIQUE

Before designing playbooks, critique your research:

### 3a. Source Quality Check

For EACH data source you plan to include, ask:
- Can we actually fetch this programmatically? (API, RSS, web scrape)
- Is the data fresh enough? (updated at least monthly)
- Would a business owner care about this data?
- Is this SPECIFIC to this industry, or is it generic business advice?

**Drop anything that fails 2+ of these checks.**

### 3b. Owner Relevance Check

Imagine you ARE an owner in this industry. Read through your findings and ask:
- "Do I already know this?" — if yes, it's obvious and useless
- "Can I act on this Monday morning?" — if no, it's too vague
- "Does this data actually affect my bottom line?" — if no, it's noise

### 3c. Gap Analysis

What's MISSING? For each cost driver identified in Phase 1c, verify you have a BLS series or data source that tracks it. Flag gaps explicitly:

```
Gap: No automated data source for {X}. This means the pulse will be blind to {X} cost changes.
Workaround: Google News RSS query "{X} prices" provides indirect coverage.
```

---

## PHASE 4: PLAYBOOK DESIGN

Design 5-7 playbooks. For each one:

1. **Ground it in data** — the trigger must use a variable from `track_labels` that comes from a validated BLS series
2. **Make it specific** — name a concrete action, a dollar amount, a timeline
3. **BANNED phrases:** "consider", "monitor", "leverage", "strategic", "explore", "optimize", "be aware"
4. **Test it:** Does the trigger actually fire given current data? Check: is `{variable}` > threshold RIGHT NOW based on the BLS data you just validated?

### Categories (cover at least 5):

1. **Input cost spike** — key ingredient/supply cost rises sharply
2. **Input cost drop** — opportunity to increase margins or add specials
3. **Margin squeeze** — cost up but can't easily raise prices
4. **Seasonal timing** — time-sensitive prep for peak demand
5. **Weather impact** — how weather affects THIS specific business type
6. **Regulatory/compliance** — compliance-driven action
7. **Competitive** — market structure change

---

## PHASE 5: PROMPT CONTEXT CALIBRATION

Write the 5 context strings that get injected into the LLM agents.

### Rules:
- 2-4 sentences each
- Reference SPECIFIC BLS series IDs or data sources
- Include concrete examples that sound like a real owner talking
- The critique_persona must sound like a REAL person, not a corporate profile

### Test each context string:
Read it back and ask: "If I were the LLM agent, would I produce better output with this context than without it?" If the answer is "barely" — rewrite it.

---

## PHASE 6: ASSEMBLE & FINAL VALIDATION

### 6a. Validate ALL BLS series in one API call

```bash
curl -s -X POST "https://api.bls.gov/publicAPI/v2/timeseries/data/" \
  -H "Content-Type: application/json" \
  -d '{"seriesid":["ALL","FINAL","SERIES"],"startyear":"2025","endyear":"2026"}'
```

**Every series must return data. Drop failures.**

### 6b. Validate ALL Google News queries

Run each query and confirm: >0 articles, at least one from the last 30 days.

### 6c. Generate the IndustryConfig

```python
NEW_VERTICAL = IndustryConfig(
    id="...",
    name="...",
    aliases=frozenset({...}),
    bls_series={...},
    usda_commodities=[...],
    extra_signals=[...],
    track_labels={...},
    playbooks=[...],
    economist_context="...",
    scout_context="...",
    synthesis_context="...",
    critique_persona="...",
    social_search_terms=[...],
)
```

### 6d. Register the industry

After generating the config, add it to the codebase and register in Firestore:

1. **Add to `industries.py`** — append the config to `_ALL` list
2. **Register in Firestore** via the admin API:
```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
curl -s -X POST "https://hephae-forge-api-hlifczmzgq-uc.a.run.app/api/registered-industries" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"industryKey": "INDUSTRY_ID", "displayName": "DISPLAY_NAME"}'
```

Or if running locally, use the Firestore REST API directly:
```bash
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE/registered_industries/INDUSTRY_ID" \
  -d '{
    "fields": {
      "industryKey": {"stringValue": "INDUSTRY_ID"},
      "displayName": {"stringValue": "DISPLAY_NAME"},
      "status": {"stringValue": "active"},
      "registeredAt": {"timestampValue": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"},
      "pulseCount": {"integerValue": "0"}
    }
  }'
```

3. **Trigger a test industry pulse** to validate everything works end-to-end:
```bash
curl -s -X POST "https://hephae-forge-api-hlifczmzgq-uc.a.run.app/api/registered-industries/INDUSTRY_ID/generate-now" \
  -H "Authorization: Bearer $TOKEN"
```

---

## PHASE 7: REPORT

### 7a. Research Brief → `.claude/findings/industry-profile-{id}.md`

Include ALL findings with validation status:

```markdown
# Industry Profile: {name}
Generated: {date}
Category: {category}
Registration Status: {registered/pending}

## Research Summary
{2-3 paragraph overview of the industry, key challenges, cost structure}

## BLS CPI Series (validated via API)
| Series ID | Label | Latest Value | MoM% | Role | Status |
{every series — PASS or FAIL}

## USDA Commodities
| Commodity | Relevance | Available? |

## News Feeds (validated)
| Google News Query | Articles | Recent? | Sample Headlines |
{every query with validation results}

## Communities (verified)
| Community | Platform | Members | Business-Focused? | Verified Via | Usable? |
{every community — note which were actually crawled}

## Cost Structure (sourced)
| Cost Driver | % of Revenue | Data Source | BLS Series |

## Seasonal Calendar
| Month(s) | Demand Level | Key Events | Playbook Trigger |

## Self-Critique
| Finding | Issue | Resolution |
{gaps, dropped sources, quality concerns}

## Playbooks
| Name | Trigger | Play | Current Data Match? |
{note whether each trigger would fire given current BLS values}

## Technology Platforms
| Platform | What It Does | Market Position |

## Regulatory Sources
| Source | Data Available | API? | Verified? |
```

### 7b. Code Output

Output the complete `IndustryConfig(...)` block to the conversation, plus the registration commands.

### 7c. Next Steps

List what the user needs to do:
1. Review the config
2. Deploy (or confirm the code was added to `industries.py`)
3. Register any zip codes for this industry
4. Wait for Monday cron or trigger manually

---

## Key References

| Area | File |
|------|------|
| Industry configs | `apps/api/hephae_api/workflows/orchestrators/industries.py` |
| Industry registration | `lib/db/hephae_db/firestore/registered_industries.py` |
| Industry pulse generation | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| Industry pulse cron | `apps/api/hephae_api/routers/batch/industry_pulse_cron.py` |
| Industry admin API | `apps/api/hephae_api/routers/admin/registered_industries.py` |
| BLS client | `lib/integrations/hephae_integrations/bls_client.py` |
| USDA client | `lib/integrations/hephae_integrations/usda_client.py` |
| Signal fetching | `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` |
| Playbooks | `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` |

## What NOT To Do

- Do NOT list data sources you haven't validated. Every source must have a "tested via" note.
- Do NOT include trade publication RSS feeds without testing — most are behind Cloudflare.
- Do NOT list Reddit communities without actually searching for business threads in them.
- Do NOT write playbooks with triggers that reference variables you don't have BLS data for.
- Do NOT write vague playbooks. "Consider adjusting prices" = REJECTED.
- Do NOT skip the self-critique phase. The first draft always has gaps.
- Do NOT register the industry until the user has reviewed the config.
