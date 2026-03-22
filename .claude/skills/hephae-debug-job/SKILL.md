---
name: hephae-debug-job
description: Investigate running or failed Hephae workflows, discovery jobs, and weekly pulse jobs — aggregate-first pattern detection with cascade analysis, qualification audit, and strategic spot-checking. Produces structured findings for handoff to a coding agent.
argument-hint: [workflow-id-or-prefix | pulse | discovery-job]
---

# Debug Job — Pattern-First Workflow & Pulse Debugger

You are a debugger for the Hephae pipeline. Your job is to investigate workflows, discovery jobs, or weekly pulse jobs — diagnose issues against the system's design contracts, and produce a structured findings report.

**Core approach:** Collect → Aggregate → Detect patterns → Spot-check only what's suspicious → Trace cascades. Do NOT render a per-business dashboard — compute aggregate metrics instead and only drill into specific businesses when a pattern demands evidence.

## Input

The user will provide one or more of:
- A workflow ID or prefix (e.g., `of0O9BLm` matches `of0O9BLmx46z0sLDZ55C`)
- A discovery job ID or prefix (e.g., `abc123`)
- `pulse` or `pulse 07110` — debug weekly pulse for a zip code
- `discovery-job` or `discovery-jobs` — debug batch discovery jobs
- A symptom (e.g., "businesses stuck in analysis", "pulse missing signals")
- A zip code or business slug
- "check all running" to scan for any active workflows/jobs with issues

Arguments: $ARGUMENTS

**Routing logic:**
- If args contain "pulse" → go to PULSE DEBUG FLOW (below)
- If args contain "discovery-job" or match a `discovery_jobs` document → go to DISCOVERY JOB DEBUG FLOW (below)
- Otherwise → go to WORKFLOW DEBUG FLOW (existing phases 1-8)

If no ID is provided, list recent items from the relevant collection and ask which one to investigate.

## Authentication & API Access

All Firestore reads use the REST API with a gcloud access token:
```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## PHASE 1: COLLECT — Parallel Data Gathering

Gather ALL raw data needed for analysis. **Issue 1a, 1b, 1c, 1d as parallel Bash tool calls in a single response.**

### 1a. Resolve Workflow

If the user gave a partial ID, list workflows and find the match:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows?pageSize=20" | python3 -c "..."
```

Fetch the full workflow document. Parse it to extract:
- `phase`, `createdAt`, `updatedAt`, `zipCode`, `businessType`, `retryCount`, `lastError`
- `progress.*` counters
- Full `businesses[]` array with ALL fields per business

### 1b. Fetch ALL Business Documents (batched)

For EVERY business in the workflow, fetch the separate Firestore document at `businesses/{slug}`. **Batch fetches in groups of 10 slugs per Bash call** to avoid sequential round-trips:

```bash
TOKEN=$(gcloud auth print-access-token)
for slug in slug1 slug2 slug3 slug4 slug5 slug6 slug7 slug8 slug9 slug10; do
  curl -s -H "Authorization: Bearer $TOKEN" "$FIRESTORE_BASE/businesses/$slug" &
done
wait
```

The workflow `businesses[]` array has workflow-phase state; the separate `businesses/{slug}` document has enrichment data, latestOutputs, identity, etc. Discrepancies between these two sources are a finding.

Extract from each business doc:
- `officialUrl`, `phone`, `email`, `emailStatus`, `contactFormUrl`, `contactFormStatus`
- `socialLinks.*` (instagram, facebook, twitter, yelp, tiktok, etc.)
- `hours`, `googleMapsUrl`, `menuUrl`
- `competitors[]`
- `latestOutputs.*` (keys + scores + reportUrls)
- `identity.*`
- `crm.*` (if present)

### 1c. Fetch Task Documents (including retry metadata)

Query tasks by workflow ID to get execution metadata:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"tasks"}],"where":{"fieldFilter":{"field":{"fieldPath":"metadata.workflowId"},"op":"EQUAL","value":{"stringValue":"WORKFLOW_ID"}}},"limit":100}}'
```

Extract per task: `businessId`, `status`, `substep`, `createdAt`, `startedAt`, `completedAt`, `error`, and metadata fields:
- `capabilitiesCompleted`, `capabilitiesFailed`, `capabilitiesSkipped`
- **Retry fields:** `retryRound`, `retryOnlyCaps`, `retryTaskId`, `retriableFailures`

### 1d. Cloud Run Logs

```bash
# Recent API errors
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-api" AND severity>=ERROR' \
  --limit=50 --freshness=2h --format="table(timestamp, jsonPayload.message, textPayload)" \
  --project=$PROJECT

# Rate limiting / model errors
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"429|Resource exhausted|rate.limit"' \
  --limit=20 --freshness=1h --project=$PROJECT

# Model fallback events
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"ModelFallback|fallback"' \
  --limit=20 --freshness=2h --project=$PROJECT

# Retry/fallback task events
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"retry|RetryRound|retriable"' \
  --limit=20 --freshness=2h --project=$PROJECT
