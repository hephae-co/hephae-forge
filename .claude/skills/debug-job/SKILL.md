---
name: debug-job
description: Investigate running or failed Hephae workflows — checks phase integrity, business state, capability execution, evaluation standards, model fallback health, and database rules against design contracts. Produces structured findings for handoff to a coding agent.
argument-hint: [workflow-id-or-prefix]
---

# Debug Job — Hephae Workflow Investigator

You are a workflow debugger for the Hephae pipeline. Your job is to investigate a running or failed workflow, diagnose issues against the system's design contracts, and produce a structured findings report. Unlike a simple status check, you perform **deep verification** — checking whether discovered data is accurate, whether businesses that were parked actually lack what was claimed, and whether capability results make sense.

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
```

Firestore base URL: `https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents`

---

## PHASE 1: Collect Complete State

This phase gathers ALL raw data needed for analysis. Run as many queries in parallel as possible.

### 1a. Resolve Workflow

If the user gave a partial ID, list workflows and find the match:
```bash
# List workflows
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows?pageSize=20" | python3 -c "..."
```

Fetch the full workflow document. Parse it to extract:
- `phase`, `createdAt`, `updatedAt`, `zipCode`, `businessType`, `retryCount`, `lastError`
- `progress.*` counters
- Full `businesses[]` array with ALL fields per business

### 1b. Fetch ALL Business Documents

For EVERY business in the workflow (not just qualified ones), fetch the separate Firestore document at `businesses/{slug}`. This is critical because:
- The workflow `businesses[]` array has workflow-phase state
- The separate `businesses/{slug}` document has enrichment data, latestOutputs, identity, etc.
- Discrepancies between these two sources are a finding

```bash
TOKEN=$(gcloud auth print-access-token)
for slug in {all-slugs}; do
  curl -s -H "Authorization: Bearer $TOKEN" \
    "$FIRESTORE_BASE/businesses/$slug"
done
```

Extract from each business doc:
- `officialUrl`, `phone`, `email`, `emailStatus`, `contactFormUrl`, `contactFormStatus`
- `socialLinks.*` (instagram, facebook, twitter, yelp, tiktok, etc.)
- `hours`, `googleMapsUrl`, `menuUrl`
- `logoUrl`, `favicon`, `primaryColor`, `secondaryColor`
- `persona`
- `competitors[]`
- `news[]`
- `latestOutputs.*` (keys + scores + reportUrls)
- `identity.*` (the full enriched profile mirror)
- `crm.*` (if present)

### 1c. Fetch Task Documents

Query tasks by workflow ID to get execution metadata:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"tasks"}],"where":{"fieldFilter":{"field":{"fieldPath":"metadata.workflowId"},"op":"EQUAL","value":{"stringValue":"WORKFLOW_ID"}}},"limit":50}}'
```

Extract per task: `businessId`, `status`, `substep`, `createdAt`, `startedAt`, `completedAt`, `error`, and metadata fields (`capabilitiesCompleted`, `capabilitiesFailed`, `capabilitiesSkipped`).

### 1d. Cloud Run Logs

```bash
# Recent API errors
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-api" AND severity>=ERROR' \
  --limit=50 --freshness=2h --format="table(timestamp, jsonPayload.message, textPayload)" \
  --project=$PROJECT

# Rate limiting
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"429|Resource exhausted|rate.limit"' \
  --limit=20 --freshness=1h --project=$PROJECT

# Model fallback events
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"ModelFallback|fallback"' \
  --limit=20 --freshness=2h --project=$PROJECT
```

If gcloud or curl commands fail, tell the user what to run and ask for the output. Never guess at data you can't read.

---

## PHASE 2: Render Complete Business Dashboard

Before any analysis, output a **comprehensive dashboard** of every business. This gives the user complete visibility into what the pipeline found.

### 2a. Business Summary Table

Output a table like this for ALL businesses:
```
| # | Business | Phase | URL | Phone | Email | Contact Form | Caps Done | Eval Score | Error |
|---|----------|-------|-----|-------|-------|--------------|-----------|------------|-------|
```

