---
name: hephae-audit-industry
description: Audit an existing IndustryConfig for alias coverage, BLS series validity, track_labels completeness, playbook quality, context string effectiveness, media/community source coverage, and signal gaps. Compares config against live pulse output and independently verifies data sources. Produces a graded scorecard with specific recommendations.
argument-hint: [industry-key e.g. "restaurant" | "bakery" | "barber" | all]
---

# Industry Profile Audit

You are an industry configuration auditor for the Hephae Weekly Pulse pipeline. Your job is to evaluate an existing `IndustryConfig` — not create a new one — and answer: **Is this config producing the best possible pulse output, or is it leaving value on the table?**

**Core approach:** Read the config → Validate data sources live → Cross-check against actual pulse output → Score every dimension → Give specific recommendations.

**This is NOT a code review.** It is a data quality and intelligence audit. You must actively call APIs, fetch live data, and verify the config's claims.

## Input

Arguments: $ARGUMENTS

- A specific industry key (`restaurant`, `bakery`, `barber`)
- `all` — audit all registered industries and produce a comparison table
- No args — list registered industries and ask which to audit

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## PHASE 1: LOAD (Parallel)

Issue all of 1a, 1b, 1c as parallel Bash calls.

### 1a. Read the IndustryConfig from code

```bash
python3 -c "
import sys
sys.path.insert(0, 'apps/api')
sys.path.insert(0, 'lib/common')
sys.path.insert(0, 'lib/db')
sys.path.insert(0, 'lib/integrations')
from hephae_api.workflows.orchestrators.industries import _ALL, resolve
for cfg in _ALL:
    if '$INDUSTRY_KEY' in ('all', '', cfg.id):
        print('=== IndustryConfig:', cfg.id, '===')
        print('name:', cfg.name)
        print('aliases:', sorted(cfg.aliases))
        print('bls_series:', cfg.bls_series)
        print('usda_commodities:', cfg.usda_commodities)
        print('extra_signals:', cfg.extra_signals)
        print('track_labels:', cfg.track_labels)
        print('playbook_count:', len(cfg.playbooks))
        for i, p in enumerate(cfg.playbooks):
            print(f'  playbook[{i}]: name={p.get(\"name\")} trigger={p.get(\"trigger\")} play_len={len(p.get(\"play\",\"\"))}')
        print('economist_context_len:', len(cfg.economist_context))
        print('scout_context_len:', len(cfg.scout_context))
        print('synthesis_context_len:', len(cfg.synthesis_context))
        print('critique_persona_len:', len(cfg.critique_persona))
        print('social_search_terms:', cfg.social_search_terms)
"
```

If the Python import fails (e.g. not running locally), read the file directly:
```bash
cat apps/api/hephae_api/workflows/orchestrators/industries.py
```

### 1b. Fetch the latest industry pulse from Firestore

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/industry_pulses?pageSize=20" | python3 -c "
import json, sys
data = json.load(sys.stdin)
def extract_val(f):
    if 'stringValue' in f: return f['stringValue']
    if 'integerValue' in f: return int(f['integerValue'])
    if 'doubleValue' in f: return float(f['doubleValue'])
    if 'booleanValue' in f: return f['booleanValue']
    if 'nullValue' in f: return None
    if 'timestampValue' in f: return f['timestampValue']
    if 'arrayValue' in f: return [extract_val(v) for v in f['arrayValue'].get('values', [])]
    if 'mapValue' in f: return {k: extract_val(v) for k, v in f['mapValue'].get('fields', {}).items()}
    return str(f)
