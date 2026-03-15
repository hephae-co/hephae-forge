# Debug Report: WgjhRth9tmBlQIQ2tmPt
Generated: 2026-03-15T17:49:00Z
Zip: 07110 (Nutley, NJ) | Type: Restaurants | Phase: approval (complete) | Duration: ~20 min

## Workflow Summary

| Metric | Value |
|--------|-------|
| Workflow ID | WgjhRth9tmBlQIQ2tmPt |
| Zip Code / Business Type | 07110 / Restaurants |
| Phase | **approval** (analysis + evaluation complete) |
| Duration (created → approval) | ~20 min (17:29:11 → 17:48:54) |
| Total Businesses | 15 |
| Website Discovery Rate | 14 / 15 (93.3%) |
| Qualification Breakdown | 10 qualified, 5 parked |
| Dynamic Threshold Used | 30 (saturation=moderate, loaded from zip research) |
| Quality Passed | **4 / 10** (40%) |
| Quality Failed | **6 / 10** (60%) — 3 traffic hallucination, 2 low scores, 1 competitive hallucination |
| Retry Rate | 0 / 10 (0%) |

## Capability Coverage (10 qualified businesses, FINAL)

| Capability | should_run | Completed | Failed | Notes |
|------------|-----------|-----------|--------|-------|
| SEO | needs officialUrl (10) | 10 | 0 | 100% success |
| Traffic | always (10) | 10 | 0 | 100% success |
| Competitive | always (10) | 9 | 1 | sugar-tree-caf failed |
| Margin Surgeon | menuScreenshotBase64 OR menuUrl | 0 | 9 | **100% failure** (1 skipped) |
| Social | always (10) | 10 | 0 | 100% success |

## Evaluation Results (FINAL)

| Business | SEO | Traffic | Competitive | Quality |
|----------|-----|---------|-------------|---------|
| Luna Wood Fire Tavern | 85 | 90 | 90 | **PASSED** |
| Sugar Tree Café | 90 | 90 | (failed) | **PASSED** |
| Nutley Diner | 90 | 95 | 90 | **PASSED** |
| Rocky's Pizzeria | 85 | 95 | 90 | **PASSED** |
| Queen Margherita | 90 | **40 (h!)** | 90 | FAILED — traffic hallucinated |
| Cucina 355 | 90 | **65 (h!)** | 92 | FAILED — traffic hallucinated |
| Pita Bowl | 95 | **65 (h!)** | 92 | FAILED — traffic hallucinated |
| The Oakley Kitchen | 90 | 95 | **75** | FAILED — competitive below 80 |
| Ralph's Pizzeria | **65** | 95 | 95 | FAILED — SEO below 80 |
| Cowan's Public | 90 | 95 | **45 (h!)** | FAILED — competitive hallucinated |

*(h!) = isHallucinated=True*

## Improvements From Prior Workflow (8x5Idxzp)

| Metric | Prior (8x5Idxzp) | Current (WgjhRth9) | Change |
|--------|-------------------|---------------------|--------|
| Website Discovery Rate | 7/19 (36.8%) | 14/15 (93.3%) | +56.5pp |
| Research Context | None | Loaded (threshold=30) | Fixed |
| Businesses Qualified | 7/19 (36.8%) | 10/15 (66.7%) | +29.9pp |
| Traffic Hallucination | (not evaluated) | 3/10 (30%) | Partial fix |
| Quality Passed | 0 (blocked) | 4/10 (40%) | New |
| Margin Surgeon | 100% skip | 100% fail | **Regressed** |

---

## PATTERN-1: Margin Surgeon 100% Failure [CRITICAL]

- **Aggregate Signal:** 0 completions, 9 failures, 1 skip. Zero margin analysis produced.
- **Category:** `capability_execution`
- **Affected:** 10/10 qualified businesses (100%)
- **Spot-Check Evidence:**
  - luna-wood-fire-tavern: fail=['margin_surgeon'] — has menuUrl but no menuScreenshotBase64
  - queen-margherita: fail=['margin_surgeon'] — same
  - sugar-tree-caf: skip=['margin_surgeon'] — only business that skipped (no menuUrl yet when task ran)
- **Cascade Impact:** Zero margin analysis for any business. No menu pricing insights or margin optimization in any report.
- **Root Cause:** `registry.py:207` `should_run` was widened to `lambda biz: bool(biz.get("menuScreenshotBase64") or biz.get("menuUrl"))`. Now returns True when `menuUrl` exists, but the margin_surgeon runner still requires `menuScreenshotBase64` and crashes without it.
- **File:** `apps/api/hephae_api/workflows/capabilities/registry.py:207`
- **Fix Direction:** Either (a) update the margin_surgeon runner to accept `menuUrl` and fetch/screenshot the menu itself, or (b) revert should_run to only check `menuScreenshotBase64` until the runner supports URL-based input, or (c) add a menu screenshot step to enrichment.

## PATTERN-2: Traffic Hallucination — 30% Failure Rate [HIGH]

- **Aggregate Signal:** 3/10 traffic evaluations flagged `isHallucinated=True` with scores 40-65 (below 80). Causes 3 businesses to fail quality despite strong SEO and competitive scores.
- **Category:** `evaluation_quality`
- **Affected:** 3 businesses — Queen Margherita (s=40,h=True), Cucina 355 (s=65,h=True), Pita Bowl (s=65,h=True)
- **Spot-Check Evidence:**
  - Queen Margherita: SEO=90, competitive=90 both passed, but traffic=40 with hallucination killed the entire evaluation
  - Cucina 355: SEO=90, competitive=92, but traffic=65 hallucinated
  - 7/10 traffic evaluations passed (some with 90-95 scores), so this is not systemic but significant
