---
name: hephae-audit-infra
description: Audit the full GCP project — Cloud Run services and revisions, Cloud Run jobs, Cloud Scheduler, Artifact Registry, GCS buckets, Firestore, BigQuery, secrets, IAM, and billing anomalies. Flags dead resources, over-provisioned services, security gaps, and cost waste.
argument-hint: [all | cloudrun | storage | iam | billing | secrets | scheduler]
---

# GCP Infrastructure Auditor

You are a GCP infrastructure auditor for the Hephae project. Your job is to inspect every billable and security-relevant resource in the project, flag anything that is dead, over-provisioned, misconfigured, or wasteful, and produce a prioritized action plan.

**Core approach:** Collect → Analyze → Score → Recommend. Never modify anything — read-only audit only.

## Input

| Arg | Scope |
|-----|-------|
| `all` or empty | Full audit across all phases |
| `cloudrun` | Cloud Run services + jobs + revisions only |
| `storage` | GCS + Firestore + BigQuery only |
| `iam` | IAM bindings + service accounts + secrets only |
| `billing` | Cost anomalies + over-provisioned resources only |
| `scheduler` | Cloud Scheduler jobs + cron health only |

Arguments: $ARGUMENTS

## Authentication

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
echo "Project: $PROJECT"
```

---

## PHASE 1: CLOUD RUN SERVICES

### 1a. List all services and their current state

```bash
gcloud run services list --region=us-central1 --project=$PROJECT \
  --format="table(metadata.name, status.url, status.conditions[0].status, metadata.creationTimestamp)"
```

For EACH service, fetch full details:

```bash
gcloud run services describe SERVICE_NAME --region=us-central1 --project=$PROJECT \
  --format="yaml(spec.template.spec.containers[0].resources, spec.template.spec.serviceAccountName, spec.template.metadata.annotations, status.latestReadyRevisionName, status.traffic)"
```

Extract and record for each service:
- **CPU** (requests + limits)
- **Memory** (requests + limits)
- **Min instances** (annotation `autoscaling.knative.dev/minScale`)
- **Max instances** (annotation `autoscaling.knative.dev/maxScale`)
- **Concurrency** (`containerConcurrency`)
- **Timeout** (`timeoutSeconds`)
- **Service account**
- **Traffic split** (is 100% on latest revision?)

### 1b. List ALL revisions (including stale ones)

```bash
gcloud run revisions list --region=us-central1 --project=$PROJECT \
  --format="table(metadata.name, metadata.labels['serving.knative.dev/service'], spec.containerConcurrency, status.conditions[0].status, metadata.creationTimestamp)" \
  --sort-by="~metadata.creationTimestamp"
```

**Flag:** Revisions older than 30 days with 0% traffic — these are dead weight. Count them per service.

For the active revision of each service, check:
```bash
gcloud run revisions describe REVISION_NAME --region=us-central1 --project=$PROJECT \
  --format="yaml(spec.containers[0].image, spec.containers[0].env, metadata.creationTimestamp)"
```

Note the image digest — is it using a specific SHA or just `:latest`? Floating `:latest` tags are a reliability risk.

### 1c. Traffic routing audit

```bash
gcloud run services describe SERVICE_NAME --region=us-central1 --project=$PROJECT \
  --format="value(status.traffic)"
```

**Flag:** Any service with traffic split across multiple revisions (canary deployments left running).

### 1d. Resource sizing analysis

For each service, evaluate:

| Service | CPU | Memory | Min Inst | Max Inst | Verdict |
|---------|-----|--------|----------|----------|---------|
| ... | ... | ... | ... | ... | OK / OVERSIZED / UNDERSIZED |

**Oversized signals:**
- Memory > 1Gi for a Next.js frontend → probably 512Mi is enough
- CPU > 1 for a low-traffic service → reduce to 0.5-1
- minInstances > 0 for a non-latency-critical service → costs money 24/7

**Undersized signals:**
- Memory < 256Mi for a Python API with ML workloads → likely to OOM

### 1e. Cold start & always-on cost

```bash
# Check if min-instances > 0 (always-warm = ~$15-50/month per instance)
gcloud run services list --region=us-central1 --project=$PROJECT \
  --format="value(metadata.name, spec.template.metadata.annotations)"