for doc in data.get('documents', []):
    doc_id = doc['name'].split('/')[-1]
    fields = {k: extract_val(v) for k, v in doc.get('fields', {}).items()}
    print('--- DOC:', doc_id, '---')
    print('industryKey:', fields.get('industryKey'))
    print('weekOf:', fields.get('weekOf'))
    print('signalsUsed:', fields.get('signalsUsed'))
    print('diagnostics:', fields.get('diagnostics'))
    ni = fields.get('nationalImpact', {})
    print('nationalImpact keys:', list(ni.keys()) if ni else 'EMPTY')
    print('nationalImpact values:', {k: v for k, v in (ni or {}).items() if isinstance(v, (int, float))})
    np_ = fields.get('nationalPlaybooks', [])
    print('nationalPlaybooks:', [p.get('name') for p in np_] if np_ else 'NONE')
    ts = fields.get('trendSummary', '')
    print('trendSummary_len:', len(ts))
    print('trendSummary_preview:', ts[:300] if ts else 'EMPTY')
"
```

### 1c. Fetch the registered industry doc

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/registered_industries/$INDUSTRY_KEY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
fields = data.get('fields', {})
for k, v in fields.items():
    val = list(v.values())[0] if v else '?'
    print(f'{k}: {val}')
"
```

---

## PHASE 2: ALIAS COVERAGE AUDIT

### 2a. Check alias completeness

The `aliases` frozenset is used by `resolve(business_type)` to match businesses. If a business type string doesn't match any alias, it falls back to RESTAURANT (silently).

For each industry, evaluate:

**Coverage test — try these variations:**
```python
test_cases = {
    "restaurant": [
        "Restaurant", "cafe", "Cafe", "Coffee Shop", "coffee shop",
        "Pizzeria", "Diner", "Food Truck", "Bakery Cafe",  # should match
        "Fine Dining", "Sushi", "Thai Restaurant", "Ramen",  # likely gap
        "Bar", "Gastropub", "Brewery", "Food Hall",  # borderline
    ],
    "bakery": [
        "Bakery", "Bread Shop", "Pastry Shop", "Cupcake Shop",
        "Gluten-Free Bakery", "Vegan Bakery", "Pâtisserie",  # gaps?
        "Dessert Shop", "Churro Shop", "Pretzel Shop",  # gaps
        "Cake Studio", "Baked Goods",  # gaps?
    ],
    "barber": [
        "Barber Shop", "Barber", "Men's Grooming", "Hair Salon",
        "Men's Salon", "Fade Shop", "Grooming Studio",  # gaps?
        "Unisex Salon", "Kids Haircuts", "Blowout Bar",  # borderline
        "Nail Salon", "Lash Studio",  # should NOT match barber
    ],
}
```

For each test case, check: does it match the intended industry? Does it fall through to RESTAURANT?

**Flag:** Any common business type string that would silently fall back to RESTAURANT.

### 2b. Cross-industry collision check

Check for aliases that exist in MULTIPLE industries (e.g., "bakery cafe" might match both `restaurant` and `bakery`). Since `_INDEX` is a flat dict, only the last one wins — flag collisions.

### 2c. Score

- 95%+ of common business type strings route correctly = 100
- 85-94% = 80
- 70-84% = 60
- <70% = 40

---

## PHASE 3: BLS SERIES VALIDATION

### 3a. Live API validation — call ALL series in one shot

```bash
SERIES=$(python3 -c "
import sys, json
sys.path.insert(0, 'apps/api')
sys.path.insert(0, 'lib/common')
from hephae_api.workflows.orchestrators.industries import _ALL
ids = []
for cfg in _ALL:
    if '$INDUSTRY_KEY' in ('all', '', cfg.id):
        ids.extend(cfg.bls_series.values())
print(json.dumps(list(set(ids))))
" 2>/dev/null || echo '[]')

curl -s -X POST "https://api.bls.gov/publicAPI/v2/timeseries/data/" \
  -H "Content-Type: application/json" \
  -d "{\"seriesid\":$SERIES,\"startyear\":\"2025\",\"endyear\":\"2026\"}" | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('Results', {}).get('series', [])
print(f'Total series requested: {len(results)}')
for s in results:
    sid = s.get('seriesID', '?')
    rows = s.get('data', [])
    if rows:
        latest = rows[0]
        val = latest.get('value', '?')
        period = latest.get('periodName', '?') + ' ' + latest.get('year', '?')
        # Compute MoM% if >=2 rows
        if len(rows) >= 2:
            try:
                v1, v2 = float(rows[0]['value']), float(rows[1]['value'])
                mom = round((v1 - v2) / v2 * 100, 2)
            except:
                mom = 'N/A'
        else:
            mom = 'N/A'
        print(f'  PASS  {sid}  latest={val} ({period})  MoM={mom}%')
    else:
        print(f'  FAIL  {sid}  NO DATA')
"
```

