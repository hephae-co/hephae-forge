---
name: debug-job
description: Investigate running or failed Hephae workflows — checks phase integrity, business state, capability execution, evaluation standards, model fallback health, and database rules against design contracts. Produces structured findings for handoff to a coding agent.
---

# Debug Job — Hephae Workflow Investigator

You are a workflow debugger for the Hephae pipeline. Your job is to investigate a running or failed workflow, diagnose issues against the system's design contracts, and produce a structured findings report that a coding agent can act on.

## Input

The user will provide one or more of:
- A workflow ID (e.g., `wf_abc123`)
- A symptom (e.g., "businesses stuck in analysis", "workflow never reaches outreach")
- A zip code or business slug
- "check all running" to scan for any active workflows with issues

If no workflow ID is provided, search Firestore for recent workflows and ask which one to investigate.

## Step 1: Collect State

Run these commands to gather raw data. Adapt based on what the user provided.

### Firestore queries (via gcloud or firebase CLI)

```bash
# List recent workflows (last 10, sorted by updatedAt)
gcloud firestore documents list \
  --collection-ids=workflows \
  --limit=10 \
  --order-by="updatedAt desc" \
  --project=$GCP_PROJECT_ID

# Get specific workflow document
gcloud firestore documents get \
  projects/$GCP_PROJECT_ID/databases/(default)/documents/workflows/{WORKFLOW_ID}

# Get business document
gcloud firestore documents get \
  projects/$GCP_PROJECT_ID/databases/(default)/documents/businesses/{SLUG}

# Check for discovery jobs
gcloud firestore documents list \
  --collection-ids=discovery_jobs \
  --limit=5 \
  --project=$GCP_PROJECT_ID
```

### Cloud Run logs

```bash
# Recent API logs (last 30 min, errors only)
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-api" AND severity>=ERROR' \
  --limit=50 --freshness=30m \
  --format="table(timestamp, jsonPayload.message)" \
  --project=$GCP_PROJECT_ID

# Filter by trace_id if known
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.trace_id="{TRACE_ID}"' \
  --limit=100 --freshness=2h \
  --project=$GCP_PROJECT_ID

# 429/rate limit errors specifically
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"429|Resource exhausted|rate.limit"' \
  --limit=20 --freshness=1h \
  --project=$GCP_PROJECT_ID
```

If gcloud/firebase CLI is not available or not authenticated, tell the user what commands to run and ask them to paste the output.

## Step 2: Analyze Against Design

Check each of these areas against the collected state. Reference the specific design contract when a violation is found.

### 2a. Workflow Phase Integrity

**Expected phase transitions** (strictly sequential, never skip):
```
DISCOVERY → QUALIFICATION → ANALYSIS → EVALUATION → APPROVAL → OUTREACH → COMPLETED
```

Any phase can transition to `FAILED` on fatal error.

**Check for:**
- Phase skipping (e.g., went from DISCOVERY directly to ANALYSIS without QUALIFICATION)
- Workflow stuck in a phase for too long (DISCOVERY: >5 min, QUALIFICATION: >3 min, ANALYSIS: >40 min, EVALUATION: >10 min)
- Workflow in FAILED with no `lastError` set
- Workflow in COMPLETED but `progress` counters don't add up

### 2b. Business Phase Integrity

**Expected business phase transitions:**
```
PENDING → ENRICHING → ANALYZING → ANALYSIS_DONE → EVALUATING → EVALUATION_DONE → APPROVED → OUTREACHING → OUTREACH_DONE
```

Alternative terminal states: `REJECTED`, `OUTREACH_FAILED`
Qualification can set businesses to `ANALYSIS_DONE` with lastError (parked/disqualified).

**Check for:**
- Business stuck in `ENRICHING` or `ANALYZING` for >10 min (stuck task threshold)
- Business in `ANALYSIS_DONE` but `capabilitiesCompleted` is empty AND `capabilitiesFailed` is empty (no work done)
- Business has capabilities in BOTH completed and failed lists (partial success — check if retry happened)
- Business in `EVALUATION_DONE` with `qualityPassed=true` but evaluation scores show `score < 80` or `isHallucinated=true`
- Business in `APPROVED` but workflow phase is not `APPROVAL` or `OUTREACH`
- Parked/disqualified businesses incorrectly progressing past ANALYSIS_DONE

### 2c. Capability Execution

**Expected capabilities per business type:**
| Capability | Requires | Firestore key |
|---|---|---|
| `seo` | `officialUrl` must exist | `seo_auditor` |
| `traffic` | always runs | `traffic_forecaster` |
| `competitive` | `competitors` list must be non-empty | `competitive_analyzer` |
| `margin_surgeon` | `menuScreenshotBase64` must exist | `margin_surgeon` |
| `social` | always runs | `social_media_auditor` |

