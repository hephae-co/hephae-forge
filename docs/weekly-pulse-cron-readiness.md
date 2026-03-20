# Weekly Pulse — Cron Readiness Report

**Date**: 2026-03-19
**Goal**: Assess readiness to run 5 zipcodes on a Monday cron
**Verdict**: **ALMOST READY** — 3 blocking issues, 4 non-blocking improvements

---

## 1. Current State Summary

### Pipeline Architecture (Working)

```
PulseOrchestrator (SequentialAgent)
├─ Stage 1: DataGatherer (ParallelAgent)
│  ├─ BaseLayerFetcher (BaseAgent — 15 signal sources, cache-through)
│  └─ ResearchFanOut (ParallelAgent)
│     ├─ SocialPulseResearch (LlmAgent + google_search)
│     └─ LocalCatalystResearch (LlmAgent + google_search + crawl4ai)
├─ Stage 2: PreSynthesis (ParallelAgent)
│  ├─ PulseHistorySummarizer → trendNarrative
│  ├─ EconomistAgent → macroReport
│  └─ LocalScoutAgent → localReport
├─ Stage 3: DualSynthesis (ParallelAgent)
│  ├─ GeminiSynthesis (Gemini 3.1 Flash Lite + HIGH thinking)
│  ├─ ClaudeSynthesis (Claude Sonnet via LiteLlm)
│  └─ InsightMerger (BaseAgent — deterministic dedup + rank)
└─ Stage 4: CritiqueLoop (LoopAgent, max_iterations=2)
   ├─ PulseCritiqueAgent (Pass A: local quality, Pass B: insight quality)
   ├─ CritiqueRouter (escalate on pass, feedback on fail)
   └─ WeeklyPulseAgent (rewrite mode)
```

### Cron Infrastructure (Implemented)

- `pulse_cron.py`: GET `/api/cron/weekly-pulse` triggered by Cloud Scheduler Monday 6am ET
- `registered_zipcodes.py`: Full CRUD (register, pause, resume, unregister) + admin endpoints
- Idempotent: skips zips with existing pulse for the current week
- 30-second stagger between zip launches via `asyncio.create_task()`
- Job tracking in `pulse_jobs` collection with 15-minute timeout
- Status endpoint: GET `/api/cron/weekly-pulse/status` + GET `/api/registered-zipcodes/cron-status`

### What Was Fixed (from audit findings)

- ✅ DualModelSynthesis refactored to use ADK LiteLlm (no more raw httpx/genai_client)
- ✅ InsightMerger extracted as separate BaseAgent with localBriefing merge logic
- ✅ LocalBriefing schema added (LocalEvent, CompetitorNote, communityBuzz, governmentWatch)
- ✅ Synthesis prompt updated with REQUIRED localBriefing instructions
- ✅ Critique Pass A (local briefing quality) added with thresholds
- ✅ Job timeout mechanism with `timeoutAt` field
- ✅ LiteLlm dependency resolved (`google-adk[extensions]`)

---

## 2. Firestore Run Data Analysis

### Run History (9 total, 3 meaningful)

| Run | Date | Signals | Insights | Critique | localBriefing | Quality |
|-----|------|---------|----------|----------|---------------|---------|
| Doc 9 | Mar 17 | 11 (old format) | 3 | N/A | ❌ | Pre-v2 pipeline |
| Docs 6-8 | Mar 18-19 | 1 (zipReport only) | 0-3 | Mixed | ❌ | Data-starved |
| Doc 3 | Mar 19 13:21 | 15 (full) | 3 | ❌ FAIL (score=133) | ❌ | Critique caught obviousness |
| Doc 2 | Mar 19 14:20 | 15 (full) | 5 | ✅ PASS (score=145) | ❌ | Good but no local briefing |
| **Doc 1** | **Mar 19 17:05** | **15 (full)** | **6** | **✅ PASS (score=144)** | **✅** | **Best run** |

### Latest Run Deep Dive (Doc 1 — 07110, Restaurants)

**Pipeline timing**: ~3 minutes (17:02:01 → 17:05:05)

**Critique scores per insight**: actionability 85-95, cross_signal 88-92, obviousness 10-20 — all PASS

**localBriefing contents**:
- thisWeekInTown: Flashlight Egg Hunt (specific event with date)
- competitorWatch: 2 entries — Former Bacarosa vacancy analysis, Cowan's Public positioning
- communityBuzz: Franklin Ave vacancy opportunity
- governmentWatch: present

**quickStats**: 4 priceAlerts, 1 upcomingEvent, 3 trendingSearches, weather outlook

**Verdict**: The latest run is production-quality. Local briefing is populated, critique passes, insights are specific and actionable.

### Data Cache Status

14 entries across 12 sources (blsCpi, cdcPlaces, census, fda, irs, news, noaa, osm, qcew, sba, trends, usda, weather) with correct TTLs. **Cache is critical for multi-zip efficiency** — shared county/state-level data (BLS, Census, FDA, CDC) will be fetched once and reused across zips in the same geography.