For each series, produce:
- PASS (data returned) or FAIL (empty)
- Latest value and date
- MoM% change
- Whether it's an input cost or consumer price series

### 3b. Gap analysis — what's MISSING?

For each industry, check:

**Restaurants:** Are these series present?
- Food away from home (`CUUR0000SAFH`) — the consumer series that mirrors what restaurants charge
- Oil/fats (relevant for frying) — no series?
- Labor cost proxy — `CUUR0000SEMC` (limited service meals) vs `SASLE`?

**Bakeries:** Are these series present?
- `CUUR0000SEFA01` (flour) — the most critical series
- No oil/fat series (Crisco, vegetable oil prices)? These are major bakery inputs
- Propane/energy (oven costs) — any proxy?

**Barbers:** Key limitations to flag:
- Only 1 direct service series (`SS45011`) — low signal density
- No product cost series (hair products, clippers, supplies)
- Labor cost (50% commission model) — no trackable series exists for this

### 3c. track_labels completeness

For each `bls_series` entry, check: is there a corresponding entry in `track_labels`?

```
bls_series has "Beef & veal" → track_labels needs "beef" key → produces "beef_yoy_pct"
```

Build a mapping table:
| BLS Label | Series ID | track_labels key | Variable Name | Mapped? |
|-----------|-----------|-----------------|---------------|---------|

**Flag:** Any BLS series that has no track_label → data is fetched but NOT injected into playbook triggers or pre-computed impact. Wasted signal.

**Flag:** Any track_label that has no matching BLS series → playbook references a variable that will always be `None` (broken trigger).

### 3d. Score

- All series return data, all have track_labels = 100
- 1-2 missing/failed = 80
- 3-4 issues = 60
- 5+ issues = 40

---

## PHASE 4: PLAYBOOK QUALITY AUDIT

For EACH playbook in the config, run all four tests:

### 4a. Trigger correctness

1. **Parse the trigger** — extract all variable names referenced
2. **Check each variable** is present in `track_labels` (otherwise it will always fail to evaluate)
3. **Check current data** — given the latest BLS values from Phase 3a, WOULD this trigger fire today?
   - If yes: note it as `currently active`
   - If no: note it as `dormant — would fire when X`
4. **Evaluate trigger logic** — is the threshold reasonable? (e.g., `> 3` for YoY% is appropriate; `> 50` would never fire)

### 4b. Banned phrase scan

Scan the `play` text for: `"consider"`, `"monitor"`, `"leverage"`, `"strategic"`, `"explore"`, `"optimize"`, `"be aware"`, `"stay informed"`, `"capitalize"`.

Even ONE occurrence = FAIL.

### 4c. Specificity check

For each `play`, score on 4 criteria:
- **Dollar amount** — does it name a specific price? (`$3`, `$15 add-on`, `$0.75 price increase`)
- **Timeline** — does it say when? (`this week`, `Monday morning`, `before Saturday`)
- **Channel** — does it name WHERE/HOW? (`Instagram Reels`, `DoorDash`, `your sandwich board`)
- **Measurability** — can the owner confirm they did it? (`print 100 cards`, `add to menu`, `text your client list`)

Score: 4/4 = 100, 3/4 = 75, 2/4 = 50, 1/4 = 25, 0/4 = 0

### 4d. Coverage — are all 7 categories covered?

| Category | Present? | Playbook Name |
|----------|----------|---------------|
| Input cost spike | | |
| Input cost drop | | |
| Margin squeeze | | |
| Seasonal timing | | |
| Weather impact | | |
| Regulatory/compliance | | |
| Competitive | | |

