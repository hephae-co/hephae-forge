---
name: hephae-debug-discovery
description: Debug batch discovery jobs — check progress, skip reasons, quality gate decisions, and capability execution across zip codes.
argument-hint: [job-id | latest]
---

# Debug Discovery Job

You are a debugger for Hephae batch discovery jobs. Your job is to investigate running or completed discovery jobs, check progress, analyze skip reasons, and identify quality gate or capability execution issues.

**Core approach:** Fetch job → Compute aggregates → Detect patterns → Spot-check suspicious businesses.

## Input

The user provides a discovery job ID, prefix, or "latest". Arguments: $ARGUMENTS

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## DJ-1: COLLECT

### 1a. Resolve Job

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/discovery_jobs?pageSize=20"
```

If "latest", fetch the most recent by `createdAt`. Extract:
- `name`, `status`, `createdAt`, `startedAt`, `completedAt`
- `targets[]` (zipCode + businessTypes per target)
- `progress` (totalZips, completedZips, totalBusinesses, qualified, skipped, failed)
- `settings` (freshnessDiscoveryDays, freshnessAnalysisDays, rateLimitSeconds)
- `skipReasons[]` (sampled list, max 50)
- `error` (if failed)

**Statuses:** `pending` → `running` → `review_required` | `outreach_pending` | `completed` | `failed` | `cancelled`

### 1b. Fetch Affected Businesses

For each target zipCode, query businesses:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"businesses"}],"where":{"fieldFilter":{"field":{"fieldPath":"zipCode"},"op":"EQUAL","value":{"stringValue":"ZIP_CODE"}}},"limit":50}}'
```

### 1c. Cloud Run Job Logs

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="hephae-forge-batch" AND textPayload=~"DiscoveryJobs"' \
  --limit=50 --freshness=8h --format="table(timestamp, severity, textPayload)" \
  --project=$PROJECT
```

---

## DJ-2: AGGREGATES

| Metric | Value |
|--------|-------|
| Job ID / Name | |
| Status | |
| Duration | |
| Targets | {N} zip codes |
| Total Businesses | |
| Qualified | {N} ({%}) |
| Skipped | {N} ({%}) |
| Failed | {N} ({%}) |
| Freshness Settings | discovery={N}d, analysis={N}d |

### Skip Reason Breakdown

Categorize `skipReasons[]`: fresh_discovery, fresh_analysis, quality_gate_rejected, chain_detected, no_contact, other.

---

## DJ-3: PATTERNS

| Rule | Trigger | Severity |
|------|---------|----------|
| High Skip Rate | >60% skipped | HIGH |
| High Failure Rate | >20% failed | HIGH |
| Zero Qualified | qualified=0 | CRITICAL |
| Job Stuck | RUNNING >2h with no progress | HIGH |
| Quality Gate Hallucination | Rejected businesses have websites + contact info | MEDIUM |

---

## DJ-4: SPOT-CHECK (2-3 per pattern)

- **Skipped:** Were they actually analyzed recently?
- **Failed:** Systemic (model 429) or per-business (Playwright timeout)?
- **Quality gate rejects:** Does the business actually have website, contact info, social?

---

## DJ-5: REPORT

Write to `.claude/findings/latest.md`:
```markdown
# Debug Report: Discovery Job {job_id}
Generated: {timestamp}
Job: {name} | Status: {status} | Targets: {N} zips | Duration: {duration}
```

## Key References

| Area | File |
|------|------|
| Discovery job CRUD | `apps/api/hephae_api/routers/admin/discovery_jobs.py` |
| Discovery job Firestore | `lib/db/hephae_db/firestore/discovery_jobs.py` |
| Discovery orchestrator | `apps/api/hephae_api/workflows/scheduled_discovery/orchestrator.py` |
| Quality gate | `apps/api/hephae_api/workflows/scheduled_discovery/quality_gate.py` |
| Capability dispatcher | `apps/api/hephae_api/workflows/scheduled_discovery/dispatcher.py` |
| Batch entrypoint | `apps/batch/hephae_batch/main.py` |
| Job launcher | `apps/api/hephae_api/lib/job_launcher.py` |

## What NOT To Do

- Do NOT modify any code or data. Read-only investigation.
- Do NOT restart or retry jobs. Just diagnose.
- Do NOT guess at Firestore data you can't read.
- Do NOT produce findings without evidence.