```

If gcloud or curl commands fail, tell the user what to run and ask for the output. Never guess at data you can't read.

---

## PHASE 2: COMPUTE AGGREGATES

Replace the verbose per-business dashboard with two compact tables. Compute these metrics from the collected data:

### 2a. Workflow Summary Table

| Metric | Value |
|--------|-------|
| Workflow ID | |
| Zip Code / Business Type | |
| Phase | |
| Duration (created → updated) | |
| Total Businesses | |
| Website Discovery Rate | {count with officialUrl} / {total} ({%}) |
| Contact Info Rate | {count with phone OR email OR contactFormUrl} / {total} ({%}) |
| Social Link Rate | {count with ≥1 socialLinks} / {total} ({%}) |
| Competitor Rate | {count with non-empty competitors[]} / {total} ({%}) |
| Menu Rate | {count with menuUrl} / {total} ({%}) |
| Enrichment Null Rate | {count where officialUrl exists but ALL enrichment fields null} / {count with officialUrl} ({%}) |
| Qualification Breakdown | {qualified} qualified, {parked} parked, {disqualified} disqualified |
| Dynamic Threshold Used | {threshold value, or "40 (default)" if no research context} |
| Retry Rate | {retry tasks} / {total tasks} ({%}) |
| Retry Success Rate | {successful retries} / {retry tasks} ({%}) |

### 2b. Capability Coverage Table

| Capability | should_run | Completed | Failed | Skipped | Avg Eval Score | Hallucination Count |
|------------|-----------|-----------|--------|---------|----------------|---------------------|
| SEO | needs `officialUrl` | | | | | |
| Traffic | always | | | | | |
| Competitive | always | | | | | |
| Margin Surgeon | needs `menuScreenshotBase64` | | | | | |
| Social | always | | | | | |

### 2c. Cross-Reference Check

Flag discrepancies between workflow `businesses[]` state and actual `businesses/{slug}` documents:
- `officialUrl` mismatch
- `capabilitiesCompleted` count mismatch (workflow progress vs task metadata)
- `latestOutputs` keys present on doc but not reflected in workflow caps

Output both tables and any cross-reference flags. This is the "dashboard" — high-signal, low-noise.

---

## PHASE 3: DETECT PATTERNS — Anomaly Rules

Apply these detection rules against the aggregates. Each triggered rule becomes a PATTERN finding.

### Rule 1: 100% Eval Failure
**Trigger:** All evaluated businesses fail (score < 80 OR isHallucinated) for one or more capabilities.
**Severity:** CRITICAL
**Next:** Identify which capability is the common denominator. Check if evaluator agent is crashing ("Failed to parse evaluator output") or if the underlying capability agent has a prompt/context bug.

### Rule 2: High Enrichment Null Rate (>50%)
**Trigger:** More than 50% of businesses with `officialUrl` have all enrichment fields null (no phone, email, socialLinks, hours, competitors, etc.).
**Severity:** CRITICAL
**Next:** Discovery Phase 2 sub-agents may be broken. Spot-check 2-3 URLs to verify data exists on the actual websites.

### Rule 3: Zero Capability Coverage
**Trigger:** A capability has 0 completions across all qualified businesses.
**Severity:** HIGH
**Next:** Trace to `should_run` condition in registry. Check if upstream data required by the condition is missing (e.g., no businesses have `officialUrl` → SEO never runs; no `menuScreenshotBase64` → Margin Surgeon never runs).

### Rule 4: Qualification Skew (parked >70%)
**Trigger:** More than 70% of discovered businesses are parked.
**Severity:** HIGH
**Next:** Check if threshold is too aggressive (saturated market → threshold=60) OR if enrichment failure is feeding bad data to scoring. Compare against the dynamic threshold formula:
- Base: 40
- Saturated (≥40 competitors or "saturated"): 60
- High (≥20 competitors or "high"): 50
- Low (<10 competitors or "low"): 30
- High opportunity (score >70): threshold -= 10
- Clamped to [20, 70]

### Rule 5: Retry Storm (>30% retry rate)
**Trigger:** More than 30% of tasks are retries.
**Severity:** HIGH
**Next:** Check which model tier is causing failures. Look for 429/503/529 errors in logs. Check if rate limits are hitting primary model (`gemini-3.1-flash-lite-preview`) and whether fallback to `gemini-2.5-flash-lite` is working.

### Rule 6: Uniform Eval Hallucination
**Trigger:** A single capability has hallucination flagged on >50% of its evaluations.
**Severity:** HIGH
**Next:** The capability's agent likely has a prompt or context bug. For traffic: check if weather/event research data is being passed. For SEO: check if PageSpeed data is available. Spot-check evaluator complaints against actual source data.

### Rule 7: Research Context Starvation
**Trigger:** No area research, zipcode research, or sector research loaded (all null/empty on workflow).
**Severity:** HIGH
**Next:** Without research context, threshold defaults to 40 (no dynamic adjustment), weather/events aren't available for traffic, and sector-specific scoring bonuses don't apply. Check orchestrator logs for research agent failures.

### Rule 8: Outreach Dead End
**Trigger:** Approved businesses (qualityPassed=true) are missing ALL of: email, phone, contactFormUrl.
**Severity:** MEDIUM
**Next:** These businesses passed quality gates but outreach has no channel to reach them. Check if enrichment found contact info that wasn't persisted, or if the qualification scanner approved them via scoring bonuses that bypassed contact requirements.

### Rule 9: capabilitiesCompleted Sync Gap
**Trigger:** Task metadata shows capabilities completed but workflow `businesses[]` entry doesn't reflect them (known race condition with polling).
**Severity:** MEDIUM
**Next:** Count affected businesses. This is a known issue — the analysis poller may miss the final `capabilitiesCompleted` update due to substep race condition.

For each triggered rule, record: severity, affected count/percentage, and whether it needs spot-check or cascade analysis.

---

## PHASE 4: SPOT-CHECK VERIFICATION — Strategic Sampling

For each triggered pattern, pick **2-3 businesses** using this sampling strategy:
- 1 "worst case" (most data missing, lowest score, most failures)
- 1 "typical case" (representative of the pattern)
- 1 "edge case" (borderline, almost didn't trigger the pattern)

### Verification Categories

**Website miss verification** (for parked businesses claiming "No website"):
1. Use WebSearch for `"{business name}" {city} {state} website`
2. Use WebFetch to check common URL patterns (`https://{slugified-name}.com`, etc.)
3. Report whether a website actually exists