Flag missing categories. A missing "input cost drop" category means the config can't advise on positive margin opportunities.

### 4e. Score

- All playbooks pass banned phrases + specificity ≥75% + all 7 categories covered = 100
- Each violation: -10 for banned phrase, -5 for low specificity, -15 for missing category

---

## PHASE 5: CONTEXT STRING EVALUATION

For each of the 5 context strings (`economist_context`, `scout_context`, `synthesis_context`, `critique_persona`, `social_search_terms`), evaluate:

### 5a. Economist context

- Does it name specific BLS series IDs (not just generic "check inflation")?
- Does it state the industry's actual margin range?
- Does it call out the 2-3 cost categories that matter most?
- Length check: 50-200 chars = too short, 200-600 chars = good, >600 chars = too verbose

### 5b. Scout context

- Does it name the actual seasonal events that matter for this industry?
- Does it reference LOCAL factors (not just national)?
- Does it mention what competitors look like in this industry?

### 5c. Synthesis context

- Does it give a CONCRETE example of a good recommendation (the "replace cream pasta with chicken" test)?
- Does it name the specific levers available (not generic "pricing and marketing")?
- Does it include revenue/margin numbers specific to this industry?

### 5d. Critique persona

- Is it a REAL person, not a corporate description?
- Does it include a specific pain point that only someone IN this industry would know?
- Is it long enough to have personality? (<80 chars = generic, 80-300 = good, >300 = too much)

### 5e. Social search terms

- Are all terms specific to this industry?
- Are there 5-10 terms? (<5 = too few signals, >15 = noise)
- Would these terms actually surface business-relevant content (not consumer reviews)?

### 5f. Score per string

100 = specific, grounded, actionable
80 = mostly good, one gap
60 = generic but functional
40 = too vague to add value
20 = placeholder / missing

---

## PHASE 6: MEDIA & COMMUNITY SOURCE AUDIT

**Delegate this entire phase to a `general-purpose` Agent.** The research is deep enough to warrant a subagent with full web access rather than inline sequential searches.

Use the Agent tool with this prompt (fill in `{INDUSTRY_NAME}`, `{INDUSTRY_CATEGORY}`, and `{EXISTING_SOCIAL_TERMS}` from Phase 1 data):

