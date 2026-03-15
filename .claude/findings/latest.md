# Debug Report: of0O9BLmx46z0sLDZ55C
Generated: 2026-03-15T15:14:00Z
Workflow Phase: approval (analysis + evaluation completed)
Businesses: 34 total, 34 analysis done, 34 evaluation done, 0 quality passed, 34 quality failed

## FINDING-1: Traffic Forecaster Ignores Weather Research Data [HIGH]
- **Symptom:** All 11 qualified businesses have `traffic` evaluations flagged `isHallucinated=True` with scores 40-65 (below 80 threshold). This causes 100% quality failure rate — zero businesses pass evaluation.
- **File:** `packages/capabilities/hephae_capabilities/traffic/runner.py` (agent prompt or context injection)
- **Expected:** Traffic forecaster should incorporate `seasonal_weather` and `localContext` research from the identity context. The research explicitly warns of a "high-impact storm system on March 16th" and "significant temperature drop on March 17th". (Contract: `contracts/eval-standards.md` — evaluator checks factual grounding against provided context)
- **Actual:** Traffic forecaster outputs "Standard conditions expected" / "Clear conditions expected" / "No significant weather disruptions" for March 16-17, directly contradicting the research data provided in its input context.
- **Contract:** Evaluation Standards (CLAUDE.md § Evaluation Standards + `contracts/eval-standards.md`)
- **Evidence:**
  - MEAL eval: `score=40, isHallucinated=True` — "The forecast ignores the 'High-impact storm system' explicitly identified in the localContext"
  - The Bosphorus eval: `score=60, isHallucinated=True` — "The 'weatherNote' claims 'Standard conditions expected' for dates where research documents adverse conditions"
  - Cucina 355 eval: `score=40, isHallucinated=True` — "claiming 'Clear conditions expected'"
  - Pattern identical across all 11 businesses
- **Fix direction:** The traffic forecaster agent prompt must explicitly instruct the model to check and integrate `localContext.seasonal_weather` and `localContext.events` when generating weather notes and foot traffic impact assessments. The weather/event data is being passed in the identity but the agent is ignoring it.
- **Impact:** 100% quality failure rate blocks entire workflow from reaching outreach. No businesses can be approved.

## FINDING-2: capabilitiesCompleted Not Synced on insights_done or Terminal Status [MEDIUM]
- **Symptom:** Some businesses show fewer capabilities completed in the workflow state than what the task metadata actually records. MEAL shows `['social', 'traffic']` but task has `['social', 'traffic', 'seo']`. Rocky's shows `['social', 'traffic']` but task has `['social', 'traffic', 'seo']`.
- **File:** `apps/api/backend/workflows/phases/analysis.py:302-310`
- **Expected:** The poller should sync `capabilitiesCompleted` from task metadata on every substep transition (or at least on `insights_done` and task completion), not only on `capability_done:` transitions.
- **Actual:** The poller only syncs `capabilitiesCompleted` inside the `elif substep.startswith("capability_done:")` branch (line 302-307). If a `capability_done:` substep is overwritten by `insights_done` between 3-second polls (because capabilities run concurrently via `asyncio.gather`), the final capability's completion is never synced to the workflow state.
- **Contract:** Workflow Phase Integrity — business state should accurately reflect task execution results
- **Evidence:**
  - MEAL: task metadata `capabilitiesCompleted=['social', 'traffic', 'seo']`, workflow state `capabilitiesCompleted=['social', 'traffic']` (seo missing)
  - Rocky's: task metadata `capabilitiesCompleted=['social', 'traffic', 'seo']`, workflow state `capabilitiesCompleted=['social', 'traffic']` (seo missing)
  - Root cause: capabilities run concurrently (`asyncio.gather` at tasks.py:332), each writes `capability_done:{name}` substep. The last capability_done can be overwritten by `insights_done` within the same poll interval.
- **Fix direction:** Add `capabilitiesCompleted`/`capabilitiesFailed` sync to the `insights_done` substep handler (line 308-310) and to the terminal status handler (lines 325-333). Example:
  ```python
  elif substep == "insights_done":
      biz.capabilitiesCompleted = meta.get("capabilitiesCompleted", [])
      biz.capabilitiesFailed = meta.get("capabilitiesFailed", [])
      # ... existing callback
  ```
  Also add the same sync in the `STATUS_COMPLETED` handler block.
