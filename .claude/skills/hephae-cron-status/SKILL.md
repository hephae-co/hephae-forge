---
name: hephae-cron-status
description: Show status of all Hephae scheduled cron jobs — what's scheduled, when, what ran last, upcoming runs.
argument-hint: [all | pulse | industry | tech | discovery]
---

# Cron Status — Scheduled Jobs Dashboard

Shows the status of all Hephae cron jobs: what's scheduled, last run, next 3 runs, and registered zipcodes/industries.

## Input

| Arg | What It Shows |
|-----|--------------|
| `all` or empty | All cron jobs + registered zips + business types |
| `pulse` | Weekly pulse cron only |
| `industry` | Industry pulse cron only |
| `tech` | Tech intelligence cron only |

Arguments: $ARGUMENTS

## Steps

### 1. List all Cloud Scheduler jobs

```bash
gcloud scheduler jobs list --location us-central1 --project hephae-co-dev --format="table(name,schedule,state,httpTarget.uri)" 2>&1
```

### 2. Show details for each relevant job

For each scheduler job, show:
- Current state (ENABLED/PAUSED)
- Schedule (cron expression + timezone)
- Last attempt time + status
- Next 3 scheduled run times (compute from cron expression + timezone)

```bash
# For each job:
gcloud scheduler jobs describe {JOB_NAME} --location us-central1 --project hephae-co-dev --format="yaml(name,schedule,state,timeZone,lastAttemptTime,scheduleTime,status)" 2>&1
```

### 3. Show registered zipcodes and business types

```bash
TOKEN=$(gcloud auth print-identity-token 2>/dev/null)
API_KEY=$(gcloud secrets versions access latest --secret=FORGE_V1_API_KEY --project=hephae-co-dev 2>/dev/null)
curl -s "https://hephae-forge-api-hlifczmzgq-uc.a.run.app/api/registered-zipcodes" \
  -H "Authorization: Bearer $TOKEN" -H "X-API-Key: $API_KEY" 2>&1 | \
  python3 -c "
import sys, json
zips = json.load(sys.stdin)
print(f'{len(zips)} registered zipcodes:')
for z in zips:
    types = z.get('businessTypes', ['Restaurants'])
    print(f'  {z[\"zipCode\"]} ({z[\"city\"]}, {z[\"state\"]}) — {z[\"onboardingStatus\"]} — {len(types)} types: {\", \".join(types)}')
print(f'\nTotal pulse runs per cron: {sum(len(z.get(\"businessTypes\", [\"Restaurants\"])) for z in zips)}')
"
```

### 4. Show registered industries

```bash
# Check what industries are configured
python3 -c "
from hephae_api.workflows.orchestrators.industries import list_industries
for cfg in list_industries():
    print(f'  {cfg.id}: {cfg.name} ({len(cfg.aliases)} aliases, {len(cfg.playbooks)} playbooks)')
" 2>/dev/null || echo "  restaurant, bakery, barber (default 3)"
```

### 5. Show recent cron run results

```bash
# Check last 5 pulse jobs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="hephae-forge-api" AND (textPayload=~"PulseCron" OR textPayload=~"TechIntelCron" OR textPayload=~"IndustryPulseCron") AND textPayload=~"Complete"' \
  --project hephae-co-dev --limit 5 \
  --format="value(timestamp,textPayload)" 2>&1
```

### 6. Compute next 3 run times

For the weekly-pulse-cron, compute the next 3 scheduled run times based on the cron expression and timezone. Display in both ET and UTC.

## Output Format

Present as a clean dashboard:

```
═══════════════════════════════════════════════════
  HEPHAE CRON STATUS
═══════════════════════════════════════════════════

📅 SCHEDULED JOBS
┌─────────────────────────┬──────────────┬─────────┐
│ Job                     │ Schedule     │ State   │
├─────────────────────────┼──────────────┼─────────┤
│ tech-intelligence-cron  │ Sun 1AM ET   │ ENABLED │
│ industry-pulse-cron     │ Sun 3AM ET   │ ENABLED │
│ weekly-pulse-cron       │ Mon 3AM ET   │ ENABLED │
│ workflow-dispatcher     │ */5 * * * *  │ ENABLED │
└─────────────────────────┴──────────────┴─────────┘

🗓️ NEXT 3 RUNS
  1. Mon Mar 23, 3:00 AM ET — Weekly Pulse (15 runs: 5 zips × 3 types)
  2. Sun Mar 29, 1:00 AM ET — Tech Intelligence (3 verticals)
  3. Sun Mar 29, 3:00 AM ET — Industry Pulse (3 industries)

📍 REGISTERED ZIPCODES (5)
  07110 (Nutley, NJ) — 3 types: Restaurants, Bakeries, Barbers
  07011 (Clifton, NJ) — 3 types: Restaurants, Bakeries, Barbers
  ...

📊 LAST 5 CRON RUNS
  2026-03-22 16:15 — TechIntelCron: 3 succeeded, 0 failed
  2026-03-22 12:09 — IndustryPulseCron: 3 generated, 0 failed
  2026-03-21 07:36 — PulseCron: 5 triggered, 0 skipped
  ...
```