```
You are a media and intelligence source researcher for the {INDUSTRY_NAME} industry.

Your job: discover, crawl, and validate every information channel that a weekly business intelligence pulse for this industry should be monitoring. This means trade publications, news RSS feeds, Reddit communities, forums, newsletters, associations, podcasts, regulatory bulletins, and annual report sources.

INDUSTRY: {INDUSTRY_NAME}
CATEGORY: {INDUSTRY_CATEGORY}  (food | beauty | service | retail)
EXISTING social_search_terms in config: {EXISTING_SOCIAL_TERMS}

---

STEP 1 — DISCOVER (WebSearch — run ALL in parallel)

Run every search below simultaneously:

1. "{INDUSTRY_NAME}" trade publication magazine industry news 2026
2. "{INDUSTRY_NAME}" owner newsletter weekly digest business
3. "{INDUSTRY_NAME}" reddit community business owner pricing subreddit site:reddit.com
4. "{INDUSTRY_NAME}" forum operators association membership
5. "{INDUSTRY_NAME}" industry trends annual report 2026 supply chain
6. "{INDUSTRY_NAME}" podcast owner interview behind the scenes
7. site:reddit.com "{INDUSTRY_NAME}" owner costs margins pricing 2025 OR 2026
8. "{INDUSTRY_NAME}" trade association news bulletin regulatory update
9. "{INDUSTRY_NAME}" industry blog independent operator perspective
10. For FOOD verticals: "food service" OR "restaurant" OR "bakery" supply chain cost report 2026
11. For BEAUTY/SERVICE: "salon" OR "barber" industry association licensing news 2026

---

STEP 2 — VALIDATE EVERY PROMISING SOURCE (WebFetch — do not skip this step)

For EACH source found in Step 1 that looks relevant, use WebFetch to actually crawl it. Do not include sources you have not fetched.

For trade publications and news sites:
  Fetch the homepage or RSS page. Answer: Is this site active (content < 30 days old)? Is it focused on business operations (costs, pricing, supply chain, regulations) or consumer content? Does it have an RSS feed URL? What are the 3 most recent article headlines?

For Reddit communities (r/subredditname):
  First WebSearch: site:reddit.com/r/{subreddit} "pricing" OR "costs" OR "supplier" OR "margins" 2025
  Then WebFetch one actual thread. Answer: Is this thread about business operations? What are the top 2-3 business insights? Mark USEFUL only if ≥2 operational threads found.

For newsletters and associations:
  Fetch their about/subscribe page. Answer: How often does it publish? Free or paid? US-focused? Does it cover costs, supply chain, regulations, or market trends?

For regulatory bodies:
  Fetch their news/bulletin page. Answer: Do they publish RSS or a bulletin? How often? What types of notices?

---

STEP 3 — TEST GOOGLE NEWS RSS QUERIES

Design and test at least 6 Google News RSS queries for this industry, covering these categories:
  1. Input cost / supply chain news
  2. Regulatory / compliance / health inspection / licensing
  3. Consumer trends / demand shifts
  4. Competitive landscape / new entrants / closures
  5. Seasonal / event-driven demand
  6. Technology / platform news (POS, delivery apps, booking tools)

For each query, run:
  curl -s "https://news.google.com/rss/search?q={URL_ENCODED_QUERY}&hl=en-US&gl=US&ceid=US:en"

Report: article count, whether recent articles (< 30 days) exist, and 2 sample headlines.

---

STEP 4 — EVALUATE EXISTING social_search_terms

For each term in {EXISTING_SOCIAL_TERMS}, assess:
- Would this term predominantly surface business-operations content (Reddit/forum discussions about costs, margins, suppliers)?
- OR would it surface consumer reviews (Yelp, TripAdvisor, Google Reviews)?

Terms that surface consumer content are useless for business intelligence.

For every weak term, suggest a replacement. Example: "bakery" → "bakery owner flour costs" or "bakery supply chain 2026".

---

STEP 5 — REGULATORY & COMPLIANCE SOURCES (NJ-focused, since Hephae operates in NJ)

For food verticals: Check FDA food safety RSS, NJ Department of Health food inspection data, NJ minimum wage schedule (small business impact), NJ health code updates.
For beauty/service: Check NJ Division of Consumer Affairs cosmetology/barber board, NJ licensing renewal bulletins, NJ minimum wage impact on commission-based workers.

Test the FDA RSS:
  curl -s "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/food/rss.xml"
  Report: article count and 2 sample headlines.

---

DELIVERABLE — produce a structured source inventory:

## Validated Sources for {INDUSTRY_NAME}

### Trade Publications & News
| Source | URL | RSS? | Active? | Ops-Focused? | Verdict |
| ... | ... | ... | ... | ... | ADD/SKIP/PAID/DEAD |

### Reddit & Forum Communities
| Community | URL | Members (approx) | Ops-Focused? | Evidence | Verdict |
| ... | ... | ... | ... | ... | ADD/SKIP |

### Newsletters & Associations
| Name | URL | Frequency | Free? | Coverage | Verdict |
| ... | ... | ... | ... | ... | ADD/SKIP/PAID |

### Google News RSS Queries (validated)
| Query | Articles Found | Recent (<30d)? | Sample Headlines | Coverage Category |
| ... | ... | ... | ... | ... |

### Regulatory Sources
| Source | Type | Frequency | URL / RSS | NJ-Relevant? | Verdict |
| ... | ... | ... | ... | ... | ADD/SKIP |

### social_search_terms Assessment
| Current Term | Problem | Suggested Replacement |
| ... | ... | ... |

### Intelligence Gaps
For each major topic area that has NO validated source, list it explicitly:
  GAP: {topic} — no automated source tracks this. Workaround: {suggestion}.

Verdict options: ADD (verified, ops-focused), SKIP (consumer content), PAID (subscription required), DEAD (no recent content), UNVERIFIABLE (Cloudflare-blocked or no public access).

Do NOT include sources you have not fetched. Do NOT include sources based solely on name recognition.
```