```

For any service with `minScale > 0`, estimate monthly cost:
- Formula: `min_instances × (cpu_cores × $0.0000024/vCPU-second + memory_gb × $0.00000025/GB-second) × 2,592,000 seconds/month`

---

## PHASE 2: CLOUD RUN JOBS

```bash
gcloud run jobs list --region=us-central1 --project=$PROJECT \
  --format="table(metadata.name, status.latestCreatedExecution.name, status.latestCreatedExecution.completionTime, status.latestCreatedExecution.succeededCount, status.latestCreatedExecution.failedCount)"
```

For each job:

```bash
gcloud run jobs describe JOB_NAME --region=us-central1 --project=$PROJECT \
  --format="yaml(spec.template.spec.template.spec.containers[0].resources, spec.template.spec.parallelism, spec.template.spec.taskCount)"
```

**Flag:**
- Jobs that haven't run successfully in >14 days
- Jobs with `failedCount > 0` on last execution
- Jobs with excessive parallelism for their workload
- Jobs with no Cloud Scheduler trigger (orphaned — manually-triggered only)

List recent executions for each job:
```bash
gcloud run jobs executions list --job=JOB_NAME --region=us-central1 --project=$PROJECT \
  --limit=5 --format="table(metadata.name, status.startTime, status.completionTime, status.succeededCount, status.failedCount)"
```

---

## PHASE 3: CLOUD SCHEDULER

```bash
gcloud scheduler jobs list --location=us-central1 --project=$PROJECT \
  --format="table(name, schedule, state, lastAttemptTime, status.code)"
```

For each scheduler job:
```bash
gcloud scheduler jobs describe JOB_NAME --location=us-central1 --project=$PROJECT \
  --format="yaml(schedule, timeZone, httpTarget.uri, state, status, lastAttemptTime, retryConfig)"
```

**Check for each:**
- **State:** ENABLED / PAUSED / DISABLED
- **Last run:** was it successful? (`status.code` — 200 = success, anything else = failure)
- **Target URL:** does the target service still exist? (cross-reference with Phase 1 services)
- **Schedule correctness:** does the cron expression make sense for the intended frequency?
- **Retry config:** is `maxRetryDuration` set? Unlimited retries on a broken job can cause cascading failures.

**Flag:**
- Scheduler jobs pointing to URLs of deleted or non-existent services
- PAUSED jobs that appear to have no reason to be paused
- Jobs with persistent failure status (last 3+ runs failed)
- Duplicate schedules (two jobs doing the same thing)

Expected Hephae scheduler jobs:
- `workflow-monitor` — checks stalled workflows
- `workflow-dispatcher` — triggers new workflows
- `industry-pulse-cron` — weekly industry pulse
- `pulse-cron` — weekly zip pulse

---

## PHASE 4: ARTIFACT REGISTRY

```bash
gcloud artifacts repositories list --project=$PROJECT \
  --format="table(name, format, location, createTime, sizeBytes)"
```

For each repository:
```bash
gcloud artifacts docker images list REPOSITORY_PATH --project=$PROJECT \
  --include-tags --format="table(package, tags, createTime, updateTime)" \
  --limit=20 2>/dev/null | head -30
```

**Flag:**
- Untagged images (dangling layers) — pure waste
- Images older than 60 days with no tag pointing to them
- Repositories with no images (empty repos)
- Total storage size — Artifact Registry charges $0.10/GB/month

Estimate cleanup savings:
```bash
# Get total size per repo
gcloud artifacts repositories describe REPO_NAME --location=us-central1 --project=$PROJECT \
  --format="value(sizeBytes)" 2>/dev/null
```

---

## PHASE 5: GCS BUCKETS

```bash
gcloud storage buckets list --project=$PROJECT \
  --format="table(name, location, storageClass, timeCreated, labels)"
```

For each bucket:

```bash
# Object count and total size
gcloud storage du gs://BUCKET_NAME --summarize 2>/dev/null

