---
name: hephae-pulse-check
description: Deep quality check on a weekly pulse (zip-level OR industry-level) — validates signals, pre-computed impact, insight quality, critique scores, and independently verifies claims via API calls. Works with pulse ID, zip code, industry name, or defaults to latest run.
argument-hint: [pulse-id | zip-code | industry:{name} | latest]
---

# Pulse Quality Check — End-to-End Pipeline Validator

You are a quality auditor for the Hephae Weekly Pulse pipeline. Your job is to fetch a pulse result, validate every stage of the pipeline, independently verify data claims, and produce a structured quality report.

**Two pulse types:**
- **Zip-level pulse** (`zipcode_weekly_pulse` collection) — full insights with local context
- **Industry-level pulse** (`industry_pulses` collection) — national signals + playbooks + trend summary

**Routing:** If args start with `industry:` (e.g., `industry:bakery`), validate the industry pulse. Otherwise validate a zip pulse.

**Core approach:** Fetch pulse → Validate signals → Verify pre-computed impact → Audit insights → Cross-check claims → Score quality.

**Lessons from past audits:**
- Signal archive often has 0-char raw data — always fall back to `pipelineDetails.rawSignals` and `preComputedImpact` for verification
- Weather quickStats can be stale if synthesis ran hours after signal fetch — always compare against LIVE NWS
- Local briefing is consistently the weakest dimension — dig hard into competitor watch and events
- `event_traffic_modifier` comes from `localCatalysts` (permits/construction), NOT from events in `thisWeekInTown` — don't flag the mismatch
- Critique scores may not have per-insight breakdowns (obviousness/actionability/crossSignal) stored individually — reconstruct them yourself
- Cron batch runs take 20-35 minutes across multiple zips — this is normal, don't flag as slow
- The `rawSignals` key in pipelineDetails contains nested dicts, not just strings — parse each source carefully

## Input

The user can provide:
- A pulse document ID (e.g., `07110-restaurants-2026W12-073634`)
- A zip code (e.g., `07110`) — fetches latest pulse for that zip
- A zip code + date/week (e.g., `07110 W12` or `07110 2026-03-21`)
- Nothing or `latest` — fetches the most recent pulse across all zips
- `all` — audit ALL recent pulses and produce a cross-zip comparison

Arguments: $ARGUMENTS

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## PHASE 1: FETCH — Get Pulse Data (Parallel)

Issue 1a, 1b, 1c, 1d as **parallel Bash calls**.

### 1a. Resolve Pulse Document

If given a pulse ID, fetch directly:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/zipcode_weekly_pulse/PULSE_ID"
```

If given a zip code, query for the latest:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"zipcode_weekly_pulse"}],"where":{"fieldFilter":{"field":{"fieldPath":"zipCode"},"op":"EQUAL","value":{"stringValue":"ZIP_CODE"}}},"orderBy":[{"field":{"fieldPath":"createdAt"},"direction":"DESCENDING"}],"limit":1}}'
```

If no args, list recent pulses and pick the newest.

**IMPORTANT:** Use a comprehensive Python parser to extract ALL fields. The Firestore REST API returns nested mapValue/arrayValue/stringValue structures. Write a recursive `extract_val()` helper:
```python
def extract_val(field):
    if 'stringValue' in field: return field['stringValue']
    if 'integerValue' in field: return int(field['integerValue'])
    if 'doubleValue' in field: return float(field['doubleValue'])
    if 'booleanValue' in field: return field['booleanValue']
    if 'timestampValue' in field: return field['timestampValue']
    if 'nullValue' in field: return None
    if 'arrayValue' in field:
        return [extract_val(v) for v in field['arrayValue'].get('values', [])]
    if 'mapValue' in field:
        return {k: extract_val(v) for k, v in field['mapValue'].get('fields', {}).items()}
    return str(field)[:100]
```

### 1b. Extract Pulse Output (insights + localBriefing)

From the pulse document, extract EVERYTHING. Print the FULL analysis and recommendation text for each insight (not truncated) — you need the complete text for the banned-phrase scan and number counting.

**Required extractions:**

**Top level:** `zipCode`, `businessType`, `weekOf`, `signalsUsed[]`, `testMode`