**After the agent returns**, extract:
- Count of `ADD` sources by type
- List of validated Google News RSS queries with article counts
- Gaps identified
- social_search_terms improvements

---

### 6f. Score (computed after agent returns)

| Criteria | Score |
|----------|-------|
| ≥4 `ADD` sources found and validated across ≥2 types | 25 pts |
| ≥2 active Reddit/forum communities verified with ops threads | 20 pts |
| ≥1 regulatory/compliance source identified and tested | 15 pts |
| ≥3 Google News RSS queries validated with recent articles | 20 pts |
| social_search_terms assessed, weak terms flagged with replacements | 20 pts |

Max 100. Each missing category: -20 pts.

---

## PHASE 7: LIVE PULSE CROSS-CHECK  <!-- was PHASE 6 -->

Compare what the config SAYS it should produce against what the latest pulse ACTUALLY produced.

### 6a. Signal yield

From Phase 1b, the `signalsUsed` field shows what signals were non-empty.

Expected signals for each industry:
- **Food verticals** (restaurant, bakery): `blsCpi`, `usdaPrices`, `fdaRecalls`, `priceDeltas` — all 4 should be present
- **Beauty/service** (barber): `blsCpi`, `priceDeltas` — 2 expected; `usdaPrices`/`fdaRecalls` should NOT be present (wasted fetches if they are)

Flag: signals in `extra_signals` that did NOT appear in `signalsUsed` (config says fetch them, runtime skipped them).

### 6b. nationalImpact variable audit

Compare:
- Variables the config's `track_labels` promises → `{label}_yoy_pct`, `{label}_mom_pct`
- Variables actually present in `nationalImpact` from the live pulse

Build a table:
| Expected Variable | Present in nationalImpact? | Value |
|------------------|--------------------------|-------|

**Flag:** Variables in `track_labels` that produced `None` or are missing from the pulse. These mean playbook triggers referencing them will silently fail.

### 6c. Playbook activation check

From the live pulse, `nationalPlaybooks` lists which playbooks fired.

