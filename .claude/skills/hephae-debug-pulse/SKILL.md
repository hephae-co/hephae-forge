---
name: hephae-debug-pulse
description: Debug weekly pulse jobs and industry pulses — check signal health, cron status, registered zipcodes, batch work items, and job lifecycle issues.
argument-hint: [pulse | zip-code | industry:{name} | latest]
---

# Debug Pulse

You are a debugger for the Hephae Weekly Pulse system. Covers both zip-level and industry-level pulses, registered zipcodes, cron health, and batch work items.

**Core approach:** Fetch pulse data → Signal health → Detect patterns → Spot-check failures.

**Routing:** If args contain "industry:" → check industry pulses. Otherwise check zip pulses.

## Input

Arguments: $ARGUMENTS

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## WP-1: COLLECT (Parallel)

### 1a. Pulse Jobs

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/pulse_jobs?pageSize=10"
```

Extract: `zipCode`, `businessType`, `weekOf` (ISO: "2026-W12"), `status` (QUEUED/RUNNING/COMPLETED/FAILED), `startedAt`, `completedAt`, `timeoutAt` (15min limit), `error`, `testMode`, `result.pulseId`, `result.insightCount`.

### 1b. Pulse Results

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/zipcode_weekly_pulse?pageSize=10"
```

Extract: doc ID, `zipCode`, `businessType`, `weekOf`, `pulse.headline`, `pulse.insights[]` count, `signalsUsed[]`, `diagnostics` (signalCount, insightCount, critiquePass, critiqueScore, startedAt, completedAt), `pipelineDetails`, `testMode`.

### 1c. Registered Zipcodes

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/registered_zipcodes?pageSize=20"
```

Extract: `zipCode`, `businessType`, `status` (active/paused), `pulseCount`, `lastPulseAt`, `nextScheduledAt`.

### 1d. Industry Pulses (if checking industry layer)

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/industry_pulses?pageSize=10"
```

Extract: `industryKey`, `weekOf`, `nationalSignals`, `nationalImpact`, `nationalPlaybooks`, `trendSummary`, `signalsUsed`, `diagnostics`.

### 1e. Registered Industries

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/registered_industries?pageSize=10"
```

### 1f. Logs

```bash
# Pulse logs
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-forge-api" AND textPayload=~"WeeklyPulse|PulseJob|PulseCron|IndustryPulse"' \
  --limit=40 --freshness=4h --format="table(timestamp, textPayload)" \
  --project=$PROJECT

# Batch logs
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="hephae-forge-batch" AND textPayload=~"PulseBatch|pulse"' \
  --limit=40 --freshness=8h --project=$PROJECT
```

---

## WP-2: AGGREGATES

### Pulse Job Summary

| Metric | Value |
|--------|-------|
| Total Jobs | |
| COMPLETED / FAILED / RUNNING | |
| Test vs Non-Test | |
| Industry Pulses Generated | |
| Registered Industries (active) | |
| Registered Zipcodes (active) | |
| Zips with Stale Pulses (>7d) | |

### Signal Health (per pulse)

| Signal Source | Status | Detail |
|---------------|--------|--------|
| censusDemographics | ok/empty/error/skipped | |
| osmDensity | ok/empty/error/skipped | |
| weather | ok/empty/error/skipped | |
| localNews | ok/empty/error/skipped | |
| trends | ok/empty/error/skipped | |
| blsCpi | ok/empty/error/skipped | |
| fdaRecalls | ok/empty/error/skipped | |
| usdaPrices | ok/empty/error/skipped | |
| (etc.) | | |

---

## WP-3: PATTERNS

| Rule | Trigger | Severity |
|------|---------|----------|
| Low Signal Count | <4 sources OK | HIGH |
| Zero Insights | insightCount=0 despite signals | CRITICAL |
| Critique Failed | critiquePass=false | HIGH |
| Stale Data | prior_pulse empty/skipped | MEDIUM |
| Cross-Signal Hallucination | Insight cites error/skipped source | HIGH |
| Pulse Job Timeout | FAILED + timeoutAt exceeded | HIGH |
| Batch Items Stuck | Work items in intermediate state >10min | HIGH |
| Cron Not Firing | Active zips + lastPulseAt >7d + nextScheduled in past | HIGH |
| All Low Impact | All insights impactScore <50 | LOW |
| Industry Pulse Missing | Zip pulse ran but no industry pulse for this week | HIGH |

---

## WP-4: SPOT-CHECK

- **Failed signals:** Check API key config, try external API manually
- **Hallucinated insights:** Cross-ref signalSources vs diagnostics.sources
- **Pipeline failures:** Read pipelineDetails — which intermediate outputs exist?
- **Cron issues:** Check `gcloud scheduler jobs list`

---

## WP-5: REPORT

Write to `.claude/findings/latest.md`:
```markdown
# Debug Report: Weekly Pulse
Generated: {timestamp}
Scope: {zip/industry/all}
```

## Key References

| Area | File |
|------|------|
| Pulse orchestrator | `apps/api/hephae_api/workflows/orchestrators/weekly_pulse.py` |
| Signal fetching | `apps/api/hephae_api/workflows/orchestrators/pulse_fetch_tools.py` |
| Playbooks | `apps/api/hephae_api/workflows/orchestrators/pulse_playbooks.py` |
| Industry configs | `apps/api/hephae_api/workflows/orchestrators/industries.py` |
| Industry pulse generator | `apps/api/hephae_api/workflows/orchestrators/industry_pulse.py` |
| Pulse Firestore | `lib/db/hephae_db/firestore/weekly_pulse.py` |
| Industry pulse Firestore | `lib/db/hephae_db/firestore/industry_pulse.py` |
| Pulse cron | `apps/api/hephae_api/routers/batch/pulse_cron.py` |
| Industry pulse cron | `apps/api/hephae_api/routers/batch/industry_pulse_cron.py` |
| Registered industries | `lib/db/hephae_db/firestore/registered_industries.py` |

## What NOT To Do

- Do NOT modify code or data. Read-only investigation.
- Do NOT restart or trigger pulses. Just diagnose.
- Do NOT flag event_traffic_modifier=0 with events in briefing — different data sources.
- Do NOT flag 20-35min duration as slow for cron batches — this is normal.
- Do NOT assume signal archive has raw data — check first, fall back to pipelineDetails.