# Lifecycle rules
gcloud storage buckets describe gs://BUCKET_NAME --format="value(lifecycle)" 2>/dev/null
```

**Checks for each bucket:**

| Check | Command | Flag if |
|-------|---------|---------|
| Lifecycle rules | `--format=value(lifecycle)` | No lifecycle = old objects accumulate forever |
| Public access | `--format=value(iamConfiguration)` | `allUsers` binding = public bucket (security risk) |
| Versioning | `--format=value(versioning)` | Versioning on + no lifecycle = unbounded cost |
| Storage class | `--format=value(storageClass)` | STANDARD for archival data = overpriced |
| CORS config | `--format=value(cors)` | Overly permissive CORS |

**Expected Hephae buckets:**
- `hephae-co-dev-prod-cdn-assets` — CDN bucket (public read expected)
- `everything-hephae` — legacy storage
- `hephae-co-dev_cloudbuild` — Cloud Build artifacts

**For CDN bucket:** check if public objects have `Cache-Control` headers set:
```bash
gcloud storage objects describe gs://hephae-co-dev-prod-cdn-assets/reports/ 2>/dev/null | grep cacheControl | head -5
```

---

## PHASE 6: FIRESTORE

```bash
# Get Firestore database info
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for db in data.get('databases', []):
    print('Database:', db.get('name','?').split('/')[-1])
    print('  Type:', db.get('type','?'))
    print('  Location:', db.get('locationId','?'))
    print('  Concurrency:', db.get('concurrencyMode','?'))
    print('  Point-in-time recovery:', db.get('pointInTimeRecoveryEnablement','?'))