### Signal Archive

2 documents (was 0 in previous audit — **fix is working**). Doc `07110-2026-03-19` has 15 sources archived. Note: multiple runs in the same week overwrite the same doc (by design — doc ID is `{zip}-{weekOf}`).

---

## 3. Blocking Issues for 5-Zip Cron

### BLOCK-1: localBriefing Generation Consistency

**Problem**: Only 1 of 3 full-signal runs produced a localBriefing. Docs 2 and 3 had 15 signals but empty localBriefing. This means the synthesis prompt update + critique Pass A may not have been applied for those earlier runs (they were pre-fix), OR the LLM is still inconsistently populating it.

**Action**: Run 3 test pulses for 07110/Restaurants and verify localBriefing is populated in ALL runs. If 2/3+ fail, the synthesis prompt needs stronger enforcement (e.g., schema validation that rejects empty localBriefing when localReport state key is non-empty).

**Effort**: 30 min testing + potential 30 min prompt fix

### BLOCK-2: Idempotency Check Uses weekOf Date, Not ISO Week

**Problem** in `pulse_cron.py:120-134`:
```python
week_of = datetime.utcnow().strftime("%Y-%m-%d")  # e.g., "2026-03-23"
...
if latest_week == week_of:  # exact date match
    skipped += 1
```

This compares the exact date string, not the ISO week. If the cron runs on Monday March 23 but a test pulse was generated on Sunday March 22, the cron will NOT skip it (different date strings), generating a duplicate pulse for the same week.

Conversely, if cron fires twice on the same Monday (retry/crash), it correctly dedupes. But if `generate_pulse` sets a different `weekOf` format (e.g., "2026-W13"), the comparison always fails.

**Action**: Standardize on ISO week format (`2026-W13`) for both `weekOf` in `generate_pulse()` and the cron idempotency check, OR change the check to use `_current_week_prefix()` which already computes ISO week.

**Effort**: 15 min

### BLOCK-3: No Multi-Zip Smoke Test Has Been Run

**Problem**: All 9 runs are for the SAME zip code (07110) and SAME business type (Restaurants). The cron will run 5 different zips — we have zero evidence the pipeline works for different geographies. Potential issues:
- BigQuery `resolve_zip_geography()` may not resolve all zips
- STATE_TO_DMA mapping only covers 17 states — zips outside these get no trends data
- Different business types have different playbook coverage
- Census/BLS/OSM data availability varies by zip

**Action**: Before enabling cron, manually test 3 diverse zips:
1. A zip in a different state (e.g., 90210 CA, 60601 IL)
2. A zip in a rural area with sparse data
3. A different business type (e.g., "Retail", "Beauty salon")

Verify each produces a passing pulse with localBriefing. Fix any geography-specific failures.

**Effort**: 1-2 hours

---

## 4. Non-Blocking Improvements (Do After Cron Is Live)

### IMPROVE-1: Concurrent Pulse Limit

**Current**: `asyncio.create_task()` with 30s stagger. For 5 zips, this means 5 tasks running with starts spread over 2.5 minutes. Each takes ~3 minutes. At peak, 3-4 concurrent pulses may run.

**Risk at 5 zips**: Low. 5 × 3 min = 15 min total wall clock with staggering. Well within Cloud Run timeout.

**Risk at 50+ zips**: High. Need a semaphore (`asyncio.Semaphore(3)`) or Cloud Tasks queue.

**Action** (post-launch): Add `MAX_CONCURRENT_PULSES = 3` config and wrap task launch with semaphore.

### IMPROVE-2: Cache Warming for Shared Data

**Opportunity**: For 5 zips in the same county (e.g., all in Essex County NJ), the BLS, Census, FDA, CDC, FHFA, QCEW, IRS data is identical. The cache-through pattern handles this automatically, but the first zip fetches all data while the rest hit cache.

**Optimization**: Before staggered launch, run a pre-warm step that fetches county/state-level data for all unique counties across registered zips. This ensures even the first zip benefits from warm cache.

**Action** (post-launch): Add `_warm_shared_cache(counties: list[str])` before the staggered pulse loop.

### IMPROVE-3: Insight Field Names in Firestore

**Observation from data query**: Individual insights use `title` + `analysis` + `recommendation` (per PulseInsight schema), NOT `headline` + `body`. The admin UI needs to render these correctly. Verify the frontend component maps to the right field names.

**Action**: Check `WeeklyPulse.tsx` renders `insight.title`, `insight.analysis`, `insight.recommendation` (not `headline`/`body`).

### IMPROVE-4: Monitoring & Alerting

For cron to be reliable, add:
1. **Cron health check**: If no COMPLETED jobs by Monday 10am ET, send alert
2. **Failure rate**: If > 50% of registered zips fail in a cron run, pause and alert
3. **Quality regression**: If critiquePass rate drops below 70% over 4 weeks, investigate

**Action** (post-launch): Add a `/api/cron/weekly-pulse/health` endpoint that checks the above conditions. Wire to Cloud Monitoring alert.

