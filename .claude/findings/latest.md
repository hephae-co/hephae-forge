# Debug Report: WgjhRth9tmBlQIQ2tmPt
Generated: 2026-03-15T17:42:00Z
Zip: 07110 (Nutley, NJ) | Type: Restaurants | Phase: analysis (active) | Duration: ~12 min

## Workflow Summary

| Metric | Value |
|--------|-------|
| Workflow ID | WgjhRth9tmBlQIQ2tmPt |
| Zip Code / Business Type | 07110 / Restaurants |
| Phase | analysis (active) |
| Duration (created → last update) | ~12 min (17:29:11 → 17:41:39) |
| Total Businesses | 15 |
| Website Discovery Rate | 14 / 15 (93.3%) — massive improvement from prior 36.8% |
| Contact Info Rate | 7 / 15 (46.7%) — 7 have phone/email from enrichment |
| Social Link Rate | 6 / 15 (40%) — luna, oakley, ralph's, cucina, nutley-diner, pita-bowl from prior enrichment |
| Competitor Rate | 6 / 15 (40%) — 6 have 3 competitors each |
| Menu Rate | 6 / 15 (40%) — luna, oakley, ralph's, cucina, nutley-diner, rocky's |
| Enrichment Null Rate | TBD — enrichment still in progress for 5 businesses |
| Qualification Breakdown | 10 qualified, 5 parked (old-canal-inn, chris-and-angie-s, the-franklin, salumeria-regina, bgl) |
| Dynamic Threshold Used | 30 (saturation=moderate, loaded from zip research) |
| Retry Rate | 0 / 10 (0%) |

## Capability Coverage (10 qualified businesses, analysis in progress)

| Capability | should_run | Completed | Failed | Skipped | Notes |
|------------|-----------|-----------|--------|---------|-------|
| SEO | needs officialUrl (10) | 5 | 0 | 0 | 5 still in progress |
| Traffic | always (10) | 6 | 0 | 0 | 4 in progress |
| Competitive | always (10) | 5 | 1 | 0 | sugar-tree-caf failed |
| Margin Surgeon | menuScreenshotBase64 OR menuUrl (10) | 0 | 5 | 1 | **100% failure** |
| Social | always (10) | 6 | 0 | 0 | 4 in progress |

## Cross-Reference Flags

1. **sugar-tree-caf**: Business doc had url=MISSING before this workflow; now url=sugartreecafe.com (newly discovered by improved _find_website)
2. **queen-margherita**: Business doc had url=MISSING before; now url=qmargherita.com (newly discovered)
3. **bgl**: Has url=Y in workflow array but business doc still shows url=MISSING (enrichment pending or parked?)
4. **Prior enrichment data preserved**: luna, oakley, ralph's, cucina, nutley-diner, rocky's all have full enrichment from prior workflow 8x5Idxzp

## Improvements From Prior Workflow (8x5Idxzp)

| Metric | Prior (8x5Idxzp) | Current (WgjhRth9) | Change |
|--------|-------------------|---------------------|--------|
| Website Discovery Rate | 7/19 (36.8%) | 14/15 (93.3%) | +56.5pp |
| Research Context | None | Loaded (threshold=30) | Fixed |
| Businesses Qualified | 7/19 (36.8%) | 10/15 (66.7%) | +29.9pp |
| Enrichment Working | Yes | Yes | Stable |
| Margin Surgeon | 100% skip | 100% fail | **Regressed** |

---

## PATTERN-1: Margin Surgeon 100% Failure [CRITICAL]

- **Aggregate Signal:** 0 completions, 5 failures, 1 skip across all businesses with progress. No margin analysis produced.
- **Category:** `capability_execution`
- **Affected:** 10/10 qualified businesses (100%)
- **Spot-Check Evidence:**
  - luna-wood-fire-tavern: task completed with fail=['margin_surgeon'] — has menuUrl but no menuScreenshotBase64
  - queen-margherita: task completed with fail=['margin_surgeon'] — same pattern
  - sugar-tree-caf: task completed with skip=['margin_surgeon'] — only one that skipped instead of failing
- **Cascade Impact:** Zero margin analysis for any business → no menu pricing insights, no margin optimization recommendations.
- **Root Cause:** The `should_run` condition at `registry.py:207` was changed to: `lambda biz: bool(biz.get("menuScreenshotBase64") or biz.get("menuUrl"))`. This now returns True when `menuUrl` exists (which it does after enrichment), but the actual margin_surgeon runner likely still requires `menuScreenshotBase64` to function. The capability starts running and then crashes.
- **File:** `apps/api/hephae_api/workflows/capabilities/registry.py:207` (should_run) and the margin_surgeon runner
- **Fix Direction:** Either (a) update the margin_surgeon runner to accept `menuUrl` as input and fetch/screenshot the menu itself, or (b) revert should_run to only check `menuScreenshotBase64` until the runner supports URL-based input, or (c) add a menu screenshot step to enrichment that converts menuUrl → menuScreenshotBase64.