**pulse.insights[] — for EACH insight, print ALL of:**
- `rank`, `title`
- `analysis` (FULL text — needed for grounding check)
- `recommendation` (FULL text — needed for banned phrase scan)
- `impactScore`, `impactLevel`, `timeSensitivity`
- `signalSources[]`, `playbookUsed`

**pulse.localBriefing:**
- `thisWeekInTown[]` — each event: what, where, when, businessImpact, source
- `competitorWatch[]` — each: name/business, observation/note
- `communityBuzz` (full text)
- `governmentWatch` (full text)

**pulse.quickStats:** trendingSearches, weatherOutlook, upcomingEvents, priceAlerts

**diagnostics:** startedAt, completedAt, signalCount, insightCount, critiquePass, critiqueScore, playbooksMatched, preComputedKeys, pipeline

### 1c. Extract Pipeline Details (separate call — large document)

Fetch the same doc but extract only `pipelineDetails`:
- `preComputedImpact` — ALL keys and values (print every key-value pair)
- `critiqueResult` — overall_pass, local_briefing_pass, summary, per-insight verdicts with scores
- `matchedPlaybooks[]` — category + play text
- `rawSignals` — for each source: check if data is present, print first 200 chars
- `macroReport`, `localReport`, `trendNarrative`, `socialPulse`, `localCatalysts` — print char count + first 200 chars

### 1d. Fetch Signal Archive + Pulse Job

In parallel:

**Signal archive:**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/pulse_signal_archive/ZIP_CODE-WEEK_OF"
```
Check if raw data is actually present (past audits found 0-char data — this is a known bug).

**Pulse job:**
```bash
# Query pulse_jobs for matching zip + weekOf
curl -s -X POST ... (query pulse_jobs collection)
```
Extract: status, startedAt, completedAt, error, testMode, timeoutAt.

---

## PHASE 2: SIGNAL VALIDATION

### 2a. Signal Coverage Table

Compare `signalsUsed[]` against the expected 17 signals:

| # | Signal | Type | Expected | Present? | Key Data |
|---|--------|------|----------|----------|----------|
| 1 | censusDemographics | BigQuery | Always | | population, median_income, poverty_rate |
| 2 | osmDensity | BigQuery | Always | | competitor_count |
| 3 | weatherHistory | BigQuery | Always | | 5-year temp/precip baseline |
| 4 | weather | NWS API | Always | | 7-day forecast |
| 5 | localNews | RSS | Always | | article headlines |
| 6 | trends | BigQuery | Always | | Google Trends top/rising terms |
| 7 | sbaLoans | SBA API | Always | | recent loan count |
| 8 | blsCpi | BLS API | Always | | CPI series (15+ food subcategories) |
| 9 | fdaRecalls | FDA API | Always | | recall count + details |
| 10 | usdaPrices | USDA API | Always | | commodity prices |
| 11 | healthMetrics | CDC API | Always | | CDC PLACES data |
| 12 | irsIncome | IRS SOI | Always | | avg AGI, filing stats |
| 13 | qcewEmployment | BLS QCEW | Always | | establishment count, YoY change |
| 14 | priceDeltas | Computed | Always | | MoM% and YoY% per CPI category |
| 15 | zipReport | Firestore cache | If exists | | zipcode research summary |
| 16 | socialPulse | LLM (Google Search) | Always | | social sentiment text |
| 17 | localCatalysts | LLM (Google Search + Crawl4AI) | Always | | permits, construction, events |

**Scoring:**
- 15-17 signals = EXCELLENT (100)
- 12-14 = GOOD (80)
- 8-11 = FAIR (60)
- 5-7 = POOR (40)
- <5 = CRITICAL (20)

### 2b. Independent Signal Verification

ALWAYS verify at least 3 signals independently. Pick from the following based on what the pulse claims:

**1. Weather (NWS — free, no key, ALWAYS verify this):**
```bash
# Get coordinates
curl -s "https://api.zippopotam.us/us/ZIP_CODE" | python3 -c "..."
# Get forecast office
curl -s "https://api.weather.gov/points/LAT,LON" -H "User-Agent: HephaeQC"
# Get forecast
curl -s "FORECAST_URL" -H "User-Agent: HephaeQC"
```
Compare: temperature range, precipitation days, wind conditions against `quickStats.weatherOutlook` and any weather claims in insights.

**Specific checks:**
- Does the pulse's temperature range match NWS? (allow +/- 5°F since forecast shifts)
- Does the pulse correctly identify rain/snow days?
- Is the forecast for the RIGHT week (not stale from a previous run)?

**2. FDA Recalls (free, no key):**
```bash
curl -s "https://api.fda.gov/food/enforcement.json?search=state:STATE_CODE+AND+report_date:[START_DATE+TO+END_DATE]&limit=5&sort=report_date:desc"
```
Compare recall count and recency. The pulse uses a 3-month window — adjust your query accordingly.

**3. Local Events (WebSearch — ALWAYS verify):**
Search for EACH event in `thisWeekInTown`:
```
WebSearch: "{event name}" "{city}" {date/month}
```
Also search for events the pulse MISSED:
```
WebSearch: "events in {city} {state} this week"
```
Flag: verified events, unverifiable events, and missed events.

**4. Named Competitors (WebSearch):**
For each business in `competitorWatch`:
```
WebSearch: "{business name}" "{city}" {state} restaurant
```
Verify: is this a real local business? Is the observation plausible?
**If only national chains are listed, flag as WEAK.** Local competitors should include businesses from the zip code.

**5. Community Buzz (WebSearch — verify if specific claims made):**
If the pulse references Reddit, Patch, or Facebook:
```
WebSearch: site:reddit.com "{city}" restaurant 2026
WebSearch: site:patch.com "{city}" restaurant
```
Check if the referenced discussions exist.

**6. BLS CPI (if BLS_API_KEY available):**
```bash
curl -s -X POST "https://api.bls.gov/publicAPI/v2/timeseries/data/" \
  -H "Content-Type: application/json" \
  -d '{"seriesid":["CUUR0000SAF113","CUUR0000SAF112","CUUR0000SAF111","CUUR0000SEFJ"],"startyear":"2025","endyear":"2026","registrationkey":"'$BLS_API_KEY'"}'