### 2b. Detailed Business Cards

For each business, output a detailed card:
```
### {name} ({slug})
- **Phase:** {workflow phase} | **Quality:** {passed/failed/pending}
- **Address:** {address}
- **Website:** {officialUrl or "NOT FOUND"}
- **Phone:** {phone or "NOT FOUND"} | **Email:** {email or "NOT FOUND"}
- **Contact Form:** {contactFormUrl or "NOT FOUND"} (status: {contactFormStatus})
- **Social Links:** {list all found: instagram, facebook, etc.}
- **Menu URL:** {menuUrl or "NOT FOUND"}
- **Google Maps:** {googleMapsUrl or "NOT FOUND"}
- **Hours:** {hours or "NOT FOUND"}
- **Competitors Found:** {count and names}
- **Capabilities Completed:** {list with scores from latestOutputs}
  - SEO: score={X}, reportUrl={url}
  - Traffic: score={X}
  - etc.
- **Evaluation Results:** {per-capability: score, hallucinated, issues}
- **Last Error:** {lastError if any}
- **Task Status:** {status} started={time} completed={time} duration={X}
```

### 2c. Cross-Reference Workflow vs Business Doc

Flag any differences between the workflow `businesses[]` state and the actual `businesses/{slug}` document:
- `officialUrl` mismatch
- `capabilitiesCompleted` count mismatch (workflow vs task metadata)
- `latestOutputs` keys present on doc but not reflected in workflow caps

---

## PHASE 3: Discovery & Enrichment Accuracy Verification

This is the critical NEW phase. For businesses that were parked or show missing data, verify whether the data really is missing by checking URLs directly.

### 3a. Verify "No Website" Claims

For every business where `officialUrl` is empty and `lastError` contains "No website":
1. **Use WebSearch** to search for `"{business name}" {city} {state} website`
2. **Use WebFetch** to check common URL patterns:
   - `https://{slugified-name}.com`
   - `https://www.{slugified-name}.com`
   - Any URLs returned by WebSearch
3. Report whether a website actually exists

**This catches cases like:**
- Queen Margherita Trattoria → actually has https://qmargherita.com
- Sugar Tree Café → actually has https://sugartreecafe.com

### 3b. Verify "No Contact" Claims

For businesses that have a website but no `contactFormUrl`:
1. **Use WebFetch** on `{officialUrl}/contact`, `{officialUrl}/contact-us`, `{officialUrl}/about`
2. Check if these pages exist (HTTP 200) and contain form elements or contact info
3. For businesses that supposedly have no phone/email, check the website content

### 3c. Check Website Reachability

For businesses WITH a website URL:
1. **Use WebFetch** to verify the URL actually loads
2. Flag if the URL redirects to a generic domain registrar/parked page
3. Flag if the URL returns 404 or connection error
4. This validates whether the qualification score was reasonable

### 3d. Qualification Decision Audit

The quality gate agent generates "Parked" messages at runtime. These are AI-generated decisions, not hard-coded rules. Audit them:
- Business says "Parked: No website URL" but has `officialUrl` set → qualification bug
- Business says "Parked: Score X close to threshold Y" → check if the score is reasonable given the actual data
- Business was qualified but has very thin data → wasted compute
- Business was disqualified but has a real website + contact info → missed opportunity

Cross-reference: The quality gate checks for chains, no contact, permanently closed, insufficient data. Verify these match the actual business data.

---

## PHASE 4: Workflow & Capability Analysis

### 4a. Workflow Phase Integrity

**Expected phase transitions** (strictly sequential):
```
DISCOVERY → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH → COMPLETED
```

**Check for:**
- Phase skipping (went from DISCOVERY directly to ANALYSIS)
- Stuck too long (DISCOVERY: >5 min, QUALIFICATION: >3 min, ANALYSIS: >40 min, EVALUATION: >10 min)
- FAILED with no `lastError`
- COMPLETED but progress counters inconsistent

### 4b. Business Phase Integrity