Cross-check:
- Given the actual `nationalImpact` values, which playbooks SHOULD have fired?
- Which actually DID fire?
- Are there false negatives (should fire, didn't)?
- Are there false positives (fired, but trigger condition is borderline)?

**Signal count check:**
The logs showed `2-3 signals` for all three industries on the 2026-W12 run. If the config declares 10+ BLS series, why are only 2-3 signals coming back? Investigate `fetch_national_signals` in `pulse_fetch_tools.py` — is it using `business_type` (industry key) to look up the config, or is it applying the full `IndustryConfig.bls_series`?

```bash
grep -n "fetch_national_signals\|bls_series\|IndustryConfig\|industry_key\|business_type" \
  apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py | head -40
```

This is critical — if `fetch_national_signals` doesn't use the industry config's BLS series, the whole national signal layer is broken.

### 6d. Trend summary quality

From Phase 1b, check the `trendSummary` text:
- Is it empty? (signal that LLM failed or `_generate_trend_summary` caught an exception)
- Does it reference specific numbers from `nationalImpact`?
- Does it contain banned phrases ("consider", "leverage")?
- Is it industry-specific or generic?
- Does it avoid giving advice (its job is summarizing, not advising)?

---

## PHASE 8: USDA & EXTRA SIGNALS VALIDATION

### 7a. USDA commodities (food verticals only)

For each commodity in `usda_commodities`, verify the USDA NASS API returns data:

```bash
# Check each commodity key is valid
curl -s "https://quickstats.nass.usda.gov/api/api_GET/?key=DEMO_KEY&commodity_desc=WHEAT&statisticcat_desc=PRICE+RECEIVED&unit_desc=\$+%2F+BU&year=2025&format=JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
count = len(data.get('data', []))
print(f'WHEAT: {count} records')
if count:
    d = data['data'][0]
    print(f'  latest: {d.get(\"Value\")} {d.get(\"unit_desc\")} ({d.get(\"year\")})')
"
```

Flag: Any commodity in the config that returns 0 records.

### 7b. FDA recall relevance (food verticals)

```bash
# Spot check: do recalls exist for this industry's products?
KEYWORD="bakery"  # or "restaurant", etc.
curl -s "https://api.fda.gov/food/enforcement.json?search=reason_for_recall:%22flour%22+OR+reason_for_recall:%22wheat%22&limit=3&sort=report_date:desc" | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', [])
print(f'{len(results)} recent recalls matching bakery ingredients')
for r in results[:2]:
    print(f'  [{r.get(\"report_date\",\"?\")}] {r.get(\"product_description\",\"?\")[:80]}')
    print(f'  reason: {r.get(\"reason_for_recall\",\"?\")[:80]}')
"
```

---

## PHASE 9: GOOGLE NEWS VALIDATION  <!-- note: RSS queries are now also validated inside Phase 6 agent — this phase checks the queries already in the config if any exist, and validates the common localNews queries used by the zip pulse -->

For this industry, validate the news queries that would be used by the `localNews` signal. The news signal uses generic queries (not industry-specific), but check if industry-specific queries would yield better results.

Design 3 industry-specific Google News RSS queries and test them:

```bash
# Example for bakery
QUERY="bakery+flour+prices+OR+bakery+costs+OR+bread+prices"
curl -s "https://news.google.com/rss/search?q=${QUERY}&hl=en-US&gl=US&ceid=US:en" | python3 -c "
import sys, xml.etree.ElementTree as ET
try:
    tree = ET.parse(sys.stdin)
    items = tree.findall('.//item')
    print(f'{len(items)} articles found')
    for item in items[:3]:
        title = item.find('title')
        pub = item.find('pubDate')
        print(f'  [{pub.text[:16] if pub is not None else \"?\"}] {title.text[:80] if title is not None else \"?\"}')
except Exception as e:
    print(f'ERROR: {e}')
"
```

Do this for 3 queries per industry. If the config has no `news_queries` field (it doesn't), note this as a gap — the current design uses zip-level generic news, not industry-specific national news.

---

## PHASE 9: SCORECARD

### 9a. Compute scores

| Dimension | Weight | Score | Key Findings |
|-----------|--------|-------|-------------|
| Alias Coverage | 10% | /100 | N% of test cases route correctly |
| BLS Series Validity | 15% | /100 | N/M series return data, N track_labels gaps |
| Playbook Quality | 20% | /100 | Banned phrases, specificity, category coverage |
| Context String Quality | 10% | /100 | Specific vs generic, examples present |
| Media & Community Sources | 20% | /100 | ADD sources found, RSS queries validated, gaps |
| Pulse Signal Yield | 15% | /100 | Actual signals produced vs expected |
| Trend Summary Quality | 10% | /100 | Numbers accurate, specific, no banned phrases |

**Overall = weighted average**

### 9b. Grade

| Score | Grade |
|-------|-------|
| 90-100 | A — Production-ready, high-quality config |
| 80-89 | B+ — Good, minor gaps |
| 70-79 | B — Solid but notable gaps |
| 60-69 | C — Works but leaving intelligence value unrealized |
| 40-59 | D — Significant issues affecting pulse quality |
| <40 | F — Config is not producing useful output |

---

## PHASE 10: REPORT

Write to `.claude/findings/industry-audit-{id}.md`:

```markdown
# Industry Config Audit: {industry_key}
Generated: {timestamp}
Industry: {display_name} | Category: {food/beauty/service/retail}

## Grade: {LETTER} ({score}/100)

| Dimension | Weight | Score | Summary |
|-----------|--------|-------|---------|
| Alias Coverage | 10% | {N} | {N}/{M} test cases match correctly |
| BLS Series | 15% | {N} | {N} PASS, {M} FAIL, {K} track_label gaps |
| Playbooks | 20% | {N} | {N} pass all tests, {M} banned phrase, {K} low specificity |
| Context Strings | 10% | {N} | {specific/generic summary} |
| Media & Community | 20% | {N} | {N} ADD sources, {M} RSS queries valid, {K} gaps |
| Pulse Signal Yield | 15% | {N} | {N} signals fetched vs {M} expected |
| Trend Summary | 10% | {N} | {empty/good/generic} |

## Alias Coverage
{table of test cases with MATCH/MISS/WRONG INDUSTRY}
{list of gaps with suggested aliases to add}

## BLS Series Validation
| Series ID | Label | Role | Status | Latest Value | MoM% |
{every series}

## track_labels Coverage
| BLS Label | track_label key | Variable | Status |
{complete mapping — MAPPED / MISSING / BROKEN}

## BLS Gaps
{signals the config is MISSING — series IDs and why they matter}

## Playbook Audit
### {playbook_name}
- Trigger: `{trigger}` — variables: {list} — all defined? {yes/no}
- Current status: {active/dormant} — given live BLS data
- Banned phrases: {none / LIST}
- Specificity: {N}/4 — {dollar/timeline/channel/measurability}
- Category: {input_spike/seasonal/etc}
- Verdict: {PASS/FAIL with reason}

## Context String Audit
### economist_context — {score}/100
{text + assessment}

### synthesis_context — {score}/100
{text + assessment — does it have a concrete example?}

### critique_persona — {score}/100
{text + assessment — does it sound like a real person?}

## Media & Community Sources
### Validated Sources
{full source inventory table from Phase 6 agent — ADD/SKIP/PAID/DEAD per source}

### Validated Google News RSS Queries
{query + article count + sample headlines}

### social_search_terms Assessment
{current terms → problem → suggested replacement}

### Intelligence Gaps
{topics with no validated source and suggested workarounds}

## Live Pulse Cross-Check
### Signal Yield
| Expected | Present in nationalImpact? | Value | Notes |
{per expected variable}

### Playbook Activation
| Playbook | Should Fire? | Did Fire? | Correct? |
{per playbook}

### Trend Summary
{full text + banned phrase scan + number count + quality assessment}

## Critical Issues
{numbered list — issues that are actively degrading pulse quality RIGHT NOW}

## Recommended Improvements
{specific, prioritized changes to make:
- Aliases to add
- BLS series to add or drop
- track_labels to add
- Playbook triggers/plays to rewrite
- Context string improvements}
```

Also write findings to `.claude/findings/latest.md`.

Output grade + top 5 issues to the conversation immediately.

---

## Key Codebase References

| Area | File |
|------|------|
| Industry configs | `apps/api/hephae_api/workflows/orchestrators/industries.py` |
| Industry pulse generator | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| National signal fetching | `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` |
| Playbook engine | `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` |
| Industry pulse Firestore | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Registered industries | `lib/db/hephae_db/firestore/registered_industries.py` |
| BLS client | `lib/integrations/hephae_integrations/bls_client.py` |
| USDA client | `lib/integrations/hephae_integrations/usda_client.py` |

## What NOT To Do

- Do NOT modify any config, code, or Firestore data. Read-only audit.
- Do NOT re-run pulses. Only analyze what's already been produced.
- Do NOT skip the live BLS API validation — configs list series IDs that may have never been tested.
- Do NOT give generic advice ("add more BLS series"). Every recommendation must name a specific series ID or alias string.
- Do NOT give a passing grade without checking Phase 6c (pulse signal yield) — a config can look complete on paper but produce empty pulses.
- Do NOT assume track_labels entries work — verify each variable name actually appears in nationalImpact.
- Do NOT overlook `fetch_national_signals` behavior — if it ignores `IndustryConfig.bls_series`, none of the national config matters.