- **Impact:** Evaluation phase skips capabilities that were actually completed. For MEAL and Rocky's, SEO evaluation was skipped because SEO wasn't in `capabilitiesCompleted`, even though SEO results exist in the business document.

## FINDING-3: BigQuery evaluation_feedback Table Does Not Exist [MEDIUM]
- **Symptom:** Evaluation phase calls `record_evaluation_feedback()` which writes to `hephae.evaluation_feedback`, but this table doesn't exist in BigQuery.
- **File:** `packages/db/hephae_db/bigquery/feedback.py` (table definition) and `infra/setup.sh` (table creation)
- **Expected:** The `evaluation_feedback` table should be created during setup, per database contracts. (Contract: `contracts/bigquery-schema.md`)
- **Actual:** BigQuery dataset `hephae` contains only `analyses` and `discoveries` tables. No `evaluation_feedback` table exists.
- **Contract:** Database Rules (CLAUDE.md § Database Rules — historical data goes to BigQuery)
- **Evidence:** `bq ls "hephae-co-dev:hephae"` shows only `analyses` and `discoveries` tables. Running `bq query` against `evaluation_feedback` returns `NOT_FOUND`.
- **Fix direction:** Add the `evaluation_feedback` table creation to `infra/setup.sh` and verify the schema matches what `record_evaluation_feedback()` expects. Run the setup script to create the table.
- **Impact:** All evaluation history is silently lost. Cannot audit or analyze evaluation patterns over time. The `asyncio.create_task` call at evaluation.py:65 silently fails.

## FINDING-4: Competitive Analysis Always Skipped — No Competitors Discovered [LOW]
- **Symptom:** All 34 businesses have empty `competitors[]` arrays. The `competitive_analyzer` capability is skipped for every business because its `should_run` condition requires a non-empty competitors list.
- **File:** `packages/capabilities/hephae_capabilities/discovery/runner.py` (competitor discovery) and `apps/api/backend/workflows/capabilities/registry.py` (should_run condition)
- **Expected:** The discovery/enrichment pipeline should find competitors for businesses in the same zip code and business type. (Contract: capability registry — competitive_analyzer `should_run` checks `competitors` list)
- **Actual:** After enrichment, no business has any competitors populated. Either the discovery agent isn't finding them or the PROMOTE_KEYS sync in analysis.py isn't propagating them correctly (note: `competitors` IS in `PROMOTE_KEYS` at analysis.py:38).
- **Contract:** Capability Execution rules — capability should run when business has required data
- **Evidence:** All 34 businesses: `competitors: []` in workflow state. Business docs also show `competitors count: 0`.
- **Fix direction:** Investigate the discovery runner's competitor finding logic. Check if the competitor discovery sub-agent is producing results but they're not being persisted, or if it's failing silently.
- **Impact:** Competitive analysis capability never runs. This is an entire analysis dimension missing from all reports, reducing the value of the pipeline output.

## FINDING-5: Margin Surgeon Always Skipped — No Menu Data [LOW]
- **Symptom:** All 34 businesses have no `menuScreenshotBase64`. The `margin_surgeon` capability is skipped for every business.
- **File:** `packages/capabilities/hephae_capabilities/discovery/runner.py` (menu discovery) and `apps/api/backend/workflows/capabilities/registry.py`
- **Expected:** The discovery agent should find and capture menu data (screenshot or URL) during enrichment. The `menuUrl` field IS in PROMOTE_KEYS, and several businesses had URLs found by the menu discovery agent.
- **Actual:** While `menuUrl` may be discovered, `menuScreenshotBase64` is never populated. The registry condition checks for `menuScreenshotBase64` specifically.
- **Contract:** Capability Execution rules
- **Evidence:** All 34 businesses: `menuScreenshotBase64` not present.
- **Fix direction:** Either: (a) add a menu screenshot capture step to the enrichment pipeline that converts menuUrl to menuScreenshotBase64, or (b) update margin_surgeon's `should_run` condition to accept `menuUrl` as sufficient (the agent itself may support URL-based menu analysis with its PDF extraction flow).
- **Impact:** Margin analysis never runs. Menu-based insights and leakage analysis unavailable for all businesses.