**Expected transitions:**
```
PENDING → ENRICHING → ANALYZING → ANALYSIS_DONE → EVALUATING → EVALUATION_DONE → APPROVED → OUTREACHING → OUTREACH_DONE
```
Terminal: `REJECTED`, `OUTREACH_FAILED`

**Check for:**
- Business stuck in `ENRICHING` or `ANALYZING` >10 min (STUCK_TASK_THRESHOLD)
- `ANALYSIS_DONE` with both `capabilitiesCompleted` and `capabilitiesFailed` empty AND no `lastError` (no work done, no explanation)
- `EVALUATION_DONE` with `qualityPassed=true` but evaluation scores <80 or `isHallucinated=true`
- Phase mismatch between workflow state and task status (task completed but workflow still shows ENRICHING)

### 4c. Capability Execution Audit

**Expected per business:**
| Capability | Requires | Firestore Key |
|---|---|---|
| `seo` | `officialUrl` must exist | `seo_auditor` |
| `traffic` | always runs | `traffic_forecaster` |
| `competitive` | `competitors[]` non-empty | `competitive_analyzer` |
| `margin_surgeon` | `menuScreenshotBase64` must exist | `margin_surgeon` |
| `social` | always runs | `social_media_auditor` |

**Check for:**
- Capability ran but business lacks required data (wasted compute)
- Capability didn't run but business HAS required data (missed analysis)
- Capabilities in task metadata but NOT in workflow `capabilitiesCompleted` (sync gap — known issue with polling race condition)
- `latestOutputs` missing on business doc for completed capabilities
- `reportUrl` is null for capabilities that should generate reports (all except social)
- `agentVersion` mismatch with current `AgentVersions` in config.py

### 4d. Evaluation Standards Audit

**Pass threshold:** `score >= 80 AND isHallucinated == false`

**Check for:**
- `qualityPassed=true` but one or more evaluations failed threshold
- Evaluation ran but result not recorded on business
- Evaluation skipped for a completed capability
- ALL businesses failing evaluation (100% failure = systemic issue, investigate WHY)
  - If traffic evaluations all flag hallucination → check if weather/event data is being ignored
  - If SEO evaluations all fail → check if PageSpeed API is rate-limited
  - If scores are all 0 → evaluator agent may be crashing (check for "Failed to parse evaluator output")

### 4e. Database Rules

1. **No blobs in Firestore** — check for base64 data in any field (especially `menuScreenshotBase64`)
2. **`zipCode` is first-class** — verify it's a top-level field on business docs
3. **No growing arrays** — check for `reports[]`, `analyses[]` on business docs
4. **`update()` with dotted paths** — check logs for `set()` warnings

### 4f. Model Fallback Health

Check logs for:
- `[ModelFallback]` entries — count in last hour
- Double failures (fallback model also failing)
- `response_mime_type` / `response_schema` stripping warnings
- Agent timeout without fallback attempt

### 4g. Task Execution Timing

For each task, compute:
- Queue wait time: `startedAt - createdAt`
- Execution time: `completedAt - startedAt`
- Total time: `completedAt - createdAt`

Flag:
- Tasks waiting >5 min in queue (Cloud Tasks backlog)
- Tasks executing >10 min (potential stuck agent)
- Serial execution pattern (each task starts exactly when previous ends = concurrency=1)
- Tasks that hit 40-min polling timeout
- Tasks stuck >10 min without substep change

---

## PHASE 5: Continuous Monitoring (if workflow is active)

If the workflow is NOT in a terminal phase (COMPLETED, FAILED, APPROVAL), enter a monitoring loop:

1. **Re-poll the workflow document** every 30 seconds
2. **Detect new phase transitions** since the last poll
3. **Report progress** changes (new businesses completing analysis, new evaluations, etc.)
4. **Accumulate findings** — new issues discovered during monitoring are appended to the findings report
5. **Detect stalls** — if `updatedAt` hasn't changed in >5 minutes, flag it
6. **Exit conditions:**
   - Workflow reaches COMPLETED, FAILED, or APPROVAL phase
   - User interrupts
   - 60 minutes elapsed (safety valve)

During monitoring, periodically re-check tasks for newly completed businesses and update the dashboard.

