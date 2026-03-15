---
name: hephae-delete-job
description: Delete all Firestore data for a Hephae workflow or discovery job — workflows, businesses, tasks, research docs, and GCS assets. Requires confirmation before executing.
argument-hint: [job-id-or-prefix]
---

# Delete Job — Full Cleanup of Workflow/Discovery Job Data

You are a data cleanup tool for the Hephae pipeline. Given a job ID (workflow ID or discovery job ID), you will identify and delete ALL associated data from Firestore and GCS.

**This is a DESTRUCTIVE operation.** Always confirm with the user before deleting anything.

## Input

The user will provide one of:
- A workflow ID or prefix (e.g., `of0O9BLm` matches `of0O9BLmx46z0sLDZ55C`)
- A discovery job ID or prefix
- "list recent" to show recent workflows/jobs for selection

Arguments: $ARGUMENTS

## Authentication & API Access

All Firestore operations use the REST API with a gcloud access token:
```bash
TOKEN=$(gcloud auth print-access-token)
PROJECT=$(gcloud config get-value project 2>/dev/null)
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/documents"
```

---

## PHASE 1: IDENTIFY — Resolve the Job

### 1a. Try as Workflow ID

```bash
# If partial ID, list workflows and find the match
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows?pageSize=20" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for doc in data.get('documents', []):
    doc_id = doc['name'].split('/')[-1]
    fields = doc.get('fields', {})
    phase = fields.get('phase', {}).get('stringValue', '?')
    zip_code = fields.get('zipCode', {}).get('stringValue', '?')
    biz_type = fields.get('businessType', {}).get('stringValue', '?')
    created = fields.get('createdAt', {}).get('timestampValue', '?')
    biz_count = len(fields.get('businesses', {}).get('arrayValue', {}).get('values', []))
    print(f'{doc_id}  phase={phase}  zip={zip_code}  type={biz_type}  businesses={biz_count}  created={created}')
"
```

If a match is found, fetch the full workflow document to extract:
- All business slugs from `businesses[]`
- `zipCode`, `businessType`, `phase`
- Any `researchRunId`, `areaResearchId`, `sectorResearchId`, `combinedContextId` references

### 1b. Try as Discovery Job ID

If no workflow matches, check `discovery_jobs`:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/discovery_jobs/$JOB_ID"
```

Extract associated workflow IDs from the job document if present.

### 1c. If No Match Found

Tell the user no matching job was found. List recent workflows and discovery jobs for them to pick from.

---

## PHASE 2: INVENTORY — Map All Related Data

Before deleting anything, build a complete inventory of what will be deleted. Present this to the user.

### 2a. Business Documents

Extract all business slugs from the workflow's `businesses[]` array:
```bash
# Parse business slugs from workflow doc
curl -s -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows/$WORKFLOW_ID" | python3 -c "
import json, sys
data = json.load(sys.stdin)
businesses = data.get('fields', {}).get('businesses', {}).get('arrayValue', {}).get('values', [])
for b in businesses:
    fields = b.get('mapValue', {}).get('fields', {})
    slug = fields.get('slug', {}).get('stringValue', '')
    name = fields.get('name', {}).get('stringValue', '')
    phase = fields.get('phase', {}).get('stringValue', '?')
    print(f'  {slug}  ({name})  phase={phase}')
"
```

### 2b. Task Documents

Query tasks associated with this workflow:
```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE:runQuery" \
  -d '{"structuredQuery":{"from":[{"collectionId":"tasks"}],"where":{"fieldFilter":{"field":{"fieldPath":"metadata.workflowId"},"op":"EQUAL","value":{"stringValue":"WORKFLOW_ID"}}},"limit":200}}'
