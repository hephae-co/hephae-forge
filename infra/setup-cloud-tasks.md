# Cloud Tasks Setup

The workflow analysis phase uses Google Cloud Tasks to execute business analysis in parallel. This replaces the old in-process `asyncio.gather` approach.

## Prerequisites

### 1. Enable Cloud Tasks API

```bash
gcloud services enable cloudtasks.googleapis.com --project=$GCP_PROJECT_ID
```

### 2. Create the Agent Queue

```bash
gcloud tasks queues create hephae-agent-queue \
  --location=us-central1 \
  --project=$GCP_PROJECT_ID \
  --max-dispatches-per-second=5 \
  --max-concurrent-dispatches=3 \
  --max-attempts=2 \
  --min-backoff=10s
```

Queue settings:
- **max-concurrent-dispatches=3** — replaces the old `BATCH_CONCURRENCY = 3`
- **max-dispatches-per-second=5** — rate limit to avoid overwhelming the API
- **max-attempts=2** — retry once on failure (execute endpoint is idempotent)

### 3. Grant IAM Roles to Service Account

The Cloud Run service account needs three roles:

```bash
SA="hephae-forge@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Enqueue tasks
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/cloudtasks.enqueuer"

# Invoke Cloud Run (for OIDC token on task callbacks)
gcloud run services add-iam-policy-binding hephae-forge-api \
  --project=$GCP_PROJECT_ID \
  --region=us-central1 \
  --member="serviceAccount:$SA" \
  --role="roles/run.invoker"

# Act-as-self (required for Cloud Tasks to create OIDC tokens)
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="serviceAccount:$SA" \
  --role="roles/iam.serviceAccountUser" \
  --project=$GCP_PROJECT_ID
```

### 4. API_BASE_URL Environment Variable

The deploy script auto-detects this from the existing Cloud Run service URL. It must be set so Cloud Tasks knows where to POST task execution requests.

```
API_BASE_URL=https://hephae-forge-api-XXXXX.us-central1.run.app
```

## Architecture

```
Workflow Engine
  └─ run_analysis_phase()
       ├─ Creates Firestore task record per business
       ├─ Enqueues WORKFLOW_ANALYZE to hephae-agent-queue
       └─ Polls Firestore every 3s for substep transitions → fires SSE callbacks

Cloud Tasks Queue (hephae-agent-queue)
  └─ POST /api/research/tasks/execute
       └─ _run_workflow_analyze(slug, task_id, metadata)
            ├─ Enrichment → substep: enrichment_done
            ├─ Identity building (area/zip/sector research context)
            ├─ Food pricing context (BLS + USDA for food businesses)
            ├─ Run all capabilities (asyncio.gather) → substep: capability_done:{name}
            ├─ Persist latestOutputs to Firestore
            └─ Generate insights → substep: insights_done
```

## Verification

1. Start a workflow — check Cloud Tasks queue has WORKFLOW_ANALYZE tasks:
   ```bash
   gcloud tasks list --queue=hephae-agent-queue --location=us-central1 --project=$GCP_PROJECT_ID
   ```

2. Check Firestore `tasks` collection — task metadata should show substep progression

3. SSE stream should show enrichment/capability/insights events with ~3s latency

4. Businesses tab "Run All" still works via existing ANALYZE_FULL path (unchanged)

## Tuning

- **Increase parallelism**: `gcloud tasks queues update hephae-agent-queue --max-concurrent-dispatches=5`
- **Dispatch deadline**: Set to 30 min (1800s) per task — full analysis can take 10-15 min
- **Polling interval**: 3 seconds — acceptable latency for admin SSE