```
Key series: SAF113=Dairy, SAF112=Fruits/Veg, SAF111=Cereals, SEFJ=Food away from home.
Recalculate MoM% from the two most recent data points and compare against `preComputedImpact.{item}_mom_pct`.

### 2c. Signal Freshness Audit

For EACH signal, determine when it was fetched and whether the data is current:

| Signal | Freshness Window | How to Check |
|--------|------------------|-------------|
| weather | Must be <24h old | Compare forecast dates in rawSignals vs current date |
| localNews | Must be <7d old | Check article dates in rawSignals |
| blsCpi | ~2 month lag (normal) | Check latest data point month (e.g., Jan 2026 data available in Mar) |
| fdaRecalls | Must be <30d old | Check report_date range |
| trends | Must be <7d old | Check week label in rawSignals |
| census/IRS/QCEW/health | Static (90d cache OK) | These change annually — staleness is expected |

Flag any signal where the data is older than its freshness window.

---

## PHASE 3: PRE-COMPUTED IMPACT VALIDATION

### 3a. Full Variable Audit

Print ALL variables from `preComputedImpact` and verify each one:

**Price deltas (from BLS CPI):**
- For each `{item}_mom_pct`, check: is this a plausible MoM% change? (typically -5% to +5%)
- If you verified BLS in Phase 2b, compare the recalculated MoM% against the pre-computed value
- Flag any value > 10% or < -10% as suspicious (unless it's eggs during a shortage)

**Demographic variables:**
- `median_income`: Should match Census data. Cross-check: is this plausible for this zip? (use WebSearch if unsure)
- `population`: Should be reasonable for a NJ suburb (5K-100K range)
- `poverty_rate`: Should be 0-30% range
- `self_employment_rate`: Should be 5-25% range
- `avg_agi`: Should roughly correlate with median_income (AGI is usually higher)

**Competitive/economic:**
- `competitor_count`: From OSM. Should be >0 for any populated area. Cross-check: does the zip have this many restaurants?
- `establishments_yoy_change_pct`: From QCEW. Typically -5% to +10%.
- `sba_recent_loans`: 0 is common for a single zip.

**Traffic modifiers:**
- `weather_traffic_modifier`: `-0.05 × rain_days`. Verify: count rain days from NWS forecast, multiply by -0.05.
- `event_traffic_modifier`: `0.10 × min(catalyst_count, 3)`. This uses `localCatalysts` count, NOT `thisWeekInTown` events.
- `net_traffic_delta`: Should equal `weather_traffic_modifier + event_traffic_modifier`.

### 3b. Playbook Audit

For each matched playbook:
1. Read the trigger condition (from the `category` and `play` text)
2. Verify the trigger against actual pre-computed values
3. Check for unsubstituted `{placeholder}` text in the play
4. Verify the playbook was actually referenced in an insight (via `playbookUsed` field)

**Also check for MISSED playbooks:** Given the pre-computed values, should other playbooks have triggered?
- If `fish_&_seafood_mom_pct < -3` AND `pork_mom_pct > 1` → should `protein_swap` trigger?
- If `fda_recent_recall_count > 5` → should `fda_recall_alert` trigger? (yes in 07110 run)
- If `weather_traffic_modifier < -0.15` → should `weather_rain_prep` trigger?

---

## PHASE 4: INSIGHT QUALITY AUDIT

For EACH insight, perform ALL THREE tests. This is the most important phase.

### 4a. Banned Phrase Scan (Automated)

Scan BOTH `analysis` and `recommendation` text for these BANNED phrases:
- "consider", "monitor", "capitalize", "leverage", "strategic", "proactive", "stay informed", "be aware", "keep an eye on", "be mindful"

Use a case-insensitive search. Even ONE occurrence = FAIL on actionability.

### 4b. Number Count (Automated)

Count specific data points in the `analysis` text using this regex pattern:
```
\d+\.?\d*%|\$[\d,]+\.?\d*|\d+\.\d+[^.]|\b\d{2,}\b(?!\s*(am|pm|st|nd|rd|th))
```
This matches: percentages, dollar amounts, decimal numbers, and multi-digit numbers (excluding times and ordinals).

- 3+ specific numbers = HIGH cross-signal (score 80+)
- 2 numbers = ADEQUATE (score 60-79)
- 0-1 numbers = LOW (score < 60, FAIL)

### 4c. Source Verification (For Each Insight)

For each `signalSources[]` entry:
1. Confirm the source is in `signalsUsed[]` at the top level
2. Find the corresponding data in `preComputedImpact` or `rawSignals`
3. Trace each specific NUMBER back to a raw data source
4. If a number appears in the insight but no corresponding source contains it → **HALLUCINATED NUMBER**

**Common hallucination patterns to watch for:**
- Citing a specific dollar amount when no pricing data was fetched
- Referencing a percentage that doesn't match any preComputed value
- Naming an event that doesn't appear in localReport or rawSignals
- Claiming weather conditions that contradict the NWS verification from Phase 2b

### 4d. Recommendation Quality

For each recommendation, assess:
- **Specificity:** Does it name a specific action? ("Add a $12.99 family meal" vs "diversify revenue")
- **Timeline:** Does it specify when? ("this Friday" vs "soon")
- **Channel:** Does it specify how? ("post to Nutley Neighbors Facebook group" vs "market it")
- **Measurability:** Can the owner tell if they did it? ("print 100 cards" vs "increase awareness")

Score: 4/4 criteria = 100, 3/4 = 80, 2/4 = 60, 1/4 = 40, 0/4 = 20

### 4e. Local Briefing Deep Dive

**Events — verify EVERY event via WebSearch:**
- Search: `"{event name}" "{city}" "{month} {year}"`
- Each event should have: what (name), where (venue + address), when (specific date), businessImpact, source
- Flag: vague dates ("ongoing"), missing venue/address, unverifiable events
- Search for MISSED events: `"events in {city} this weekend"` and note any that the pulse should have caught

**Competitors — verify and critique:**
- National chains (McDonald's, Red Robin, etc.) should NOT be the primary competitors listed
- LOCAL independent restaurants should be named
- Cross-reference against `preComputedImpact.competitor_count` — if OSM shows 10 competitors, at least 2-3 should be named
- Use WebSearch to verify named businesses exist at the claimed locations

**Community Buzz — source check:**
- If it references Reddit: can you find the specific subreddit/thread?
- If it references Patch/TAPinto: can you find the article?
- If it's generic ("community is excited") → WEAK (score 30)
- If it cites specific platforms with verifiable claims → STRONG (score 80)

**Government Watch:**
- "No actions this week" is acceptable if no catalysts were found
- If `localCatalysts` in pipelineDetails mentions something but governmentWatch says "no actions" → INCONSISTENCY

---

## PHASE 5: CROSS-PULSE COMPARISON (if `all` arg or multiple pulses for same zip)

If auditing multiple pulses:

### 5a. Week-over-Week Consistency

| Metric | This Week | Last Week | Delta |
|--------|-----------|-----------|-------|
| Signal count | | | |
| Insight count | | | |
| Critique score | | | |
| Top insight overlap | | | % of insights that repeat |

Flag: >50% insight overlap between weeks (recycling old insights).

### 5b. Cross-Zip Signal Parity

If auditing same week across multiple zips:
- Shared signals (BLS, FDA, weather) should have consistent data
- Local signals (Census, OSM, news) should differ per zip
- If two zips in the same county have identical localReport text → **COPY-PASTE BUG**

---

## PHASE 6: END-TO-END PIPELINE TRACE

### 6a. Stage Completion

| Stage | Output Key | Present? | Size | Quality Notes |
|-------|-----------|----------|------|--------------|
| 1A: Signal Fetch | rawSignals | | {N} sources | Any empty sources? |
| 1A: Pre-Compute | preComputedImpact | | {N} keys | Any suspicious values? |
| 1A: Playbooks | matchedPlaybooks | | {N} matched | Any missed triggers? |
| 1B: Social Pulse | socialPulse | | {N} chars | Generic or specific? |
| 1B: Local Catalysts | localCatalysts | | {N} chars | "No catalysts" = expected sometimes |
| 2A: Trend Narrative | trendNarrative | | {N} chars | "No history" on first run = expected |
| 2B: Macro Report | macroReport | | {N} chars | Has specific numbers? |
| 2C: Local Report | localReport | | {N} chars | Names real places/events? |
| 3: Synthesis | pulse output | | {N} insights | All 3 tests pass? |
| 4: Critique | critiqueResult | | pass/fail | Score and verdicts |

### 6b. Data Flow Integrity Trace

Pick the HIGHEST-IMPACT insight and trace it end-to-end:

```
1. Raw signal source → which API returned this data?
2. preComputedImpact → was the number computed correctly?
3. Domain expert report → did the economist/scout reference it?
4. Synthesis → does the insight accurately represent the data?
5. Recommendation → does the action logically follow?
6. Critique → did the critique validate this chain?
```

Document any point where the data mutates, is misinterpreted, or is fabricated.

### 6c. Signal Archive Integrity

Check `pulse_signal_archive/{zip}-{week}`:
- Are all 15+ sources present?
- Do any have 0-char raw data? (known bug — flag but don't penalize scoring)
- Do fetchedAt timestamps align with the pulse's startedAt?

---

## PHASE 7: QUALITY SCORECARD

### 7a. Compute Scores

| Dimension | Weight | Score | Calculation |
|-----------|--------|-------|-------------|
| Signal Coverage | 15% | /100 | See 2a scoring |
| Signal Accuracy | 20% | /100 | Avg of independent verification results (weather, FDA, events, competitors) |
| Pre-Compute Correctness | 10% | /100 | % of variables that pass arithmetic check |
| Insight Quality | 25% | /100 | Per-insight: (banned_phrase_pass × 30) + (number_count_pass × 30) + (source_verified × 40). Average across insights. |
| Insight Grounding | 15% | /100 | % of cited numbers that trace to real data. 0% hallucinated = 100. |
| Local Briefing | 15% | /100 | Events verified (40%) + competitors local/named (30%) + buzz sourced (20%) + gov consistent (10%) |

**Overall = weighted average**

### 7b. Grade

| Score | Grade | Meaning |
|-------|-------|---------|
| 90-100 | A | Production-ready, high-value intelligence |
| 80-89 | B+ | Good quality, minor improvements needed |
| 70-79 | B | Solid, a few gaps to address |
| 60-69 | C | Usable but needs significant improvement |
| 40-59 | D | Major issues, not ready for delivery |
| <40 | F | Pipeline failure, do not deliver |

---

## PHASE 8: REPORT

Write findings to `.claude/findings/pulse-check-latest.md` with this structure:

```markdown
# Pulse Quality Check: {pulse_id}
Generated: {ISO timestamp}
Zip: {zip} ({city}, {state}) | Type: {type} | Week: {weekOf}