**Contact miss verification** (for businesses with website but no contact info):
1. Use WebFetch on `{officialUrl}/contact`, `{officialUrl}/contact-us`, `{officialUrl}/about`
2. Check if these pages contain form elements, mailto links, or phone numbers

**Qualification audit** (for borderline parked/qualified businesses):
1. Reconstruct the scoring using actual weights from `scanner.py`:
   - Custom domain: +15, Platform subdomain: +8
   - HTTPS: +3, Platform detected: +10
   - Multiple analytics pixels: +10, Single pixel: +5
   - Contact path: +8, Mailto: +5, Tel: +3
   - Strong social (≥3): +8, Some social (≥1): +4
   - JSON-LD: +5, Page title: +2
   - Innovation Gap (modern platform + no social): +20
   - Aggregator Escape (dining on delivery + weak website): +20
   - Economic Delta (wealthy area + poor digital): +15
   - Services gap (website but no contact path): +10
   - Retail gap (custom domain but no e-commerce): +8
2. Compare reconstructed score against the dynamic threshold used

**Evaluation claim verification** (for failing evaluations):
1. Read the evaluator's specific complaints
2. Check if those complaints match the actual source data in the capability output
3. Determine if the evaluator is wrong (hallucination by evaluator) or right (real quality issue)

**Enrichment data verification** (for null enrichment):
1. Use WebFetch on the business URL
2. Check if the page contains data that enrichment should have extracted
3. Compare against what's stored in Firestore

---

## PHASE 5: CASCADE ANALYSIS

For each triggered pattern, trace its downstream effects using these cascade trees:

### Cascade: Enrichment Nulls
```
Enrichment all-null (despite URL existing)
├── SEO skipped (no crawl data to audit)
├── Competitive skipped (no competitors found)
├── Margin Surgeon skipped (no menu screenshot)
├── Social works blind (no social links to audit)
├── Outreach impossible (no email/phone/contactForm)
└── Lower qualification scores (missing signals → lower score)
```
Quantify: "Enrichment null rate of X% caused competitive skip rate of Y%, margin skip rate of Z%"

### Cascade: No Website Found
```
No website discovered
├── officialUrl empty → enrichment has nothing to crawl
│   └── (same cascade as enrichment nulls above)
├── Qualification score capped (no domain, platform, pixel, contact bonuses)
└── Likely parked (score ≈ 0 vs threshold of 30-60)
```

### Cascade: Research Context Failed
```
Research agents failed (area/zipcode/sector)
├── Default threshold (40) — no dynamic adjustment
├── No weather/events data → traffic hallucination
├── No demographic data → Economic Delta bonus never fires
├── No sector data → tech-forward bonus never fires
└── No competitive landscape → saturation unknown → threshold stays at 40
```

### Cascade: Rate Limit Storm
```
API rate limits hit
├── Capabilities fail with 429/503/529
├── Retries queued (retryRound incremented)
├── If all retries fail → permanent capability gap
├── If fallback model also fails → double failure
└── If many businesses affected → extends workflow duration significantly
```

For each cascade, quantify the downstream impact with actual counts from the aggregates.

---

## PHASE 6: QUALIFICATION AUDIT

Perform a focused qualification audit regardless of whether Rule 4 triggered:

### 6a. Dynamic Threshold Check
- Was research context loaded? (Check workflow for area_research, zipcode_research, sector_research)
- What market saturation was detected?
- What was the computed threshold? (Use formula from `threshold.py`:
  - Base=40, saturated/≥40 biz→60, high/≥20 biz→50, low/<10 biz→30
  - Opportunity score >70 → subtract 10
  - Clamp to [20, 70])

### 6b. Scoring Reconstruction (2-3 borderline businesses)
- Reconstruct the score using the actual weights from `scanner.py` (listed in Phase 4)
- Compare against the threshold
- Determine: was the outcome correct given the data?

### 6c. Classification Breakdown
- Count "parked due to enrichment failure" (has URL but enrichment all-null → low score)
- Count "parked due to no website" (no officialUrl at all)
- Count "parked due to legitimate lack of data" (website exists, enrichment ran, just not enough signals)
- Count "disqualified as chain" vs "disqualified as dead site"