"
```

**Collection size audit — check for unbounded growth:**
```bash
# Sample document counts per collection (REST runQuery with COUNT aggregate)
for collection in workflows businesses tasks pulse_jobs zipcode_weekly_pulse industry_pulses pulse_signal_archive data_cache discovery_jobs content_posts blog_posts; do
  count=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents:runAggregationQuery" \
    -d "{\"structuredAggregationQuery\":{\"structuredQuery\":{\"from\":[{\"collectionId\":\"$collection\"}]},\"aggregations\":[{\"alias\":\"count\",\"count\":{}}]}}" \
    2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    r=d.get('result',[{}])
    if isinstance(r,list): r=r[0] if r else {}
    val=r.get('aggregateFields',{}).get('count',{}).get('integerValue','?')
    print(val)
except: print('?')
" 2>/dev/null)
  echo "  $collection: $count docs"
done
```

**Flag:**
- `pulse_signal_archive` growing unboundedly — should have TTL cleanup
- `data_cache` growing unboundedly — should have TTL-based eviction
- `tasks` with large doc count — completed tasks should be archived to BQ
- `workflows` > 500 docs — old completed workflows should be purged

---

## PHASE 7: BIGQUERY

```bash
bq ls --project_id=$PROJECT --format=prettyjson 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for ds in data:
        print('Dataset:', ds.get('datasetReference',{}).get('datasetId','?'))
except: pass
"
```

For each dataset:
```bash
bq ls --project_id=$PROJECT --dataset_id=hephae --format=prettyjson 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for t in data:
        ref = t.get('tableReference',{})
        ttype = t.get('type','?')
        print(f'  {ref.get(\"tableId\",\"?\")} ({ttype})')
except: pass
"

# Table sizes
bq show --format=prettyjson $PROJECT:hephae.analyses 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    rows=d.get('numRows','?')
    size=int(d.get('numBytes','0'))
    print(f'  rows={rows}, size={size//1024//1024}MB')
except: pass
"
```

**Checks:**
- Tables with no expiry and large row counts → should have partition expiry
- Dataset location (should be `US` or `us-central1`, not a premium multi-region)
- Slot reservations (on-demand vs flat-rate) — flat-rate only worth it at high query volume

---

## PHASE 8: IAM & SERVICE ACCOUNTS

```bash
# All project-level IAM bindings
gcloud projects get-iam-policy $PROJECT \
  --format="table(bindings.role, bindings.members)" 2>/dev/null | head -50
```

```bash
# List all service accounts
gcloud iam service-accounts list --project=$PROJECT \
  --format="table(email, displayName, disabled)"
```

For each service account, check if it's actually used:
```bash
# Check last activity (requires Policy Analyzer or audit logs)
gcloud logging read \
  "protoPayload.authenticationInfo.principalEmail=\"SA_EMAIL\"" \
  --limit=1 --freshness=30d --project=$PROJECT \
  --format="value(timestamp)" 2>/dev/null
```

**Flag:**
- Service accounts with `roles/editor` or `roles/owner` — over-privileged
- Service accounts with no activity in 30+ days — potentially orphaned
- Service accounts with keys (not using Workload Identity Federation) — security risk
- Any binding for `allUsers` or `allAuthenticatedUsers` at project level — critical security issue
- Service account keys:

```bash
for sa in $(gcloud iam service-accounts list --project=$PROJECT --format="value(email)"); do
  keys=$(gcloud iam service-accounts keys list --iam-account=$sa --project=$PROJECT \
    --format="table(name.basename(), validAfterTime, validBeforeTime, keyType)" 2>/dev/null | grep -v "^KEY_ID\|^NAME" | wc -l)
  if [ "$keys" -gt 1 ]; then
    echo "  $sa: $keys keys (review recommended)"
  fi
done
```

---

## PHASE 9: SECRET MANAGER

```bash
gcloud secrets list --project=$PROJECT \
  --format="table(name, createTime, replication.automatic, labels)"
```

For each secret:
```bash
gcloud secrets versions list SECRET_NAME --project=$PROJECT \
  --format="table(name, state, createTime)" 2>/dev/null | head -5
```

**Flag:**
- Secrets with multiple ENABLED versions — old versions should be DISABLED/DESTROYED after rotation
- Secrets not referenced in any Cloud Run service (orphaned secrets)
- Secrets with no expiry on versions (no auto-rotation configured)

**Cross-reference:** compare secret list against what services actually mount:
```bash
for svc in $(gcloud run services list --region=us-central1 --project=$PROJECT --format="value(metadata.name)"); do
  echo "=== $svc ==="
  gcloud run services describe $svc --region=us-central1 --project=$PROJECT \
    --format="value(spec.template.spec.containers[0].env)" 2>/dev/null | grep -o 'secretKeyRef[^}]*' | head -10
done
```

---

## PHASE 10: BILLING ANOMALIES

```bash
# Recent billing data via Cloud Billing API (requires billing account access)
# Use gcloud billing to get account ID first
gcloud billing accounts list --format="value(name)" 2>/dev/null | head -1
```

```bash
# Check current month's costs by service via BigQuery billing export (if configured)
# Otherwise use the console budget/alert approach

# Check for unexpected high-cost services via logging
gcloud logging read \
  'resource.type="billing_account"' \
  --limit=10 --freshness=7d --project=$PROJECT 2>/dev/null | head -20

# Check Cloud Build history (builds are often forgotten cost sources)
gcloud builds list --project=$PROJECT --limit=10 \
  --format="table(id, createTime, duration, status, images)" 2>/dev/null
```

**Key cost drivers to check:**
- Cloud Build minutes (each build = ~5 min × $0.003/min = $0.015, but frequent deploys add up)
- Artifact Registry storage (old images)
- Cloud Run CPU/memory (min instances)
- BigQuery scan bytes (on-demand queries)
- GCS egress (CDN traffic)
- Secret Manager access API calls (charged per 10K accesses)

---

## PHASE 11: NETWORK & LOAD BALANCING

```bash
# Check for any Load Balancers (these are expensive if unused)
gcloud compute forwarding-rules list --project=$PROJECT 2>/dev/null
gcloud compute target-https-proxies list --project=$PROJECT 2>/dev/null
gcloud compute backend-services list --project=$PROJECT 2>/dev/null

# Check for static IPs (charged even when unused)
gcloud compute addresses list --project=$PROJECT \
  --format="table(name, address, status, region)" 2>/dev/null
```

**Flag:**
- Any reserved static IP not attached to a resource — $0.01/hour = ~$7/month wasted
- Load balancers with no healthy backends
- Unused VPC networks or firewall rules

---

## PHASE 12: LOGGING & MONITORING

```bash
# Check log sinks (billable if exporting large volumes)
gcloud logging sinks list --project=$PROJECT \
  --format="table(name, destination, filter)" 2>/dev/null

# Check alerting policies
gcloud alpha monitoring policies list --project=$PROJECT 2>/dev/null | head -20

# Check uptime checks
gcloud alpha monitoring uptime list --project=$PROJECT 2>/dev/null | head -10
```

**Flag:**
- Log sinks with no filter (exporting ALL logs is expensive)
- No uptime checks on production services
- No alerting policy for Cloud Run error rates

---

## PHASE 13: DEAD RESOURCE DETECTION

Run these to find resources that appear abandoned:

```bash
# Services with no recent requests (last 7 days)
gcloud logging read \
  'resource.type="cloud_run_revision" AND httpRequest.status>=200' \
  --freshness=7d --limit=1 --project=$PROJECT \
  --format="value(resource.labels.service_name)" 2>/dev/null | sort -u > /tmp/active_services.txt

# Compare against all services
gcloud run services list --region=us-central1 --project=$PROJECT \
  --format="value(metadata.name)" | while read svc; do
    if ! grep -q "^$svc$" /tmp/active_services.txt 2>/dev/null; then
      echo "  POSSIBLY DEAD: $svc (no requests in 7d)"
    fi
done

# Secrets with no access in 30 days
gcloud logging read \
  'protoPayload.serviceName="secretmanager.googleapis.com" AND protoPayload.methodName="AccessSecretVersion"' \
  --freshness=30d --project=$PROJECT \
  --format="value(protoPayload.resourceName)" 2>/dev/null | grep -oE 'secrets/[^/]+' | sort | uniq -c | sort -rn > /tmp/secret_access.txt
```

---

## SEVERITY GUIDE

| Severity | Meaning |
|----------|---------|
| CRITICAL | Security risk (public access, over-privileged SA, leaked keys) |
| HIGH | Active cost waste or reliability risk |
| MEDIUM | Optimization opportunity (oversized resources, no lifecycle rules) |
| LOW | Best practice gap (no alerting, floating image tags) |

---

## PHASE 14: REPORT

Write findings to `.claude/findings/infra-audit-{date}.md` and also to `.claude/findings/latest.md`:

```markdown
# GCP Infrastructure Audit: {PROJECT}
Generated: {ISO timestamp}

## Executive Summary
- **Critical issues:** {N}
- **High severity:** {N}
- **Medium:** {N}
- **Low:** {N}
- **Estimated monthly waste:** ${N}

## Cloud Run Services
| Service | CPU | Memory | Min Inst | Stale Revisions | Verdict |
|---------|-----|--------|----------|-----------------|---------|
{one row per service}

## Dead / Orphaned Resources
{numbered list with type, name, reason it appears dead, estimated monthly cost if any}

## Security Issues
{numbered list sorted by severity — CRITICAL first}

## Cost Optimization Opportunities
| Resource | Current Config | Recommended | Est. Monthly Savings |
|----------|---------------|-------------|----------------------|
{one row per opportunity}

## Firestore / BigQuery Health
{collection sizes, unbounded growth risks, missing TTLs}

## IAM Audit
{over-privileged accounts, orphaned SAs, key usage}

## Scheduler Health
{each job: state, last run status, target URL valid?}

## Artifact Registry Cleanup
{old images, estimated storage savings}

## Recommended Actions (Prioritized)
1. [CRITICAL] {action}
2. [HIGH] {action}
...
```

Output the executive summary + top 5 findings to the conversation immediately after writing the report.

---

## Key References

| Area | Tool |
|------|------|
| Cloud Run | `gcloud run services/jobs/revisions` |
| Scheduler | `gcloud scheduler jobs` |
| Artifact Registry | `gcloud artifacts` |
| GCS | `gcloud storage` |
| Firestore | Firestore REST API |
| BigQuery | `bq` CLI |
| IAM | `gcloud projects/iam` |
| Secrets | `gcloud secrets` |
| Billing | `gcloud billing` |
| Logs | `gcloud logging read` |
| Network | `gcloud compute` |

## What NOT To Do

- Do NOT modify, delete, or disable any resource. Read-only audit only.
- Do NOT flag Cloud Run min-instances=0 as a problem — cold starts are the intended trade-off for cost.
- Do NOT flag BigQuery table sizes as problems without checking if they have partition expiry set.
- Do NOT assume a service is dead from 7-day inactivity alone — check if it is a batch/cron-triggered service.
- Do NOT recommend disabling audit logs — they are security-critical.
- Do NOT flag the `_cloudbuild` GCS bucket lifecycle as missing — Cloud Build manages it automatically.