---

## 5. Zip Selection — Essex/Passaic County NJ Cluster

All 5 zips within ~5 miles of each other. All Restaurants. Same DMA (New York).

| # | Zip | Town | County | Notes |
|---|-----|------|--------|-------|
| 1 | 07110 | Nutley | Essex | Already tested — 9 runs, baseline |
| 2 | 07042 | Montclair | Essex | Strong restaurant scene, upscale dining |
| 3 | 07003 | Bloomfield | Essex | Adjacent to Nutley, diverse food options |
| 4 | 07011 | Clifton | Passaic | Cross-county (Passaic) — tests different county-level data |
| 5 | 07109 | Belleville | Essex | Borders Nutley south, Italian/Latin American dining |

**Cache efficiency**: 4 Essex County zips share BLS, Census, QCEW, IRS, CDC, FHFA data.
Clifton (Passaic) will fetch its own county-level data — good test of cross-county handling.
All 5 share New York DMA trends data.

---

## 6. Registration & Launch Checklist

### Pre-Launch (Do Now)

- [ ] Fix BLOCK-2: Standardize weekOf to ISO week format
- [ ] Run BLOCK-3: Test 07042, 07003, 07011 manually (testMode=true) — verify geography resolves, data fetches, pulse generates
- [ ] Verify BLOCK-1: Run 07110 3x, confirm localBriefing in all

### Register Zips

```bash
# Via admin API (or admin UI if available)
POST /api/registered-zipcodes
{"zipCode": "07110", "businessType": "Restaurants"}

POST /api/registered-zipcodes
{"zipCode": "07042", "businessType": "Restaurants"}

POST /api/registered-zipcodes
{"zipCode": "07003", "businessType": "Restaurants"}

POST /api/registered-zipcodes
{"zipCode": "07011", "businessType": "Restaurants"}

POST /api/registered-zipcodes
{"zipCode": "07109", "businessType": "Restaurants"}
```

Each registration auto-resolves geography via BigQuery and sets `nextScheduledAt` to next Monday.

### Cloud Scheduler Setup

```bash
gcloud scheduler jobs create http weekly-pulse-cron \
  --schedule="0 11 * * 1" \
  --uri="https://<CLOUD_RUN_URL>/api/cron/weekly-pulse" \
  --http-method=GET \
  --headers="X-Cron-Secret=Bearer ${CRON_SECRET}" \
  --time-zone="UTC" \
  --attempt-deadline="900s" \
  --location="us-central1"
```

(11:00 UTC = 6:00 AM ET on Mondays)

### Post-Launch Monitoring

1. Monday 6:05 AM: Check `/api/cron/weekly-pulse/status` — should show `triggered: 5`
2. Monday 6:20 AM: Check `/api/weekly-pulse/jobs` — should show 5 RUNNING or first few COMPLETED
3. Monday 6:30 AM: All 5 should be COMPLETED. Check any FAILED for errors
4. Review pulse quality: localBriefing populated? Insights specific? Critique passing?

---

## 7. Cost Estimate (5 Zips Weekly)

| Component | Per Pulse | 5 Zips/Week | Monthly |
|-----------|-----------|-------------|---------|
| Gemini 3.1 Flash Lite (stages 1-4) | ~50K tokens | 250K tokens | 1M tokens |
| Claude Sonnet (dual synthesis) | ~15K tokens | 75K tokens | 300K tokens |
| Google Search (social + catalyst) | 2-4 queries | 10-20 queries | 40-80 queries |
| BigQuery (geography, history) | ~100 MB scanned | 500 MB | 2 GB |
| Firestore (reads + writes) | ~50 ops | 250 ops | 1000 ops |
| **Estimated monthly cost** | | | **~$5-10** |

At this scale, cost is negligible. Gemini Flash Lite is essentially free tier. Claude Sonnet for 5 pulses/week is ~$1-2/month.

---

## 8. Files Reference

### Core Pipeline
- `agents/hephae_agents/research/pulse_orchestrator.py` — ADK tree factory + InsightMerger
- `agents/hephae_agents/research/pulse_data_gatherer.py` — Stage 1
- `agents/hephae_agents/research/pulse_domain_experts.py` — Stage 2
- `agents/hephae_agents/research/weekly_pulse_agent.py` — Stage 3 synthesis
- `agents/hephae_agents/research/pulse_critique_agent.py` — Stage 4
- `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py` — Main runner

### Cron & Registration
- `apps/api/hephae_api/routers/batch/pulse_cron.py` — Cron endpoint
- `apps/api/hephae_api/routers/admin/registered_zipcodes.py` — Registration CRUD
- `lib/db/hephae_db/firestore/registered_zipcodes.py` — Firestore persistence

### Support
- `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` — Data fetchers
- `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` — Playbook matching
- `lib/db/hephae_db/firestore/pulse_jobs.py` — Job tracking
- `lib/db/hephae_db/firestore/data_cache.py` — Cache layer
- `lib/db/hephae_db/schemas/agent_outputs.py` — All output schemas