### 6d. Full Probe Outcomes
- How many businesses needed full probe (Step B)?
- Did full probe (browser crawl + LLM classifier) upgrade any from parked to qualified?
- Was the LLM tiebreaker used? If so, what did it decide?

---

## PHASE 7: MONITOR (if workflow is active)

If the workflow is NOT in a terminal phase (COMPLETED, FAILED, APPROVAL), enter a monitoring loop:

1. **Re-poll the workflow document** every 30 seconds
2. **Detect new phase transitions** since the last poll
3. **Report progress** changes (new businesses completing analysis, new evaluations, etc.)
4. **Track retry tasks** appearing during monitoring
5. **Detect stalls** — if `updatedAt` hasn't changed in >5 minutes, flag it
6. **Exit conditions:**
   - Workflow reaches COMPLETED, FAILED, or APPROVAL phase
   - User interrupts
   - 60 minutes elapsed (safety valve)

During monitoring, periodically re-check tasks for newly completed businesses and report deltas.

---

## PHASE 8: REPORT & MEMORY

### 8a. Write Findings Report

Write findings to `.claude/findings/latest.md` in this format:

```markdown
# Debug Report: {workflow_id}
Generated: {ISO timestamp}
Zip: {zip} | Type: {type} | Phase: {phase} | Duration: {duration}

## Summary
{Workflow Summary table from Phase 2a}

## Capability Coverage
{Capability Coverage table from Phase 2b}

## PATTERN-{N}: {title} [{CRITICAL|HIGH|MEDIUM|LOW}]
- **Aggregate Signal:** {what the numbers show — e.g., "100% traffic eval failure, 0/12 passed"}
- **Category:** {one of the categories below}
- **Affected:** {count} businesses ({percentage}%)
- **Spot-Check Evidence:** {2-3 specific examples from Phase 4}
- **Cascade Impact:** {downstream effects with quantities from Phase 5}
- **File:** {exact file path in current repo structure}
- **Fix Direction:** {specific guidance}
```

### Severity Levels
- **CRITICAL** = Discovery data is wrong OR systemic quality failure (100% eval failure, >50% enrichment null)
- **HIGH** = Workflow blocked, zero capability coverage, qualification skew, retry storm
- **MEDIUM** = Sync gaps, outreach dead ends, minor data inconsistencies
- **LOW** = Cosmetic, minor inefficiency, or non-blocking issue

### Finding Categories
- `discovery_accuracy` — Business has data that discovery didn't find
- `enrichment_gap` — Enrichment ran but missed data that exists
- `qualification_error` — Qualification outcome wrong given actual data
- `capability_execution` — Capability should have run but didn't, or vice versa
- `evaluation_quality` — Systemic evaluation failure, threshold issues
- `cascade_failure` — Upstream failure causing downstream capability gaps
- `retry_health` — Rate limits, retry storms, fallback failures
- `outreach_readiness` — Approved businesses lack outreach channels
- `phase_integrity` — Workflow or business phase transition violation
- `model_health` — Rate limiting, fallback cascades, agent crashes
- `timing` — Tasks too slow, stuck, or queued too long

Sort findings: CRITICAL → HIGH → MEDIUM → LOW.

Also output the full findings summary to the conversation so the user can read it immediately.

### 8b. Recurring Pattern Detection

After producing findings, check memory at `.claude/projects/*/memory/` for previously seen patterns. If the same issue (same agent failing, same phase stalling, same error type) has occurred before, update the memory with the new occurrence count.

Save new recurring patterns:
```markdown
---
name: recurring-{issue-type}
description: {pattern description}
type: project
---

{pattern} has occurred {N} times across workflows.
**Why:** {root cause if known}
**How to apply:** Flag immediately in future debug runs.
```

---

## Workflow Phase & Business Phase References

### Expected workflow phase transitions (strictly sequential):
```
DISCOVERY → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH → COMPLETED
```

**Check for:**
- Phase skipping (went from DISCOVERY directly to ANALYSIS)
- Stuck too long (DISCOVERY: >5 min, QUALIFICATION: >3 min, ANALYSIS: >40 min, EVALUATION: >10 min)
- FAILED with no `lastError`
- COMPLETED but progress counters inconsistent

### Expected business phase transitions:
```
PENDING → ENRICHING → ANALYZING → ANALYSIS_DONE → EVALUATING → EVALUATION_DONE → APPROVED → OUTREACHING → OUTREACH_DONE
```
Terminal: `REJECTED`, `OUTREACH_FAILED`

### Capability should_run conditions (from registry.py):

| Capability | should_run | Firestore Key |
|---|---|---|
| `seo` | `officialUrl` must exist | `seo_auditor` |
| `traffic` | always runs (no condition) | `traffic_forecaster` |
| `competitive` | always runs (no condition) | `competitive_analyzer` |
| `margin_surgeon` | `menuScreenshotBase64` must exist | `margin_surgeon` |
| `social` | always runs (no condition) | `social_media_auditor` |

### Evaluation pass threshold:
`score >= 80 AND isHallucinated == false`

### Database rules to check:
1. **No blobs in Firestore** — check for base64 data (especially `menuScreenshotBase64`)
2. **`zipCode` is first-class** — verify it's a top-level field on business docs
3. **No growing arrays** — check for `reports[]`, `analyses[]` on business docs
4. **`update()` with dotted paths** — check logs for `set()` warnings

