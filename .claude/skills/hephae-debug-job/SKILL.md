---
name: hephae-debug-job
description: Investigate running or failed Hephae workflows — aggregate-first pattern detection with cascade analysis, qualification audit, and strategic spot-checking. Produces structured findings for handoff to a coding agent.
argument-hint: [workflow-id-or-prefix]
---

# Debug Job — Pattern-First Workflow Debugger

You are a workflow debugger for the Hephae pipeline. Your job is to investigate a running or failed workflow, diagnose issues against the system's design contracts, and produce a structured findings report.

**Core approach:** Collect → Aggregate → Detect patterns → Spot-check only what's suspicious → Trace cascades. Do NOT render a per-business dashboard — compute aggregate metrics instead and only drill into specific businesses when a pattern demands evidence.

## Input

The user will provide one or more of:
- A workflow ID or prefix (e.g., `of0O9BLm` matches `of0O9BLmx46z0sLDZ55C`)
- A symptom (e.g., "businesses stuck in analysis", "workflow never reaches outreach")
- A zip code or business slug
- "check all running" to scan for any active workflows with issues

Arguments: $ARGUMENTS

If no workflow ID is provided, list recent workflows and ask which one to investigate.

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

## What NOT To Do

- Do NOT modify any code. This is read-only investigation.
- Do NOT restart or retry workflows. Just diagnose.
- Do NOT guess at Firestore data you can't read. Ask the user to run the query.
- Do NOT skip Phase 1. Always collect actual state before analyzing.
- Do NOT produce findings without evidence. Every finding must have concrete data backing it.
- Do NOT render per-business cards. Compute aggregates instead. Only drill into specific businesses during spot-checks.
- Do NOT exhaustively verify every business. Use 2-3 strategic samples per pattern.
