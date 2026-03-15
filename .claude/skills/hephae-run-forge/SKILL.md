---
name: hephae-run-forge
description: Run the Hephae Forge pipeline locally in debug mode — triggers discovery through evaluation for a given zip code or county and business type. Streams progress and auto-debugs on failure.
argument-hint: [zip-code-or-county business-type]
user_invocable: true
---

# Run Forge — Local Debug Pipeline Runner

You are a pipeline runner for the Hephae Forge workflow. You launch the full pipeline (discovery → qualification → analysis → evaluation) locally against the unified API and monitor progress, reporting results back to the user.

## Input

The user may provide arguments inline, or you may need to ask.

Arguments: $ARGUMENTS

### Step 1: Gather Inputs

Parse `$ARGUMENTS` for a zip code (5-digit number) and/or business type. If arguments are missing or incomplete, ask the user using `AskUserQuestion`:

**If no zip code or county:**
Ask: "What zip code or county should I run? (e.g., `07001` or `Bergen County, NJ`)"

**If no business type:**
Ask: "What business type? (e.g., `Restaurants`, `Bakeries`, `Hair Salons`, `Laundromats`)"

**If the user gave a county name** (not a 5-digit zip): use the county workflow path.
**If the user gave a zip code**: use the single-zip workflow path.

### Step 2: Ensure API is Running

Check if the API is already running on port 8080:

```bash
curl -s http://localhost:8080/health 2>/dev/null | head -1
```

If not running, start it in the background:

```bash
cd /Users/sarthak/Desktop/hephae/hephae-forge/apps/api && .venv/bin/uvicorn hephae_api.main:app --port 8080 &
```

Wait up to 10 seconds for it to become healthy.

### Step 3: Create & Start Workflow

**For a single zip code:**

```bash
curl -s -X POST http://localhost:8080/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"zipCode": "<ZIP>", "businessType": "<TYPE>"}'
```

**For a county:**

```bash
curl -s -X POST http://localhost:8080/api/workflows/county \
  -H "Content-Type: application/json" \
  -d '{"county": "<COUNTY>", "businessType": "<TYPE>", "maxZipCodes": 5}'
```

Note: If auth is required (401/403), the API may need `FORGE_API_SECRET` or Firebase auth disabled for local dev. Check if there's a `SKIP_AUTH` env var or if the admin auth middleware passes when no allowlist is configured. If auth blocks, try setting `ADMIN_EMAIL_ALLOWLIST=""` in the environment.

Extract the `workflowId` from the response.

### Step 4: Monitor Progress

Poll the workflow status every 10 seconds using the Firestore REST API (same pattern as debug-job):

```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"

curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows/<WORKFLOW_ID>" | python3 -c "
import sys, json
doc = json.load(sys.stdin)
fields = doc.get('fields', {})
phase = fields.get('phase', {}).get('stringValue', 'UNKNOWN')
progress = {}
prog_fields = fields.get('progress', {}).get('mapValue', {}).get('fields', {})
for k, v in prog_fields.items():
    val = v.get('integerValue') or v.get('stringValue', '')
    if val: progress[k] = val
print(f'Phase: {phase}')
for k, v in progress.items():
    print(f'  {k}: {v}')
error = fields.get('lastError', {}).get('stringValue')
if error: print(f'ERROR: {error}')
"
```

### Step 5: Report Progress

As you poll, report progress to the user in a compact format:

```
Workflow <ID> — Phase: DISCOVERY
  zipCodesScanned: 1/1
  businessesFound: 12
```

Update the user at each phase transition:
- **DISCOVERY** → report businesses found
- **QUALIFICATION** → report qualified/parked/disqualified counts
- **ANALYSIS** → report capabilities completed per business
- **EVALUATION** → report pass/fail scores
- **APPROVAL** → tell user workflow is paused for approval
- **COMPLETED** → summarize final results
- **FAILED** → trigger auto-debug (see Step 6)

### Step 6: On Failure — Auto-Debug

If the workflow reaches FAILED phase or stalls in one phase for >5 minutes:

1. Read the workflow's `lastError` field
2. Check businesses for the workflow to see which ones failed:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/businesses?pageSize=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for doc in data.get('documents', []):
    fields = doc.get('fields', {})
    wf_id = fields.get('workflowId', {}).get('stringValue', '')
    if wf_id == '<WORKFLOW_ID>':
        name = fields.get('name', {}).get('stringValue', '?')
        phase = fields.get('phase', {}).get('stringValue', '?')
        err = fields.get('lastError', {}).get('stringValue', '')
        caps = fields.get('capabilitiesCompleted', {})
        print(f'{name}: phase={phase} err={err[:80] if err else \"ok\"} caps={caps}')
"
```

3. Check Cloud Run logs for errors:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR AND timestamp>="<5_MIN_AGO_ISO>"' \
  --project=$PROJECT --limit=20 --format="table(timestamp,textPayload)"
```

4. Summarize the failure with:
   - Which phase failed
   - How many businesses were affected
   - Root cause (rate limit, model error, data issue, etc.)
   - Suggested fix

### Step 7: Final Summary

When the workflow reaches APPROVAL or COMPLETED, provide a final summary:

```
## Forge Run Complete

- **Zip Code(s):** 07001
- **Business Type:** Restaurants
- **Businesses Discovered:** 15
- **Qualified:** 8 | Parked: 5 | Disqualified: 2
- **Capabilities Run:** SEO: 8, Traffic: 8, Competitive: 8, Margin: 6
- **Evaluation:** 7 passed (score ≥80), 1 failed
- **Status:** Paused at APPROVAL — run `/hephae-debug-job <workflow-id>` for detailed inspection
```

Pull these numbers from the workflow's `progress` field and business documents.

---

## Important Notes

- This runs the FULL pipeline — discovery, qualification, analysis (4 capabilities), evaluation. It can take 10-30 minutes depending on the number of businesses found.
- The API must have `GEMINI_API_KEY` set in the environment for agents to work.
- Analysis runs via Cloud Tasks in production; locally it runs in-process.
- If you see 429 errors, the model is rate-limited — the built-in retry logic handles this (up to 3 rounds).
- Do NOT modify any code. This skill is read-only — it only starts workflows and monitors them.