---

## Key Codebase References

| Area | File |
|------|------|
| Analysis orchestrator + polling | `apps/api/hephae_api/workflows/phases/analysis.py` |
| Task handler (enrichment + capabilities) | `apps/api/hephae_api/routers/admin/tasks.py` |
| Enrichment + website finding | `apps/api/hephae_api/workflows/phases/enrichment.py` |
| Discovery runner (2-phase) | `agents/hephae_agents/discovery/runner.py` |
| Qualification scanner (scoring + 2-step) | `agents/hephae_agents/qualification/scanner.py` |
| Dynamic threshold computation | `agents/hephae_agents/qualification/threshold.py` |
| Chain detection | `agents/hephae_agents/qualification/chains.py` |
| Qualification tools (page fetch, domain, etc.) | `agents/hephae_agents/qualification/tools.py` |
| Evaluation phase | `apps/api/hephae_api/workflows/phases/evaluation.py` |
| Outreach phase | `apps/api/hephae_api/workflows/phases/outreach.py` |
| Capability registry + should_run | `apps/api/hephae_api/workflows/capabilities/registry.py` |
| Workflow engine + checkpointing | `apps/api/hephae_api/workflows/engine.py` |
| Workflow Firestore I/O | `lib/db/hephae_db/firestore/workflows.py` |
| Business Firestore I/O | `lib/db/hephae_db/firestore/businesses.py` |
| Agent versions config | `apps/api/hephae_api/config.py` |
| Type definitions | `apps/api/hephae_api/types.py` |
| Evaluator agents | `agents/hephae_agents/evaluators/` |
| Social outreach generator | `agents/hephae_agents/social/outreach_generator/` |
| Discovery phase | `apps/api/hephae_api/workflows/phases/discovery.py` |
| Eval standards contract | `infra/contracts/eval-standards.md` |

---

# DISCOVERY JOB DEBUG FLOW

When the user asks to debug a discovery job (batch discovery), use this flow instead of the workflow phases above.

## DJ-1: COLLECT — Fetch Discovery Job Data

### DJ-1a. Resolve Job

```bash
# List recent discovery jobs
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/discovery_jobs?pageSize=20" | python3 -c "..."
```

If the user gave a partial ID, find the match. If they said "last" or "latest", fetch the most recent by `createdAt`. Fetch the full document and extract:
- `name`, `status`, `createdAt`, `startedAt`, `completedAt`
- `targets[]` (zipCode + businessTypes per target)
- `progress` (totalZips, completedZips, totalBusinesses, qualified, skipped, failed)
- `settings` (freshnessDiscoveryDays, freshnessAnalysisDays, rateLimitSeconds)
- `skipReasons[]` (sampled list, max 50)
- `error` (if failed)
- `notifyEmail`

**Statuses:** `pending` → `running` → `review_required` | `outreach_pending` | `completed` | `failed` | `cancelled`

### DJ-1b. Fetch Affected Businesses

For each target zipCode, query businesses that were touched by this job:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"businesses"}],"where":{"fieldFilter":{"field":{"fieldPath":"zipCode"},"op":"EQUAL","value":{"stringValue":"ZIP_CODE"}}},"limit":50}}'
```

Extract per business: `slug`, `officialUrl`, `discoveryStatus`, `qualificationOutcome`, `latestOutputs` keys, `updatedAt`.

### DJ-1c. Cloud Run Job Logs

The batch runner is `hephae-forge-batch` (Cloud Run Job), launched via `apps/api/hephae_api/lib/job_launcher.py`.

```bash
# Batch job logs
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="hephae-forge-batch" AND textPayload=~"DiscoveryJobs"' \
  --limit=50 --freshness=8h --format="table(timestamp, severity, textPayload)" \
  --project=$PROJECT

# Errors
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="hephae-forge-batch" AND severity>=ERROR' \
  --limit=30 --freshness=8h --project=$PROJECT