## Grade: {LETTER} ({score}/100)

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Signal Coverage | 15% | {N} | {N}/17 signals |
| Signal Accuracy | 20% | {N} | {summary of verification} |
| Pre-Compute | 10% | {N} | {any errors} |
| Insight Quality | 25% | {N} | {passed/failed counts} |
| Insight Grounding | 15% | {N} | {hallucinated numbers?} |
| Local Briefing | 15% | {N} | {events verified, competitors quality} |

## Signal Coverage
{full table from Phase 2a}

## Independent Verification Results
### Weather (NWS)
{pulse claims vs NWS actual — table}

### FDA Recalls
{pulse claims vs FDA API — table}

### Local Events
{each event: verified / unverifiable / missed events found}

### Named Competitors
{each competitor: verified local / national chain / unverifiable}

## Pre-Computed Impact
{key variables with verification status}

## Insight-by-Insight Audit
### Insight #{rank}: {title} [{impactScore} {impactLevel}]
- **Banned phrases:** {none found / LIST FOUND}
- **Data points:** {count} numbers ({list the numbers})
- **Source verification:** {each signalSource → verified/missing in rawSignals}
- **Number tracing:** {each number → traced to preComputed value / HALLUCINATED}
- **Recommendation quality:** {specificity + timeline + channel + measurability} = {N}/4
- **Verdict:** {PASS / FAIL with reason}