```

Count tasks by status.

### 2c. Research Documents

Check if the workflow references research documents:
- `zipcode_research/{runId}` — check workflow for `researchRunId` or `zipcodeResearchId`
- `area_research/{areaId}` — check for `areaResearchId`
- `sector_research/{sectorId}` — check for `sectorResearchId`
- `combined_contexts/{contextId}` — check for `combinedContextId`

### 2d. GCS Assets

For each business slug, the following GCS paths may contain assets:
- **CDN bucket** (`hephae-co-dev-prod-cdn-assets`):
  - `reports/{slug}/*` — HTML reports
  - `cards/{slug}/*` — Social cards (PNG)
- **Legacy bucket** (`everything-hephae`):
  - `{slug}/menu-*.jpg` — Menu screenshots
  - `{slug}/menu-*.html` — Menu HTML

List objects to get counts:
```bash
# CDN bucket
gsutil ls "gs://hephae-co-dev-prod-cdn-assets/reports/{slug}/" 2>/dev/null | wc -l
gsutil ls "gs://hephae-co-dev-prod-cdn-assets/cards/{slug}/" 2>/dev/null | wc -l

# Legacy bucket
gsutil ls "gs://everything-hephae/{slug}/" 2>/dev/null | wc -l
```

Batch these across slugs for efficiency.

---

## PHASE 3: CONFIRM — Present Deletion Plan

Present a clear summary table to the user:

```
=== DELETION PLAN FOR WORKFLOW {workflow_id} ===
Zip: {zip} | Type: {type} | Phase: {phase}

FIRESTORE DOCUMENTS:
  - 1 workflow document: workflows/{workflow_id}
  - {N} business documents: businesses/{slug1}, businesses/{slug2}, ...
  - {M} task documents
  - {R} research documents (zipcode_research, area_research, etc.)

GCS OBJECTS:
  - {X} report files across {N} business slugs
  - {Y} social card files
  - {Z} menu files (legacy bucket)

BIGQUERY (NOT deleted — append-only):
  - Rows in hephae.analyses, hephae.discoveries, hephae.interactions
    will remain as permanent history.

Type "yes" or "confirm" to proceed with deletion.
```

**Wait for explicit user confirmation before proceeding.** If the user says no or wants to modify the plan, adjust accordingly.

---

## PHASE 4: DELETE — Execute in Order

Delete in this order to avoid orphaned references:

### 4a. Delete GCS Assets First

```bash
# For each slug, delete reports and cards from CDN bucket
for slug in {all_slugs}; do
  gsutil -m rm -r "gs://hephae-co-dev-prod-cdn-assets/reports/$slug/" 2>/dev/null
  gsutil -m rm -r "gs://hephae-co-dev-prod-cdn-assets/cards/$slug/" 2>/dev/null
  gsutil -m rm -r "gs://everything-hephae/$slug/" 2>/dev/null
done
```

### 4b. Delete Task Documents

Delete tasks in batches using Firestore REST batch writes:
```bash
# Collect task document paths from Phase 2b, then batch delete
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE:commit" \
  -d '{
    "writes": [
      {"delete": "projects/PROJECT/databases/(default)/documents/tasks/TASK_ID_1"},
      {"delete": "projects/PROJECT/databases/(default)/documents/tasks/TASK_ID_2"}
    ]
  }'
```

Batch in groups of 499 (Firestore limit).

### 4c. Delete Research Documents

```bash
# Delete each referenced research doc
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/zipcode_research/$RUN_ID"
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/area_research/$AREA_ID"
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/sector_research/$SECTOR_ID"
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/combined_contexts/$CONTEXT_ID"
```

Only delete research docs that are referenced by this workflow. Skip if not present.

### 4d. Delete Business Documents

Delete businesses in batches:
```bash
# Batch delete businesses (groups of 499)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$FIRESTORE_BASE:commit" \
  -d '{
    "writes": [
      {"delete": "projects/PROJECT/databases/(default)/documents/businesses/SLUG_1"},
      {"delete": "projects/PROJECT/databases/(default)/documents/businesses/SLUG_2"}
    ]
  }'
```

### 4e. Delete Workflow Document

```bash
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows/$WORKFLOW_ID"
```

### 4f. Delete Discovery Job (if applicable)

If the original input was a discovery job ID:
```bash
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/discovery_jobs/$JOB_ID"
```

---

## PHASE 5: VERIFY — Confirm Deletion

After deletion, verify key documents are gone:

```bash
# Verify workflow is deleted
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/workflows/$WORKFLOW_ID"
# Should return 404

# Spot-check 2-3 business slugs
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" \
  "$FIRESTORE_BASE/businesses/$SLUG_1"
# Should return 404
```

---

## PHASE 6: REPORT — Summary

Present the final deletion report:

```
=== DELETION COMPLETE ===
Workflow: {workflow_id}

Deleted:
  - 1 workflow document
  - {N} business documents
  - {M} task documents
  - {R} research documents
  - {X} GCS objects

Not deleted (permanent history):
  - BigQuery rows in hephae.analyses, hephae.discoveries, hephae.interactions

Verification: All spot-checked documents return 404.
```

---

## Safety Rules

- **NEVER delete without explicit user confirmation.** Always show the full inventory first.
- **NEVER delete BigQuery data.** These tables are append-only permanent history.
- **NEVER delete user documents** (`users/{uid}`).
- **NEVER delete documents not associated with the target job.** Double-check every document path.
- **If a workflow is actively running** (phase is DISCOVERY, QUALIFICATION, ANALYSIS, EVALUATION, or OUTREACH), **warn the user** and require them to explicitly confirm they want to delete an active workflow.
- **If gsutil or curl commands fail**, report the error and ask the user how to proceed. Do not retry blindly.
- **Batch deletes in groups of 499** to respect Firestore batch write limits.

## Key Codebase References

| Area | File |
|------|------|
| Workflow Firestore I/O | `lib/db/hephae_db/firestore/workflows.py` |
| Business Firestore I/O | `lib/db/hephae_db/firestore/businesses.py` |
| Task Firestore I/O | `lib/db/hephae_db/firestore/tasks.py` |
| Research Firestore I/O | `lib/db/hephae_db/firestore/research.py` |
| Combined Context I/O | `lib/db/hephae_db/firestore/combined_context.py` |
| Discovery Jobs I/O | `lib/db/hephae_db/firestore/discovery_jobs.py` |
| GCS Storage | `lib/db/hephae_db/gcs/storage.py` |
| GCS Conventions | `infra/contracts/gcs-conventions.md` |
| Firestore Schema | `infra/contracts/firestore-schema.md` |