```

---

## DJ-2: COMPUTE AGGREGATES

### DJ-2a. Job Summary Table

| Metric | Value |
|--------|-------|
| Job ID / Name | |
| Status | |
| Duration (started → completed) | |
| Targets | {N} zip codes |
| Total Businesses Discovered | |
| Qualified | {N} ({%}) |
| Skipped | {N} ({%}) |
| Failed | {N} ({%}) |
| Freshness Settings | discovery={N}d, analysis={N}d |
| Rate Limit | {N}s between businesses |

### DJ-2b. Per-Zip Breakdown

For each target zip, count businesses by status:
- Discovered + qualified (has `latestOutputs`)
- Discovered + skipped (freshness or quality gate)
- Failed (discovery or capability error)

### DJ-2c. Skip Reason Analysis

Categorize `skipReasons[]`:
- "fresh_discovery" — recently discovered, skipped
- "fresh_analysis" — recently analyzed, skipped
- "quality_gate_rejected" — LLM quality gate said no
- "chain_detected" — franchise/chain exclusion
- "no_contact" — no contact info found
- Other

---

## DJ-3: DETECT PATTERNS

### DJ Rule 1: High Skip Rate (>60%)
**Trigger:** More than 60% of discovered businesses were skipped.
**Next:** Check if freshness thresholds are too aggressive (freshnessDiscoveryDays too low = everything is "fresh"). Or quality gate is too strict.

### DJ Rule 2: High Failure Rate (>20%)
**Trigger:** More than 20% of businesses failed.
**Next:** Check Cloud Run Job logs for errors. Common: rate limiting (429), model errors, Playwright timeouts.

### DJ Rule 3: Zero Qualified
**Trigger:** Job completed with `qualified=0`.
**Next:** Either all businesses are fresh (skipped), quality gate rejected everything, or discovery found nothing. Check `skipReasons` distribution.

### DJ Rule 4: Job Stuck in Running
**Trigger:** Job has `status=running` but `startedAt` > 2 hours ago with no progress change.
**Next:** Cloud Run Job may have crashed. Check job execution logs.

### DJ Rule 5: Quality Gate Hallucination
**Trigger:** Quality gate rejected businesses that clearly have websites + contact info.
**Next:** Spot-check 2-3 rejected businesses — fetch their Firestore docs and verify the data.

---

## DJ-4: SPOT-CHECK (2-3 businesses per pattern)

For each triggered pattern:
- **Skipped businesses**: Check if freshness dates are reasonable. Were they actually analyzed recently?
- **Failed businesses**: Check error messages in logs. Systemic (model 429) or per-business (Playwright timeout)?
- **Quality gate rejects**: Verify the business data — website, contact info, social links?

---

## DJ-5: REPORT

Write findings to `.claude/findings/latest.md`:

```markdown
# Debug Report: Discovery Job {job_id}
Generated: {ISO timestamp}
Job: {name} | Status: {status} | Targets: {N} zips | Duration: {duration}

## Job Summary
{DJ-2a table}

## Skip Reason Distribution
{DJ-2c breakdown}

## PATTERN-{N}: {title} [{severity}]
...
```

---

# WEEKLY PULSE DEBUG FLOW

When the user asks to debug weekly pulse, use this flow. Pulse has three layers:
1. **Pulse Jobs** (`pulse_jobs` collection) — async job tracking (QUEUED/RUNNING/COMPLETED/FAILED)
2. **Pulse Results** (`zipcode_weekly_pulse` collection) — the actual pulse output with insights + diagnostics
3. **Registered Zipcodes** (`registered_zipcodes` collection) — cron scheduling for auto-run
4. **Batch Work Items** (`pulse_batch_work_items` collection) — county-wide batch tracking

If the user says "debug pulse" without specifying, check recent pulse jobs first. If they give a zip code, look up pulses for that zip. If they say "last pulse" or "latest", fetch the most recent pulse job or result.

## WP-1: COLLECT — Fetch Pulse Data

### WP-1a. List Recent Pulse Jobs

```bash
# List recent pulse jobs (tracks execution status)
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/pulse_jobs?pageSize=10" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for doc in data.get('documents', []):
    f = doc.get('fields', {})
    doc_id = doc['name'].split('/')[-1]
    status = f.get('status', {}).get('stringValue', '?')
    zip_code = f.get('zipCode', {}).get('stringValue', '?')
    biz_type = f.get('businessType', {}).get('stringValue', '?')
    week = f.get('weekOf', {}).get('stringValue', '?')
    error = f.get('error', {}).get('stringValue', '')
    print(f'{doc_id}: {zip_code}/{biz_type} week={week} status={status} error={error[:80]}')
"
```

Extract per job: `zipCode`, `businessType`, `weekOf` (ISO format: "2026-W12"), `status`, `force`, `startedAt`, `completedAt`, `timeoutAt`, `error`, `testMode`, `result.pulseId`, `result.insightCount`, `result.headline`.

**Pulse Job Statuses:** `QUEUED` → `RUNNING` → `COMPLETED` | `FAILED`
- `timeoutAt` = startedAt + 15 minutes — auto-fails if exceeded

### WP-1b. Fetch Pulse Results

```bash
# List recent pulse results (the actual output)
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/zipcode_weekly_pulse?pageSize=10" | python3 -c "..."
```

If a specific zip is given, filter. Extract from each pulse result:
- Document ID (format: `{zip}-{type_slug}-{YYYYMMDD}-{HHMMSS}`)
- `zipCode`, `businessType`, `weekOf` (ISO week: "2026-W12")
- `pulse.headline`
- `pulse.insights[]` — count, plus per insight: `rank`, `title`, `impactScore`, `impactLevel`, `timeSensitivity`, `signalSources[]`
- `pulse.quickStats` — trendingSearches, weatherOutlook, upcomingEvents, priceAlerts
- `signalsUsed[]`
- `diagnostics.sources` — per source: status (ok/empty/error/skipped) + detail
- `diagnostics.signalCount`, `insightCount`, `critiquePass`, `critiqueScore`, `playbooksMatched`
- `diagnostics.startedAt`, `diagnostics.completedAt`
- `pipelineDetails` — intermediate outputs (macroReport, localReport, trendNarrative, socialPulse, localCatalysts, preComputedImpact, matchedPlaybooks, critiqueResult, rawSignals)
- `testMode`, `expireAt`

### WP-1c. Check Cron / Registered Zipcodes

```bash
# List registered zipcodes (what's auto-scheduled)
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/registered_zipcodes?pageSize=20" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for doc in data.get('documents', []):
    f = doc.get('fields', {})
    doc_id = doc['name'].split('/')[-1]
    status = f.get('status', {}).get('stringValue', '?')
    zip_code = f.get('zipCode', {}).get('stringValue', '?')
    biz_type = f.get('businessType', {}).get('stringValue', '?')
    count = f.get('pulseCount', {}).get('integerValue', '0')
    last = f.get('lastPulseAt', {}).get('stringValue', f.get('lastPulseAt', {}).get('timestampValue', 'never'))
    print(f'{doc_id}: {zip_code}/{biz_type} status={status} pulseCount={count} lastPulse={last}')