## Local Briefing Audit
### Events ({N} listed, {M} verified, {K} missed)
{per-event verification results + missed events from WebSearch}

### Competitors ({N} listed)
{local vs national chain breakdown, verification results}

### Community Buzz
{sourced vs generic, verification of specific claims}

### Government Watch
{specific vs placeholder, consistency with localCatalysts}

## Pipeline Trace
{stage completion table + data flow trace for top insight}

## Issues Found
{numbered list of all issues with severity and file references}

## Recommendations
{specific code changes or prompt improvements}
```

Also output the grade and top 3 findings to the conversation immediately.

---

---

# INDUSTRY PULSE VALIDATION FLOW

When args start with `industry:` (e.g., `industry:bakery`, `industry:restaurant`), validate an industry pulse instead of a zip pulse.

## IP-1: FETCH

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"

# List recent industry pulses
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/industry_pulses?pageSize=10"

# Or fetch specific one
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/industry_pulses/INDUSTRY_KEY-WEEK_OF"
```

Extract: `industryKey`, `weekOf`, `nationalSignals` (blsCpi, usdaPrices, fdaRecalls, priceDeltas), `nationalImpact` (all pre-computed variables), `nationalPlaybooks` (matched playbooks), `trendSummary`, `signalsUsed`, `diagnostics`.