## PATTERN-2: Full Probe NoneType Crash [HIGH]

- **Aggregate Signal:** 3 out of 4 full probe attempts failed with `'NoneType' object has no attribute 'get'`. The 4th (BGL) timed out.
- **Category:** `qualification_error`
- **Affected:** 4 businesses in full probe (old-canal-inn, chris-and-angie-s-dinette, salumeria-regina, bgl)
- **Spot-Check Evidence:**
  - Old Canal Inn: Playwright crawled theoldcanalinn.com, extracted UI data (hasFavicon=True, primaryColor=#4f46e5), then probe FAILED with NoneType
  - Salumeria Regina: Playwright timed out on salumeriareginanj.com (30s), then probe FAILED with NoneType
  - BGL: Playwright timed out on thebgl.com (30s)
- **Root Cause:** `scanner.py:375` calls `crawl_web_page(url)` which returns `None` when the crawl times out or fails. Line 380 then does `crawl_data.get("deterministicContact", {})` which crashes because `crawl_data` is `None`.
- **File:** `agents/hephae_agents/qualification/scanner.py:375-380`
- **Fix Direction:** Add a null check: `if not crawl_data: return partial_result` before line 380. This would gracefully fall back to the Step A result when crawling fails.

## PATTERN-3: Overpass API Rate Limiting [MEDIUM]

- **Aggregate Signal:** Overpass API returned HTTP 429 at 17:29:24 — 13 seconds into this workflow.
- **Category:** `model_health`
- **Affected:** Potential degradation of local context for all businesses
- **Spot-Check Evidence:** Log: `HTTP Request: POST https://overpass-api.de/api/interpreter "HTTP/1.1 429 Too Many Requests"` — this is the 3rd occurrence across 3 workflows in the same hour.
- **File:** Discovery agents using Overpass API
- **Fix Direction:** Implement caching for Overpass queries by zip code (same data for same zip), or add retry with backoff.

## PATTERN-4: Competitive Capability Failure for Sugar Tree [LOW]

- **Aggregate Signal:** 1/6 competitive analyses failed (sugar-tree-caf).
- **Category:** `capability_execution`
- **Affected:** 1 business (sugar-tree-caf)
- **Spot-Check Evidence:** sugar-tree-caf task: completed with fail=['competitive']. This is a newly discovered business (first time through the pipeline) — no prior competitive data.
- **File:** `agents/hephae_agents/competitive_analysis/runner.py`
- **Fix Direction:** Check if the competitive runner received valid competitors data. Sugar Tree Cafe had 0 competitors on its business doc, which may cause the competitive analyzer to fail rather than skip.

## Qualification Audit

### Dynamic Threshold
- Research context: **Loaded** from zip 07110 research
- Market saturation: moderate
- Computed threshold: **30** (lower than default 40)
- This is good — a lower threshold qualifies more businesses

### Classification Breakdown
- 10 qualified (66.7%) — includes 7 with prior enrichment + 3 newly discovered (sugar-tree-caf, queen-margherita, cowan-s-public)
- 5 parked (33.3%):
  - old-canal-inn: Had URL in workflow, Playwright crawled but full probe crashed (NoneType bug)
  - chris-and-angie-s-dinette: Same — URL found, Playwright extracted data, probe crashed
  - the-franklin-restaurant: No URL in workflow
  - salumeria-regina: URL found, Playwright timed out, probe crashed
  - bgl: URL found, Playwright timed out, probe crashed
- **3 of 5 parked businesses were parked due to the full probe NoneType bug** — they had URLs and Playwright data but the probe crash caused them to fall back to Step A scores (below threshold 30)

### Full Probe Impact
- 4 businesses entered full probe
- 0 successfully completed full probe (3 NoneType crash, 1 timeout)
- At least 2 (old-canal-inn, chris-and-angie-s-dinette) had extractable data that could have upgraded their scores
- **Fix the NoneType bug and these businesses likely qualify** — old-canal-inn had hasFavicon=True, primaryColor=#4f46e5, linkCount=24; chris-and-angie-s had hasLogo=True, hasFavicon=True, linkCount=39