"
```

Extract: `zipCode`, `businessType`, `city`, `state`, `status` (active/paused), `pulseCount`, `lastPulseAt`, `lastPulseId`, `nextScheduledAt`.

### WP-1d. Check Batch Work Items (if county-wide run)

```bash
# If debugging a batch, list work items
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"pulse_batch_work_items"}],"where":{"fieldFilter":{"field":{"fieldPath":"batchId"},"op":"EQUAL","value":{"stringValue":"BATCH_ID"}}},"limit":50}}'
```

**Batch Work Item Statuses:** `QUEUED` → `FETCHING` → `RESEARCH` → `PRE_SYNTHESIS` → `SYNTHESIS` → `CRITIQUE` → `COMPLETED` | `FAILED`

### WP-1e. Logs

```bash
# Pulse logs from API (single pulse runs in-process)
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-forge-api" AND textPayload=~"WeeklyPulse|PulseJob|PulseCron"' \
  --limit=40 --freshness=4h --format="table(timestamp, textPayload)" \
  --project=$PROJECT

# Batch pulse logs (county-wide runs via Cloud Run Job)
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="hephae-forge-batch" AND textPayload=~"PulseBatch|pulse"' \
  --limit=40 --freshness=8h --format="table(timestamp, textPayload)" \
  --project=$PROJECT
```

---

## WP-2: COMPUTE AGGREGATES

### WP-2a. Pulse Job Summary Table

| Metric | Value |
|--------|-------|
| Job ID | |
| Pulse Doc ID | |
| Zip Code / Business Type | |
| Week Of (ISO) | |
| Status | |
| Test Mode | |
| Duration (started → completed) | |
| Timeout At | |
| Headline | |
| Insight Count | |
| Signal Count | |
| Critique Pass / Score | |
| Playbooks Matched | |

### WP-2b. Signal Health Table

Build from `diagnostics.sources`:

| Signal Source | Status | Detail |
|---------------|--------|--------|
| weather | ok/empty/error/skipped | |
| bls_cpi | ok/empty/error/skipped | |
| usda_prices | ok/empty/error/skipped | |
| fda_recalls | ok/empty/error/skipped | |
| google_news | ok/empty/error/skipped | |
| google_trends | ok/empty/error/skipped | |
| local_catalysts | ok/empty/error/skipped | |
| nj_legal_notices | ok/empty/error/skipped | |
| social_pulse | ok/empty/error/skipped | |
| maps_density | ok/empty/error/skipped | |
| zipcode_research | ok/empty/error/skipped | |
| prior_pulse | ok/empty/error/skipped | |

Count: sources_ok, sources_empty, sources_error, sources_skipped.

### WP-2c. Cron Health (if applicable)

| Metric | Value |
|--------|-------|
| Registered Zipcodes (active) | |
| Registered Zipcodes (paused) | |
| Last Cron Run | |
| Next Scheduled | |
| Zips with stale pulses (>7d) | |

### WP-2d. Insight Quality Table

| # | Title | Impact | Time Sensitivity | Signal Sources | Actionability |
|---|-------|--------|-------------------|----------------|---------------|
| 1 | ... | 85 (high) | this_week | weather, events | ... |

---

## WP-3: DETECT PATTERNS

### WP Rule 1: Low Signal Count (<4 sources OK)
**Trigger:** Fewer than 4 signal sources returned `ok`.
**Severity:** HIGH
**Next:** Check which sources failed. Common: missing API keys (BLS_API_KEY, USDA_NASS_API_KEY, FRED_API_KEY), NWS timeout, RSS change.

### WP Rule 2: Zero Insights Generated
**Trigger:** `insightCount = 0` despite signals available.
**Severity:** CRITICAL
**Next:** Synthesis agent failed. Check logs for `[WeeklyPulse]` errors, model failures, or malformed input. Check `pipelineDetails` for which stage failed.

### WP Rule 3: Critique Failed
**Trigger:** `diagnostics.critiquePass = false` or `critiqueScore` below threshold.
**Severity:** HIGH
**Next:** The synthesis output was rejected by the critique stage. Check `pipelineDetails.critiqueResult` for specific complaints. Common: obvious insights, lack of cross-signal reasoning, insufficient actionability.

### WP Rule 4: Stale Data (No Delta Detection)
**Trigger:** `prior_pulse` source shows `empty` or `skipped`. No week-over-week comparison.
**Severity:** MEDIUM
**Next:** First run for this zip/type? Expected. Otherwise check `weekly_pulse.py` Firestore query for prior pulse.

### WP Rule 5: Cross-Signal Hallucination
**Trigger:** Insights cite data sources that show `error` or `skipped` in diagnostics.
**Severity:** HIGH
**Next:** Compare each insight's `signalSources[]` against `diagnostics.sources`. If insight cites "BLS CPI" but `bls_cpi` status is `error`, the agent hallucinated that data.

### WP Rule 6: Pulse Job Timeout
**Trigger:** Pulse job `status=FAILED` and error contains "timeout" or `timeoutAt` was exceeded.
**Severity:** HIGH
**Next:** The 15-minute timeout was hit. Check which pipeline stage was slow — signal fetching (external APIs) or synthesis (Gemini). Check `pipelineDetails` to see which stages completed.

### WP Rule 7: Batch Work Items Stuck
**Trigger:** Batch work items stuck in intermediate stages (FETCHING, RESEARCH, PRE_SYNTHESIS, SYNTHESIS, CRITIQUE) for >10 minutes.
**Severity:** HIGH
**Next:** Check batch job logs. A work item can get stuck if the Cloud Run Job crashes mid-processing.

### WP Rule 8: Cron Not Firing
**Trigger:** `registered_zipcodes` has active entries but `lastPulseAt` is >7 days old, and `nextScheduledAt` is in the past.
**Severity:** HIGH
**Next:** Cloud Scheduler may not be triggering `/api/cron/weekly-pulse`. Check scheduler job status with `gcloud scheduler jobs describe`.

### WP Rule 9: All Insights Low Impact
**Trigger:** All insights have `impactScore < 50`.
**Severity:** LOW
**Next:** Genuinely quiet week, or synthesis agent overly conservative.

### WP Rule 10: Duplicate/Redundant Insights
**Trigger:** Multiple insights cover same topic.
**Severity:** LOW
**Next:** Check `pipelineDetails.critiqueResult` — critique should catch this.

---

## WP-4: SPOT-CHECK

For each triggered pattern:
- **Failed signal sources**: Check API key config. Try the external API manually (e.g., curl NWS forecast endpoint).
- **Hallucinated insights**: Cross-reference `signalSources` vs `diagnostics.sources`. Verify claims with WebSearch.
- **Pipeline stage failures**: Read `pipelineDetails` — which intermediate outputs exist (macroReport, localReport, trendNarrative, socialPulse, localCatalysts)? Where did the chain break?
- **Cron issues**: Check `gcloud scheduler jobs list` and recent cron invocations.

---

## WP-5: REPORT

Write findings to `.claude/findings/latest.md`:

```markdown
# Debug Report: Weekly Pulse
Generated: {ISO timestamp}
Zip: {zip} | Type: {type} | Week: {weekOf} | Job Status: {status}