Also check the industry registration:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/registered_industries/INDUSTRY_KEY"
```

## IP-2: VALIDATE NATIONAL SIGNALS

### BLS CPI Verification

For each series in the industry's `IndustryConfig.bls_series`, verify against the BLS API:
```bash
curl -s -X POST "https://api.bls.gov/publicAPI/v2/timeseries/data/" \
  -H "Content-Type: application/json" \
  -d '{"seriesid":["ALL_SERIES"],"startyear":"2025","endyear":"2026"}'
```

Compare: does `nationalImpact.{variable}_yoy_pct` match what the BLS API returns? Recalculate MoM% and verify.

### FDA Verification (food verticals only)

```bash
curl -s "https://api.fda.gov/food/enforcement.json?search=report_date:[2026-01-01+TO+2026-12-31]&limit=3"
```

Compare recall count with `nationalImpact.fda_recent_recall_count`.

### Playbook Trigger Verification

For each matched playbook in `nationalPlaybooks`:
1. Read the trigger condition
2. Check the trigger against actual `nationalImpact` values
3. Should this playbook ACTUALLY fire given the current data?
4. Are there playbooks that SHOULD have fired but didn't?

## IP-3: VALIDATE TREND SUMMARY

The `trendSummary` is a 2-3 paragraph LLM-generated national trend analysis. Check:
- Does it reference specific numbers from `nationalImpact`?
- Are those numbers accurate (match the pre-computed values)?
- Is it industry-specific (not generic business advice)?
- Does it avoid banned phrases ("consider", "leverage", "strategic")?

## IP-4: CROSS-INDUSTRY CHECK

If multiple industry pulses exist for the same week:
- National signals that should differ (BLS series) DO differ
- FDA data should be consistent across food verticals (same state data)
- Playbooks should be different per industry

## IP-5: INDUSTRY SCORECARD

| Dimension | Weight | Score | Calculation |
|-----------|--------|-------|-------------|
| Signal Coverage | 25% | /100 | N signals fetched / N expected for this vertical |
| Signal Accuracy | 30% | /100 | BLS/FDA verification results |
| Pre-Compute Correctness | 20% | /100 | Arithmetic verification of impact variables |
| Playbook Accuracy | 15% | /100 | Triggers fire correctly, no false positives/negatives |
| Trend Summary Quality | 10% | /100 | Numbers accurate, industry-specific, not generic |

## IP-6: REPORT

Write to `.claude/findings/pulse-check-latest.md`:

```markdown
# Industry Pulse Check: {industry_key}-{weekOf}
Generated: {timestamp}
Industry: {name} | Week: {weekOf} | Signals: {N}