Use tasks to track the monitoring state and output updates to the user as they happen.

---

## PHASE 6: Produce Findings Report

Write findings to `.claude/findings/latest.md` in this format:

```markdown
# Debug Report: {workflow_id}
Generated: {ISO timestamp}
Zip Code: {zip}
Business Type: {type}
Workflow Phase: {current phase}
Duration: {createdAt → updatedAt}
Businesses: {total} total, {qualified} qualified, {parked} parked, {analysis_done} analyzed, {eval_done} evaluated, {quality_passed} passed, {quality_failed} failed

## Business Dashboard
{summary table from Phase 2a}

## FINDING-{N}: {title} [{CRITICAL|HIGH|MEDIUM|LOW}]
- **Symptom:** {what you observed}
- **Category:** {discovery_accuracy | enrichment_gap | phase_integrity | capability_execution | evaluation_quality | data_rule | model_health | timing}
- **Businesses Affected:** {list of slugs or "all"}
- **File:** {exact file path}:{line number if known}
- **Expected:** {what should happen, citing contract}
- **Actual:** {what actually happened}
- **Evidence:** {concrete data — URLs checked, field values, timestamps, log snippets}
- **Fix direction:** {specific guidance}
- **Impact:** {what breaks if not fixed}
```

### Severity Levels
- **CRITICAL** = Discovery data is wrong, causing businesses to be incorrectly parked/skipped (directly reduces pipeline coverage)
- **HIGH** = Workflow blocked, data corruption, or systemic quality failure (100% eval failure)
- **MEDIUM** = Degraded quality, wasted compute, data sync issues
- **LOW** = Cosmetic, minor inefficiency, or non-blocking issue

### Findings Categories
- `discovery_accuracy` — Business has data that discovery didn't find (website exists but wasn't discovered)
- `enrichment_gap` — Enrichment ran but missed data that exists (contact form, social links)
- `phase_integrity` — Workflow or business phase transition violation
- `capability_execution` — Capability should have run but didn't, or vice versa
- `evaluation_quality` — Systemic evaluation failure, threshold issues
- `data_rule` — Firestore/BigQuery contract violation
- `model_health` — Rate limiting, fallback cascades, agent crashes
- `timing` — Tasks too slow, stuck, or queued too long

Sort findings: CRITICAL → HIGH → MEDIUM → LOW.

Also output the full findings summary to the conversation so the user can read it immediately.

---

## PHASE 7: Recurring Pattern Detection

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

## Key Codebase References

These files are most relevant for mapping findings to fixes:

| Area | File |
|------|------|
| Analysis orchestrator + polling | `apps/api/backend/workflows/phases/analysis.py` |
| Task handler (enrichment + capabilities) | `apps/api/backend/routers/admin/tasks.py` |
| Enrichment + website finding | `apps/api/backend/workflows/phases/enrichment.py` |
| Discovery runner (2-phase) | `packages/capabilities/hephae_capabilities/discovery/runner.py` |
| Quality gate agent | `apps/api/backend/workflows/scheduled_discovery/quality_gate.py` |
| Evaluation phase | `apps/api/backend/workflows/phases/evaluation.py` |
| Capability registry + should_run | `apps/api/backend/workflows/capabilities/registry.py` |
| Workflow engine + checkpointing | `apps/api/backend/workflows/engine.py` |
| Workflow Firestore I/O | `packages/db/hephae_db/firestore/workflows.py` |
| Business Firestore I/O | `packages/db/hephae_db/firestore/businesses.py` |
| Agent versions config | `apps/api/backend/config.py` |
| Type definitions | `apps/api/backend/types.py` |

## What NOT To Do

- Do NOT modify any code. This is read-only investigation.
- Do NOT restart or retry workflows. Just diagnose.
- Do NOT guess at Firestore data you can't read. Ask the user to run the query.
- Do NOT skip Phase 1. Always collect actual state before analyzing.
- Do NOT produce findings without evidence. Every finding must have concrete data backing it.
- Do NOT skip Phase 3 (verification). The most valuable findings come from checking whether "No website" claims are actually true.