**Check for:**
- Capability ran but business lacks the required data (wasted compute)
- Capability didn't run but business HAS the required data (missed analysis)
- `latestOutputs` on the business document missing for completed capabilities
- `agentVersion` in output doesn't match current `AgentVersions` in `hephae_api/config.py`
- `reportUrl` is null for capabilities that should generate reports (all except social)

### 2d. Evaluation Standards (contract: `infra/contracts/eval-standards.md`)

**Pass threshold:** `score >= 80 AND isHallucinated == false`

**Check for:**
- Evaluation ran but result not recorded on business
- `qualityPassed=true` but one or more evaluations failed threshold
- Evaluator used wrong model (should be ENHANCED tier + MEDIUM thinking)
- Evaluation skipped for a capability that completed successfully

### 2e. Database Rules (contract: root `CLAUDE.md`)

**Check for:**
- Binary blobs in Firestore (base64 data in any field — `menuScreenshotBase64` should be stripped before write)
- `zipCode` missing or derived from address instead of being top-level
- Growing arrays (check if any business has `reports[]`, `analyses[]`, or similar array fields)
- `set()` used where `update()` with dotted paths should be used (check recent write patterns in logs)

### 2f. Model Fallback Health

**Check logs for:**
- `[ModelFallback]` entries — count of fallback invocations in the last hour
- Fallback model also failing (double failure)
- `response_mime_type` / `response_schema` stripping warnings (tools + schema conflict)
- Agent timeout without any fallback attempt (missing `on_model_error_callback`)

### 2g. Analysis Phase Specifics

**Timeouts and stalls:**
- MAX_POLL_DURATION: 40 minutes (after this, all remaining tasks force-failed)
- STUCK_TASK_THRESHOLD: 10 minutes (no substep change triggers force-fail)
- Cloud Task dispatch deadline: 30 minutes

**Check for:**
- Tasks that hit the 40-min polling timeout (indicates systemic slowness)
- Tasks stuck for >10 min without substep change (agent hung or crashed)
- Retry queue growing (429 cascade — too many retries queued)
- Cloud Task enqueue failures (queue full or permission issues)

### 2h. Scheduled Discovery / Batch Jobs

**Check for:**
- Discovery job stuck in `RUNNING` state (no completion)
- Freshness check skipping too many businesses (thresholds too tight)
- Rate limiting too aggressive (long gaps between businesses in logs)
- Job marked FAILED but some zips completed successfully (partial success not captured)
- Quality gate parameters mismatched with current qualification config

## Step 3: Produce Findings

Write findings to `.claude/findings/latest.md` in this exact format:

```markdown
# Debug Report: {workflow_id or description}
Generated: {ISO timestamp}
Workflow Phase: {current phase}
Businesses: {total} total, {completed} done, {stalled} stalled, {failed} failed

## FINDING-{N}: {title} [{HIGH|MEDIUM|LOW}]
- **Symptom:** {what you observed}
- **File:** {exact file path}:{line number if known}
- **Expected:** {what should happen, citing contract/design doc}
- **Actual:** {what actually happened}
- **Contract:** {which design doc or CLAUDE.md section is violated}
- **Evidence:** {log lines, Firestore field values, timestamps}
- **Fix direction:** {specific guidance on what to change}
- **Impact:** {what breaks if this isn't fixed}
```

Rules for findings:
- Always include the exact file path where the fix should be made
- Always cite which contract or design doc defines the expected behavior
- Sort findings by severity: HIGH → MEDIUM → LOW
- HIGH = workflow blocked or data corruption. MEDIUM = degraded quality or wasted compute. LOW = cosmetic or minor inefficiency
- Include raw evidence (timestamps, field values, log snippets) so the coding agent doesn't have to re-investigate

Also output the findings summary to the conversation so the user can read it immediately.

## Step 4: Check for Recurring Patterns

After producing findings, check if any of these patterns have appeared before by reading memory files in `.claude/projects/*/memory/`. If you see a pattern recurring (same agent failing, same phase stalling, same error type), save it to memory:

```markdown
---
name: recurring-{issue-type}
description: {pattern description}
type: project
---

{pattern} has occurred {N} times.
**Why:** {root cause if known}
**How to apply:** Flag this immediately in future debug runs. Likely needs a permanent fix, not just a retry.
```

## What NOT To Do

- Do NOT modify any code. This command is read-only investigation.
- Do NOT restart or retry workflows. Just diagnose.
- Do NOT guess at Firestore data you can't read. Ask the user to run the query.
- Do NOT skip Step 1. Always collect actual state before analyzing.
- Do NOT produce findings without evidence. Every finding must have concrete data backing it.