- **Cascade Impact:** 3 businesses that would otherwise pass are blocked from outreach. All 3 have strong SEO and competitive scores.
- **Comparison to prior workflow:** Prior workflow (of0O9BLm) had 100% traffic hallucination due to missing research context. This workflow HAS research context (threshold=30), reducing hallucination from 100% to 30% — but not eliminating it.
- **File:** Traffic forecaster agent prompt + evaluator
- **Fix Direction:** The traffic forecaster agent still occasionally ignores weather/event research data. Investigate whether the 3 failing businesses received the research context in their traffic agent invocation. The evaluator is correctly flagging genuine hallucination.

## PATTERN-3: Full Probe NoneType Crash [HIGH]

- **Aggregate Signal:** 3/4 full probe attempts crashed with `'NoneType' object has no attribute 'get'`. All 4 businesses ended up parked.
- **Category:** `qualification_error`
- **Affected:** 4 businesses — old-canal-inn, chris-and-angie-s-dinette, salumeria-regina, bgl
- **Spot-Check Evidence:**
  - Old Canal Inn: Playwright crawled theoldcanalinn.com, extracted UI data (hasFavicon=True, primaryColor=#4f46e5, linkCount=24), then probe FAILED
  - Salumeria Regina: Playwright timed out on salumeriareginanj.com (30s), then probe FAILED
  - BGL: Playwright timed out on thebgl.com (30s)
- **Root Cause:** `scanner.py:375` `crawl_web_page(url)` returns `None` on timeout. Line 380 `crawl_data.get(...)` crashes on NoneType.
- **File:** `agents/hephae_agents/qualification/scanner.py:375-380`
- **Fix Direction:** Add `if not crawl_data: return partial_result` before line 380.

## PATTERN-4: Competitive Hallucination (Cowan's Public) [MEDIUM]

- **Aggregate Signal:** 1/10 competitive evaluations flagged `isHallucinated=True` with score 45.
- **Category:** `evaluation_quality`
- **Affected:** 1 business — Cowan's Public (competitive=45, h=True)
- **Spot-Check Evidence:** Cowan's Public has SEO=90, traffic=95 (both excellent), but competitive=45 hallucinated. This is a newly discovered business — first time through the pipeline.
- **Fix Direction:** Check if the competitive analyzer received valid competitor data for Cowan's Public.

## PATTERN-5: SEO and Competitive Borderline Failures [MEDIUM]

- **Aggregate Signal:** 2 businesses failed due to single capability scores just below 80.
- **Category:** `evaluation_quality`
- **Affected:** 2 businesses
  - The Oakley Kitchen: competitive=75 (5 points below threshold). SEO=90, traffic=95 both excellent.
  - Ralph's Pizzeria: SEO=65 (15 points below threshold). Traffic=95, competitive=95 both excellent.
- **Fix Direction:** These are legitimate evaluation results, not bugs. Consider whether the quality threshold (score >= 80 on ALL capabilities) is too strict — a single borderline score blocks businesses with otherwise excellent results.

## PATTERN-6: Overpass API Rate Limiting [LOW]

- **Aggregate Signal:** Overpass API returned HTTP 429 at 17:29:24 — 3rd occurrence this hour.
- **Category:** `model_health`
- **File:** Discovery agents using Overpass API
- **Fix Direction:** Cache per-zip Overpass queries or add retry with backoff.

## Qualification Audit

### Dynamic Threshold
- Research context: **Loaded** from zip 07110 research
- Market saturation: moderate
- Computed threshold: **30** (below default 40 — good for this market)

### Classification Breakdown (FINAL)
- **10 qualified (66.7%)** — 7 with prior enrichment + 3 newly discovered
- **5 parked (33.3%)**:
  - old-canal-inn: Full probe NoneType crash (had URL + Playwright data)
  - chris-and-angie-s-dinette: Full probe NoneType crash (had URL + Playwright data)
  - salumeria-regina: Playwright timeout + NoneType crash
  - bgl: Playwright timeout + NoneType crash
  - the-franklin-restaurant: No URL discovered (only business without URL)
- **4 of 5 parked businesses were parked due to the full probe NoneType bug** — they had URLs and some had extractable Playwright data

### Full Probe Impact
- 4 businesses entered full probe, 0 completed successfully
- At least 2 (old-canal-inn, chris-and-angie-s-dinette) had extractable data that could have upgraded scores above threshold 30
- **Fixing the NoneType bug would likely qualify 2-3 more businesses**, increasing the pipeline from 10 to 12-13 qualified

## Pipeline Funnel Summary

```
15 discovered
 → 14 with URLs (93%)
 → 10 qualified (67%) — 4 lost to full probe bug, 1 no URL
 → 10 analysis complete (100% of qualified)
 → Capabilities: SEO 10/10, Traffic 10/10, Competitive 9/10, Social 10/10, Margin 0/10
 → 4 passed evaluation (40% of qualified, 27% of total)
 → Awaiting approval
```

**Blockers preventing higher pass rate:**
1. Traffic hallucination: -3 businesses (Queen Margherita, Cucina 355, Pita Bowl)
2. Margin surgeon 100% failure: no margin analysis for any business
3. Borderline scores: -2 businesses (Oakley competitive=75, Ralph's SEO=65)
4. Competitive hallucination: -1 business (Cowan's Public)