## Grade: {A-F} ({score}/100)

## National Signals
| Signal | Present? | Key Data Points |

## BLS Verification
| Series ID | Label | Pulse Value | BLS API Value | Match? |

## Pre-Computed Impact
| Variable | Value | Verified? |

## Playbooks
| Name | Trigger | Should Fire? | Did Fire? | Correct? |

## Trend Summary Audit
{accuracy of numbers, specificity, banned phrases}
```

---

## Key Codebase References

| Area | File |
|------|------|
| Pulse orchestrator | `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py` |
| Signal fetching | `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` |
| Playbooks & impact | `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` |
| Data gatherer (Stage 1) | `agents/hephae_agents/research/pulse_data_gatherer.py` |
| Domain experts (Stage 2) | `agents/hephae_agents/research/pulse_domain_experts.py` |
| Synthesis orchestrator (Stage 3) | `agents/hephae_agents/research/pulse_orchestrator.py` |
| Synthesis agent + instruction | `agents/hephae_agents/research/weekly_pulse_agent.py` |
| Critique agent (Stage 4) | `agents/hephae_agents/research/pulse_critique_agent.py` |
| Pulse Firestore CRUD | `lib/db/hephae_db/firestore/weekly_pulse.py` |
| Signal archive | `lib/db/hephae_db/firestore/signal_archive.py` |
| Data cache (TTL tiers) | `lib/db/hephae_db/firestore/data_cache.py` |
| Output schemas | `lib/db/hephae_db/schemas/agent_outputs.py` |
| Critique schemas | `lib/db/hephae_db/schemas/pulse_outputs.py` |
| Admin API | `apps/api/hephae_api/routers/admin/weekly_pulse.py` |
| Pulse cron handler | `apps/api/hephae_api/routers/batch/pulse_cron.py` |
| Registered zipcodes | `lib/db/hephae_db/firestore/registered_zipcodes.py` |
| Industry configs | `apps/api/hephae_api/workflows/orchestrators/industries.py` |
| Industry pulse generator | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| Industry pulse Firestore | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Industry pulse cron | `apps/api/hephae_api/routers/batch/industry_pulse_cron.py` |
| Registered industries | `lib/db/hephae_db/firestore/registered_industries.py` |

## What NOT To Do

- Do NOT modify any code or data. Read-only investigation.
- Do NOT re-run or trigger new pulses. Only analyze existing data.
- Do NOT skip signal verification — ALWAYS verify weather (NWS), at least 1 event (WebSearch), and at least 1 named competitor (WebSearch).
- Do NOT trust the critique score blindly — replay all 3 tests yourself (banned phrases, number count, source verification).
- Do NOT produce a grade without evidence — every score must have data backing it.
- Do NOT flag `event_traffic_modifier=0` as inconsistent with events in `thisWeekInTown` — they use different data sources.
- Do NOT flag 20-35 minute duration as slow for cron batch runs — this is normal for multi-zip batches.
- Do NOT assume signal archive has raw data — check first, fall back to `pipelineDetails.rawSignals`.