## Pulse Summary
{WP-2a table}

## Signal Health
{WP-2b table}

## Insight Quality
{WP-2d table}

## Cron Health (if applicable)
{WP-2c table}

## PATTERN-{N}: {title} [{severity}]
...
```

---

# COMBINED KEY CODEBASE REFERENCES

The following table extends the workflow references with discovery job and pulse file paths:

| Area | File |
|------|------|
| Discovery job CRUD | `apps/api/hephae_api/routers/admin/discovery_jobs.py` |
| Discovery job Firestore | `lib/db/hephae_db/firestore/discovery_jobs.py` |
| Discovery orchestrator | `apps/api/hephae_api/workflows/scheduled_discovery/orchestrator.py` |
| Discovery quality gate | `apps/api/hephae_api/workflows/scheduled_discovery/quality_gate.py` |
| Discovery capability dispatcher | `apps/api/hephae_api/workflows/scheduled_discovery/dispatcher.py` |
| Discovery notifier | `apps/api/hephae_api/workflows/scheduled_discovery/notifier.py` |
| Batch entrypoint | `apps/batch/hephae_batch/main.py` |
| Job launcher (Cloud Run Jobs) | `apps/api/hephae_api/lib/job_launcher.py` |
| Weekly pulse orchestrator | `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py` |
| Weekly pulse agent | `agents/hephae_agents/research/weekly_pulse_agent.py` |
| Weekly pulse social | `agents/hephae_agents/research/social_pulse.py` |
| Weekly pulse Firestore | `lib/db/hephae_db/firestore/weekly_pulse.py` |
| Weekly pulse admin API | `apps/api/hephae_api/routers/admin/weekly_pulse.py` |
| Pulse cron handler | `apps/api/hephae_api/routers/batch/pulse_cron.py` |
| Registered zipcodes Firestore | `lib/db/hephae_db/firestore/weekly_pulse.py` (same file) |
| Workflow dispatcher | `apps/api/hephae_api/routers/batch/workflow_dispatcher.py` |

---

## What NOT To Do

- Do NOT modify any code. This is read-only investigation.
- Do NOT restart or retry workflows or jobs. Just diagnose.
- Do NOT guess at Firestore data you can't read. Ask the user to run the query.
- Do NOT skip Phase 1 / collection. Always collect actual state before analyzing.
- Do NOT produce findings without evidence. Every finding must have concrete data backing it.
- Do NOT render per-business cards. Compute aggregates instead. Only drill into specific businesses during spot-checks.
- Do NOT exhaustively verify every business. Use 2-3 strategic samples per pattern.
