> Auto-generated from codebase on 2026-03-22.

# Admin API Routes

All admin routes require authentication via **Firebase token** checked against the admin allowlist (`verify_admin_request`). Requests without a valid `x-firebase-token` header receive 401; non-allowlisted users receive 403. The one exception is `POST /api/research/tasks/execute`, which is called internally by Cloud Tasks and has no auth dependency.

Admin routers are registered **without a global prefix** in `main.py` — each router defines its own prefix.

**Total: 21 routers, 70+ endpoints** across Admin (21 routers), Batch/Cron (8 routers), plus 2 top-level health endpoints.

---

## Health (top-level)
Source: `apps/api/hephae_api/main.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | Health check |
| GET | `/` | None | Root status endpoint |

---

## Workflows
Source: `apps/api/hephae_api/routers/admin/workflows.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/workflows` | Firebase Admin | Create and start a new workflow for a zip code |
| GET | `/api/workflows` | Firebase Admin | List recent workflows (limit 20) |
| POST | `/api/workflows/county` | Firebase Admin | Create and start a county-wide workflow |

### POST /api/workflows
Create a new workflow for a single zip code and start the workflow engine in the background.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | 5-digit zip code |
| `businessType` | `string \| null` | No | Business type filter |

**Response:** `{ workflowId: string, status: "started" }`

### GET /api/workflows
List the 20 most recent workflows.

**Response:** `WorkflowDocument[]` (JSON-serialized)

### POST /api/workflows/county
Create a county-wide workflow by resolving zip codes from a county name using the county resolver agent.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `businessType` | `string` | Yes | Business type to discover |
| `county` | `string` | Yes | County name (e.g. "Cook County, IL") |
| `maxZipCodes` | `int \| null` | No | Max zip codes to include (default 10, cap 15) |

**Response:** `{ workflowId: string, status: "started", zipCodes: string[], countyName: string, state: string }`

---

## Workflow Stream
Source: `apps/api/hephae_api/routers/admin/workflow_stream.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/workflows/{workflow_id}/stream` | Firebase Admin | SSE stream of workflow progress |

### GET /api/workflows/{workflow_id}/stream
Server-Sent Events stream for real-time workflow progress. Sends initial state, then streams progress events. Falls back to Firestore polling (3s intervals, max 30 min) if no in-process engine is found.

**SSE event types:**
- `initial` -- full workflow state on connect
- `heartbeat` -- keep-alive (every 30s during in-process streaming)
- `phase_changed` -- workflow phase transition (polling mode)
- `poll` -- progress update (polling mode)
- `done` -- workflow reached terminal phase (COMPLETED, FAILED, or APPROVAL)
- `error` -- workflow not found

**Response:** `text/event-stream`

---

## Workflow Actions
Source: `apps/api/hephae_api/routers/admin/workflow_actions.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/workflows/{workflow_id}` | Firebase Admin | Get workflow detail |
| GET | `/api/workflows/{workflow_id}/research` | Firebase Admin | Get zip code and area research for a workflow |
| PATCH | `/api/workflows/{workflow_id}` | Firebase Admin | Force-stop a running workflow |
| DELETE | `/api/workflows/{workflow_id}` | Firebase Admin | Delete a workflow |
| POST | `/api/workflows/{workflow_id}/approve` | Firebase Admin | Approve/reject businesses in a workflow |
| POST | `/api/workflows/{workflow_id}/resume` | Firebase Admin | Resume a failed workflow |

### GET /api/workflows/{workflow_id}
Return the full workflow document.

**Response:** `WorkflowDocument` (JSON-serialized)

### GET /api/workflows/{workflow_id}/research
Fetch zip code reports and area research produced during a workflow run. Iterates over all zip codes in the workflow.

**Response:**
```json
{
  "zipReports": { "<zipCode>": "<ZipCodeReport>" },
  "areaResearch": { "<zipCode>": { "area": "string", "businessType": "string", "summary": "<AreaSummary>" } }
}
```

### PATCH /api/workflows/{workflow_id}
Force-stop a running workflow by marking it as FAILED.

**Response:** `{ success: true, message: "Workflow stopped" }`

### DELETE /api/workflows/{workflow_id}
Delete a workflow document.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `force` | `bool` | `false` | Force delete even if not in terminal state |

**Response:** `{ success: true, ... }`

### POST /api/workflows/{workflow_id}/approve
Submit approval/rejection decisions for businesses awaiting review. Records feedback to BigQuery. If any business is approved, starts the outreach engine in the background.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `approvals` | `dict[string, string]` | Yes | Map of business slug to `"approve"` or `"reject"` |

**Response:** `{ success: true, approved: bool }`

### POST /api/workflows/{workflow_id}/resume
Resume a failed workflow. Clears the error, increments retry count, and determines the resume phase based on business states (DISCOVERY, ANALYSIS, or EVALUATION).

**Response:** `{ success: true, resumePhase: string }`

---

## Research Businesses
Source: `apps/api/hephae_api/routers/admin/research_businesses.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/research/businesses` | Firebase Admin | List businesses with pagination and filters |
| GET | `/api/research/businesses/{slug}` | Firebase Admin | Get business profile summary for approval review |
| POST | `/api/research/businesses` | Firebase Admin | Discover businesses in a zip code |
| DELETE | `/api/research/businesses` | Firebase Admin | Delete a business by ID |
| GET | `/api/research/discovery-status` | Firebase Admin | Get discovery progress for a zip code |
| POST | `/api/research/actions` | Firebase Admin | Execute an action on one or more businesses |

### GET /api/research/businesses
Paginated business listing with optional filters.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `zipCode` | `string \| null` | `null` | Filter by zip code |
| `page` | `int` | `1` | Page number (>= 1) |
| `pageSize` | `int` | `25` | Results per page (1-100) |
| `category` | `string \| null` | `null` | Filter by category |
| `status` | `string \| null` | `null` | Filter by status |
| `hasEmail` | `bool \| null` | `null` | Filter by email presence |
| `name` | `string \| null` | `null` | Filter by name |

**Response:** Paginated business list (from `get_businesses_paginated`)

### GET /api/research/businesses/{slug}
Lightweight business profile summary for the approval UI. Includes identity fields, capability output summaries (scores/headlines only), and insights.

**Response:**
```json
{
  "slug": "string",
  "name": "string",
  "address": "string",
  "officialUrl": "string",
  "phone": "string",
  "email": "string",
  "socialLinks": {},
  "competitors": [],
  "persona": "string",
  "hours": "string",
  "menuUrl": "string",
  "logoUrl": "string",
  "capabilities": {
    "<key>": { "score": "number|null", "summary": "string", "reportUrl": "string|null" }
  },
  "insights": {}
}
```

### POST /api/research/businesses
Trigger a zip code scan to discover businesses.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | 5-digit zip code to scan |

**Response:** `{ count: int, businesses: Business[] }`

### DELETE /api/research/businesses
Delete a single business by ID.

**Query params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `string` | Yes | Business document ID |

**Response:** `{ success: true }`

### GET /api/research/discovery-status
Check discovery progress for a zip code (reads from `discovery_progress` Firestore collection).

**Query params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | 5-digit zip code |

**Response:** `{ success: bool, progress: dict | null }`

### POST /api/research/actions
Execute an action on one or more businesses. Supports both single and bulk actions.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | `string` | Yes | Action type (see below) |
| `businessId` | `string \| null` | Varies | Target business ID |
| `businessIds` | `string[] \| null` | No | For bulk actions |
| `bulkAction` | `string \| null` | No | Sub-action for bulk (default `"deep-dive"`) |
| `zipCode` | `string \| null` | No | Zip code context |
| `channel` | `string \| null` | No | Outreach channel |
| `fixtureType` | `string \| null` | No | Fixture type for save-fixture |
| `fixtureId` | `string \| null` | No | Fixture ID for remove-from-test-set |
| `notes` | `string \| null` | No | Notes for fixture |
| `agentName` | `string \| null` | No | Agent name for run-agent |
| `agentKey` | `string \| null` | No | Agent key for save-fixture or delete-agent-result |
| `editedContent` | `string \| null` | No | Edited outreach content |
| `emailSubject` | `string \| null` | No | Email subject for save-outreach-draft |

**Supported actions:**

| Action | Required Fields | Description |
|--------|----------------|-------------|
| `bulk` | `businessIds`, `bulkAction` | Run an action across multiple businesses |
| `deep-dive` | `businessId` | Generate AI insights for a business |
| `outreach` | `businessId`, `channel` | Draft and send outreach (email/social) |
| `generate-outreach-content` | `businessId` | Generate social posts + CDN assets for all channels |
| `save-outreach-draft` | `businessId`, `channel`, `editedContent` | Save an edited outreach draft |
| `delete` | `businessId` | Delete a business |
| `rediscover` | `businessId` | Delete and re-scan the business's zip code |
| `save-fixture` | `businessId`, `fixtureType` | Save business as a test fixture |
| `remove-from-test-set` | `fixtureId` | Delete a test fixture |
| `start-discovery` | `businessId` | Run enrichment pipeline on a business |
| `run-analysis` | `businessId` | Run full analysis pipeline (requires prior discovery) |
| `run-reviewer` | `businessId` | Run the reviewer agent on a business |
| `delete-agent-result` | `businessId`, `agentKey` | Delete a specific agent output from latestOutputs |
| `run-agent` | `businessId`, `agentName` | Run a specific capability agent by name |

**Response:** Varies by action (all include `{ success: bool }`)

---

## Zip Code Research
Source: `apps/api/hephae_api/routers/admin/zipcode_research.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/zipcode-research` | Firebase Admin | List recent zip code research runs |
| POST | `/api/zipcode-research/{zip_code}` | Firebase Admin | Start research for a zip code |
| GET | `/api/zipcode-research/{zip_code}` | Firebase Admin | Get the research report for a zip code |
| GET | `/api/zipcode-research/runs/{run_id}` | Firebase Admin | Get a specific research run |
| DELETE | `/api/zipcode-research/runs/{run_id}` | Firebase Admin | Delete a research run |

### GET /api/zipcode-research
List recent zip code research runs.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `10` | Max results (1-50) |

**Response:** `Run[]` (serialized)

### POST /api/zipcode-research/{zip_code}
Start a zip code research run. Returns cached result if available unless `force=true`.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `force` | `bool` | `false` | Force re-research even if cached |

**Response:** `{ success: true, report: ZipCodeReport, runId: string }`

### GET /api/zipcode-research/{zip_code}
Get the latest research report for a zip code.

**Response:** Serialized zip code report document

### GET /api/zipcode-research/runs/{run_id}
Get a specific research run by ID.

**Response:** Serialized run document

### DELETE /api/zipcode-research/runs/{run_id}
Delete a research run.

**Response:** `{ success: true }`

---

## Area Research
Source: `apps/api/hephae_api/routers/admin/area_research.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/area-research` | Firebase Admin | Start area research |
| GET | `/api/area-research` | Firebase Admin | List area research documents |
| GET | `/api/area-research/{area_id}` | Firebase Admin | Get area research detail |
| DELETE | `/api/area-research/{area_id}` | Firebase Admin | Delete area research |
| GET | `/api/area-research/{area_id}/stream` | Firebase Admin | SSE stream of area research progress |

### POST /api/area-research
Start area research for a geographic area and business type. Resolves zip codes and orchestrates multi-zip research.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `area` | `string` | Yes | Area name (e.g. "Austin, TX") |
| `businessType` | `string` | Yes | Business type to research |
| `maxZipCodes` | `int \| null` | No | Max zip codes to research (default 10, cap 15) |

**Response:** `{ areaId: string, status: "started", area: string, businessType: string }`

### GET /api/area-research
List the 20 most recent area research documents.

**Response:** `AreaResearch[]` (serialized)

### GET /api/area-research/{area_id}
Get a specific area research document.

**Response:** Serialized area research document

### DELETE /api/area-research/{area_id}
Delete an area research document. Blocked if the orchestrator is actively running.

**Response:** `{ success: true }`

### GET /api/area-research/{area_id}/stream
SSE stream for area research progress. Same streaming pattern as workflow stream: tries in-process streaming first, falls back to Firestore polling (3s intervals, max 30 min).

**SSE event types:**
- `initial` -- full document on connect
- `heartbeat` -- keep-alive
- `phase_changed` -- phase transition
- `poll` -- progress update with `{ totalZipCodes, completedZipCodes, failedZipCodes }`
- `done` -- research completed or failed
- `error` -- not found

**Response:** `text/event-stream`

---

## Sector Research
Source: `apps/api/hephae_api/routers/admin/sector_research.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sector-research` | Firebase Admin | Start sector research |
| GET | `/api/sector-research` | Firebase Admin | List sector research documents |
| GET | `/api/sector-research/{sector_id}` | Firebase Admin | Get sector research detail |

### POST /api/sector-research
Start sector-level research. Returns existing research if already completed for this sector. Runs in background.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sector` | `string` | Yes | Sector/business type |
| `zipCodes` | `string[] \| null` | No | Specific zip codes to include |
| `areaName` | `string \| null` | No | Area name for context |

**Response:** `{ status: "started" | "existing", sector: string, ... }`

### GET /api/sector-research
List the 20 most recent sector research documents.

**Response:** `SectorResearch[]` (serialized)

### GET /api/sector-research/{sector_id}
Get a specific sector research document.

**Response:** Serialized sector research document

---

## Combined Context
Source: `apps/api/hephae_api/routers/admin/combined_context.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/combined-context` | Firebase Admin | Create a combined context from multiple research runs |
| GET | `/api/combined-context` | Firebase Admin | List combined contexts |
| GET | `/api/combined-context/{context_id}` | Firebase Admin | Get a combined context |
| DELETE | `/api/combined-context/{context_id}` | Firebase Admin | Delete a combined context |

### POST /api/combined-context
Combine multiple zip code research runs into a unified context using the context combiner agent. Requires at least 2 run IDs.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `runIds` | `string[]` | Yes | List of research run IDs (min 2) |

**Response:** `{ success: true, contextId: string, context: CombinedContext }`

### GET /api/combined-context
List combined contexts.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `10` | Max results (1-50) |

**Response:** `CombinedContext[]` (serialized)

### GET /api/combined-context/{context_id}
Get a specific combined context.

**Response:** Serialized combined context document

### DELETE /api/combined-context/{context_id}
Delete a combined context.

**Response:** `{ success: true }`

---

## Stats
Source: `apps/api/hephae_api/routers/admin/stats.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/stats` | Firebase Admin | Get dashboard statistics |

### GET /api/stats
Returns aggregated dashboard statistics from Firestore.

**Response:** Dashboard stats object (from `get_dashboard_stats`)

---

## Fixtures
Source: `apps/api/hephae_api/routers/admin/fixtures.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/fixtures` | Firebase Admin | Create a test fixture from a workflow business |
| GET | `/api/fixtures` | Firebase Admin | List test fixtures |
| GET | `/api/fixtures/{fixture_id}` | Firebase Admin | Get a fixture |
| DELETE | `/api/fixtures/{fixture_id}` | Firebase Admin | Delete a fixture |

### POST /api/fixtures
Save a business from a workflow as a test fixture (for grounding or failure case tracking).

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflowId` | `string` | Yes | Source workflow ID |
| `businessSlug` | `string` | Yes | Business slug within the workflow |
| `fixtureType` | `string` | Yes | `"grounding"` or `"failure_case"` |
| `notes` | `string \| null` | No | Optional notes |

**Response:** `{ success: true, fixtureId: string }`

### GET /api/fixtures
List fixtures, optionally filtered by type.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `string \| null` | `null` | Filter by fixture type |

**Response:** `Fixture[]` (serialized)

### GET /api/fixtures/{fixture_id}
Get a specific fixture.

**Response:** Serialized fixture document

### DELETE /api/fixtures/{fixture_id}
Delete a fixture.

**Response:** `{ success: true }`

---

## Test Runner
Source: `apps/api/hephae_api/routers/admin/test_runner.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/run-tests` | Firebase Admin | Run the full QA test suite |
| GET | `/api/run-tests` | Firebase Admin | List historical test runs |

### POST /api/run-tests
Run the full QA suite (4 capabilities x evaluators). Persists results to Firestore.

**Response:** Test run summary object

### GET /api/run-tests
Return historical test runs from Firestore (auto-cleaned after 7 days).

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `20` | Max results (1-100) |

**Response:** `TestRun[]`

---

## Food Prices
Source: `apps/api/hephae_api/routers/admin/food_prices.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/food-prices/cpi` | Firebase Admin | Get BLS Consumer Price Index data |
| GET | `/api/food-prices/commodities` | Firebase Admin | Get USDA NASS commodity prices |
| GET | `/api/food-prices/summary` | Firebase Admin | Get combined food price summary |

### GET /api/food-prices/cpi
Get BLS Consumer Price Index data for food categories.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `industry` | `string` | `""` | Business type for industry-specific series |

**Response:** BLS CPI data object

### GET /api/food-prices/commodities
Get USDA NASS commodity prices for agricultural products.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `industry` | `string` | `"restaurants"` | Business type |
| `state` | `string` | `""` | State name or 2-letter code (empty = national) |

**Response:** USDA NASS commodity data object

### GET /api/food-prices/summary
Get combined food price summary from both BLS CPI and USDA NASS sources.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `industry` | `string` | `"restaurants"` | Business type |
| `state` | `string` | `""` | State for USDA data (empty = national) |

**Response:**
```json
{
  "blsCpi": "<BLS data | null>",
  "usdaNass": "<USDA data | null>",
  "sources": ["BLS Consumer Price Index", "USDA NASS QuickStats"],
  "highlights": ["<merged highlights from both sources>"]
}
```

---

## Content
Source: `apps/api/hephae_api/routers/admin/content.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/content/generate` | Firebase Admin | Generate content from research data |
| GET | `/api/content` | Firebase Admin | List content posts |
| GET | `/api/content/{post_id}` | Firebase Admin | Get a content post |
| PATCH | `/api/content/{post_id}` | Firebase Admin | Edit a draft post |
| POST | `/api/content/{post_id}/publish` | Firebase Admin | Publish a post |
| DELETE | `/api/content/{post_id}` | Firebase Admin | Delete a draft post |

### POST /api/content/generate
Generate content for a platform from research data. Calls the forge content generation endpoint, saves result as a draft.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `platform` | `ContentPlatform` | Yes | `"x"`, `"instagram"`, `"facebook"`, or `"blog"` |
| `sourceType` | `ContentSourceType` | Yes | `"zipcode_research"`, `"area_research"`, or `"combined_context"` |
| `sourceId` | `string` | Yes | ID of the research source |

**Response:** `{ success: true, post: ContentPost }`

### GET /api/content
List content posts with optional platform filter.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `platform` | `string \| null` | `null` | Filter by platform |
| `limit` | `int` | `20` | Max results (1-100) |

**Response:** `ContentPost[]` (serialized)

### GET /api/content/{post_id}
Get a specific content post.

**Response:** Serialized content post

### PATCH /api/content/{post_id}
Edit a draft content post. Only drafts can be edited.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | `string \| null` | No | Updated content text |
| `title` | `string \| null` | No | Updated title |
| `hashtags` | `string[] \| null` | No | Updated hashtags |

**Response:** Updated content post (serialized)

### POST /api/content/{post_id}/publish
Publish a content post. Blog posts are marked as published directly. Social posts are published via the platform API client. Character limits enforced per platform (X: 280, Instagram: 2200, Facebook: 63206).

**Response:** `{ success: bool, post: ContentPost, error: string | null }`

### DELETE /api/content/{post_id}
Delete a content post. Published posts cannot be deleted.

**Response:** `{ success: true }`

---

## Discovery Jobs
Source: `apps/api/hephae_api/routers/admin/discovery_jobs.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/admin/discovery-jobs` | Firebase Admin | List all discovery jobs |
| POST | `/api/admin/discovery-jobs` | Firebase Admin | Create a new discovery job |
| GET | `/api/admin/discovery-jobs/{job_id}` | Firebase Admin | Get job detail |
| POST | `/api/admin/discovery-jobs/{job_id}/run-now` | Firebase Admin | Trigger immediate execution of the Cloud Run Job |
| DELETE | `/api/admin/discovery-jobs/{job_id}` | Firebase Admin | Cancel or delete a job |

### GET /api/admin/discovery-jobs
List all discovery jobs (up to 100).

**Response:** `{ jobs: DiscoveryJob[] }`

### POST /api/admin/discovery-jobs
Create a new batch discovery job with one or more zip code targets.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Job name |
| `targets` | `DiscoveryTarget[]` | Yes | List of targets (must not be empty) |
| `notifyEmail` | `string` | No | Notification email (default `admin@hephae.co`) |
| `settings` | `dict` | No | Additional job settings |

**DiscoveryTarget:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | Target zip code |
| `businessTypes` | `string[]` | No | Business type filters (default `[]`) |

**Response:** `{ success: true, jobId: string }`

### GET /api/admin/discovery-jobs/{job_id}
Get detail for a specific discovery job.

**Response:** Discovery job document (with datetime fields serialized to ISO strings)

### POST /api/admin/discovery-jobs/{job_id}/run-now
Trigger an immediate execution of the `discovery-batch` Cloud Run Job via gcloud CLI. Job must be in `pending` status. Returns 409 if already running.

**Response:** `{ success: true, message: string }`

### DELETE /api/admin/discovery-jobs/{job_id}
Cancel a pending job or delete a completed/failed job. Running jobs cannot be deleted (returns 409).

**Response:** `{ success: true }`

---

## Tasks
Source: `apps/api/hephae_api/routers/admin/tasks.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/research/tasks` | Firebase Admin | List active tasks for specified businesses |
| POST | `/api/research/tasks/spawn` | Firebase Admin | Bulk spawn tasks into Cloud Tasks queue |
| POST | `/api/research/tasks/execute` | None (internal) | Execute a task (called by Cloud Tasks) |

> Note: Auth is applied per-route on this router. The `/execute` endpoint has no auth dependency because it is called internally by Cloud Tasks.

### GET /api/research/tasks
Fetch recent tasks for a list of businesses.

**Query params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `businessIds` | `string` | Yes | Comma-separated list of business IDs |

**Response:** `{ tasks: Task[] }` (with datetime fields serialized to ISO strings)

### POST /api/research/tasks/spawn
Bulk-create tasks and enqueue them in Cloud Tasks.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `businessIds` | `string[]` | Yes | Business IDs to spawn tasks for |
| `actionType` | `string` | Yes | Action type (e.g. `"ENRICH"`, `"ANALYZE_FULL"`, `"SEO_AUDIT"`) |
| `priority` | `int` | No | Priority level (default 5) |

**Response:** `{ success: true, count: int, taskIds: string[], enqueueFailed: int }`

### POST /api/research/tasks/execute
Internal endpoint called by Cloud Tasks to run the actual agent work. Supports `WORKFLOW_ANALYZE` (full enrichment + capability pipeline with retry logic) and dispatcher-planned workflows for other action types.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `businessId` | `string` | Yes | Target business ID |
| `actionType` | `string` | Yes | Action type |
| `taskId` | `string` | Yes | Task ledger entry ID |
| `metadata` | `dict \| null` | No | Additional metadata (retry info, source zip code, etc.) |

**Response:** `{ success: true, result: {...} }` or `{ success: true, plan: {...} }`

The `WORKFLOW_ANALYZE` pipeline performs:
1. Enrichment (profile data gathering)
2. Research context injection (area, zip code, sector, food pricing)
3. Context caching for Gemini
4. Capability execution (all enabled capabilities in parallel)
5. Result persistence to Firestore
6. Automatic retry with exponential backoff for retriable failures (429/503), up to 3 rounds

---

## Weekly Pulse
Source: `apps/api/hephae_api/routers/admin/weekly_pulse.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/weekly-pulse` | Firebase Admin | Submit pulse generation job (returns immediately) |
| GET | `/api/weekly-pulse/jobs/{job_id}` | Firebase Admin | Poll job status |
| GET | `/api/weekly-pulse` | Firebase Admin | List recent pulses |
| GET | `/api/weekly-pulse/{zip_code}/{business_type}/latest` | Firebase Admin | Latest pulse for a zip x business type |
| GET | `/api/weekly-pulse/{zip_code}/{business_type}/history` | Firebase Admin | Pulse history for a zip x business type |
| GET | `/api/weekly-pulse/id/{pulse_id}` | Firebase Admin | Get specific pulse by ID |
| DELETE | `/api/weekly-pulse/id/{pulse_id}` | Firebase Admin | Delete a pulse |

### POST /api/weekly-pulse
Submit a pulse generation job. Returns immediately with a jobId. Pipeline runs in background.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | 5-digit zip code |
| `businessType` | `string` | Yes | Business type |
| `weekOf` | `string` | No | ISO week (e.g. "2026-W13"), defaults to current week |
| `force` | `bool` | No | Force regeneration (default false) |
| `testMode` | `bool` | No | Test mode flag (default false) |

**Response:** `{ success: true, jobId: string, status: "QUEUED", testMode: bool }`

### GET /api/weekly-pulse/jobs/{job_id}
Poll job status. Returns full pulse when COMPLETED.

**Response:** Job status with `jobId`, `status` (QUEUED/RUNNING/COMPLETED/FAILED), `pulse` (when completed), `diagnostics`, `pipelineDetails`, `error` (when failed).

### GET /api/weekly-pulse
List all recent pulses across zip codes.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `20` | Max results (1-100) |
| `testMode` | `bool \| null` | `null` | Filter by test mode |

**Response:** `Pulse[]` (serialized)

### GET /api/weekly-pulse/{zip_code}/{business_type}/latest
Get the most recent pulse for a zip code + business type.

**Response:** Serialized pulse document

### GET /api/weekly-pulse/{zip_code}/{business_type}/history
Get historical pulses for a zip code + business type.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `8` | Max results (1-52) |

**Response:** `Pulse[]` (serialized)

### GET /api/weekly-pulse/id/{pulse_id}
Get a specific pulse by document ID.

**Response:** Serialized pulse document

### DELETE /api/weekly-pulse/id/{pulse_id}
Delete a specific pulse.

**Response:** `{ success: true }`

---

## Pulse Admin (Batch Monitoring)
Source: `apps/api/hephae_api/routers/admin/pulse_admin.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/weekly-pulse/batches` | Firebase Admin | List recent pulse batches with summary stats |
| GET | `/api/weekly-pulse/batches/{batch_id}` | Firebase Admin | Get detailed batch status |

### GET /api/weekly-pulse/batches
List recent pulse batches grouped by batchId from work items.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `20` | Max batch groups to return |

**Response:** `Batch[]` with `{ batchId, businessType, weekOf, totalItems, completed, failed, createdAt }`

### GET /api/weekly-pulse/batches/{batch_id}
Get detailed status for a specific batch, including per-zip status.

**Response:** Batch summary + `items[]` with `{ zipCode, status, lastError, hasSignals, hasSynthesis, critiquePass }`

---

## Registered Zipcodes
Source: `apps/api/hephae_api/routers/admin/registered_zipcodes.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/registered-zipcodes` | Firebase Admin | Register a new zipcode |
| GET | `/api/registered-zipcodes` | Firebase Admin | List all registered zipcodes |
| DELETE | `/api/registered-zipcodes/{zip_code}` | Firebase Admin | Unregister a zipcode |
| POST | `/api/registered-zipcodes/{zip_code}/pause` | Firebase Admin | Pause pulse generation |
| POST | `/api/registered-zipcodes/{zip_code}/resume` | Firebase Admin | Resume pulse generation |
| POST | `/api/registered-zipcodes/{zip_code}/approve` | Firebase Admin | Manually approve (onboard) a zipcode |
| POST | `/api/registered-zipcodes/{zip_code}/business-types` | Firebase Admin | Add a business type |
| DELETE | `/api/registered-zipcodes/{zip_code}/business-types/{biz_type}` | Firebase Admin | Remove a business type |
| GET | `/api/registered-zipcodes/cron-status` | Firebase Admin | Get cron status (active/paused counts, next run) |

### POST /api/registered-zipcodes
Register a new zipcode for weekly pulse generation. Resolves geography from BigQuery. Kicks off background zipcode profile discovery with auto-approval on success.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `zipCode` | `string` | Yes | 5-digit zip code |

**Response:** `{ success: true, id: string, city: string, state: string, county: string, discoveryStarted: true }`

### GET /api/registered-zipcodes
List all registered zipcodes, optionally filtered by status.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `string \| null` | `null` | `"active"` or `"paused"` |

**Response:** `RegisteredZipcode[]` (serialized)

### DELETE /api/registered-zipcodes/{zip_code}
Unregister a zipcode from weekly pulse generation.

**Response:** `{ success: true }`

### POST /api/registered-zipcodes/{zip_code}/pause
Pause weekly pulse generation for a zipcode.

**Response:** `{ success: true }`

### POST /api/registered-zipcodes/{zip_code}/resume
Resume weekly pulse generation for a zipcode.

**Response:** `{ success: true }`

### POST /api/registered-zipcodes/{zip_code}/approve
Human approval -- marks zip as onboarded.

**Response:** `{ success: true }`

### POST /api/registered-zipcodes/{zip_code}/business-types
Add a business type to a registered zipcode.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `businessType` | `string` | Yes | Business type to add |

**Response:** `{ success: true }`

### DELETE /api/registered-zipcodes/{zip_code}/business-types/{biz_type}
Remove a business type from a registered zipcode. Cannot remove the last business type.

**Response:** `{ success: true }`

### GET /api/registered-zipcodes/cron-status
Get weekly pulse cron status including active/paused counts, next scheduled run, and recent jobs.

**Response:**
```json
{
  "activeZipcodes": 5,
  "pausedZipcodes": 1,
  "nextRunAt": "2026-03-23T11:00:00Z",
  "schedule": "Every Monday 6:00 AM ET",
  "recentRuns": [{ "jobId": "...", "zipCode": "...", "status": "..." }]
}
```

---

## Zipcode Profiles
Source: `apps/api/hephae_api/routers/admin/zipcode_profiles.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/zipcode-profiles/discover/{zip_code}` | Firebase Admin | Trigger full discovery |
| GET | `/api/zipcode-profiles/{zip_code}` | Firebase Admin | View profile |
| GET | `/api/zipcode-profiles` | Firebase Admin | List all profiles |
| DELETE | `/api/zipcode-profiles/{zip_code}` | Firebase Admin | Delete profile |
| POST | `/api/zipcode-profiles/{zip_code}/refresh` | Firebase Admin | Re-run discovery |

### POST /api/zipcode-profiles/discover/{zip_code}
Trigger full two-phase discovery for a zip code. Runs synchronously (~60-90s).

**Response:** `{ success: true, zipCode: string, confirmedSources: int, unavailableSources: int, profile: object }`

### GET /api/zipcode-profiles/{zip_code}
View a single zipcode profile.

**Response:** Serialized profile document

### GET /api/zipcode-profiles
List all discovered zipcode profiles.

**Response:** `ZipcodeProfile[]` (serialized)

### DELETE /api/zipcode-profiles/{zip_code}
Delete a zipcode profile.

**Response:** `{ success: true }`

### POST /api/zipcode-profiles/{zip_code}/refresh
Re-run discovery for an existing zip code (full refresh).

**Response:** `{ success: true, zipCode: string, confirmedSources: int, unavailableSources: int, profile: object }`

---

## Registered Industries (NEW)
Source: `apps/api/hephae_api/routers/admin/registered_industries.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/registered-industries` | Firebase Admin | List all registered industries |
| POST | `/api/registered-industries` | Firebase Admin | Register a new industry |
| GET | `/api/registered-industries/{industry_key}` | Firebase Admin | Get a registered industry |
| DELETE | `/api/registered-industries/{industry_key}` | Firebase Admin | Unregister an industry |
| POST | `/api/registered-industries/{industry_key}/pause` | Firebase Admin | Pause an industry (skip in cron) |
| POST | `/api/registered-industries/{industry_key}/resume` | Firebase Admin | Resume a paused industry |
| POST | `/api/registered-industries/{industry_key}/generate-now` | Firebase Admin | Manually trigger an industry pulse |

### GET /api/registered-industries
List all registered industries, optionally filtered by status.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | `string \| null` | `null` | Filter by status (e.g. `"active"`) |

**Response:** `{ industries: RegisteredIndustry[] }`

### POST /api/registered-industries
Register a new industry for weekly national pulse generation. Validates that an `IndustryConfig` exists for the given key.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `industryKey` | `string` | Yes | Industry identifier (e.g. `"restaurant"`, `"bakery"`, `"barber"`) |
| `displayName` | `string` | Yes | Human-readable name |

**Response:** `{ success: true, industry: RegisteredIndustry }`

### GET /api/registered-industries/{industry_key}
Get a registered industry by key.

**Response:** Registered industry document

### DELETE /api/registered-industries/{industry_key}
Unregister an industry.

**Response:** `{ success: true }`

### POST /api/registered-industries/{industry_key}/pause
Pause an industry so it is skipped during the cron cycle.

**Response:** `{ success: true, status: "paused" }`

### POST /api/registered-industries/{industry_key}/resume
Resume a paused industry.

**Response:** `{ success: true, status: "active" }`

### POST /api/registered-industries/{industry_key}/generate-now
Manually trigger an industry pulse for the current week. Calls `generate_industry_pulse` with `force=True`.

**Response:**
```json
{
  "success": true,
  "pulseId": "string",
  "signalCount": 12,
  "playbooksMatched": 3,
  "trendSummary": "string (first 200 chars)"
}
```

---

# Batch / Cron Routers

All cron endpoints are authenticated via `CRON_SECRET` in the `X-Cron-Secret` or `Authorization` header (Bearer token).

---

## Cron: Run Analysis
Source: `apps/api/hephae_api/routers/batch/cron.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/run-analysis` | CRON_SECRET | Discover + outreach for a zip code |

### GET /api/cron/run-analysis
Scan a zip code for businesses and run outreach on the first 3. Legacy cron endpoint.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `zip` | `string` | `"10001"` | Zip code to scan |

**Response:** `{ success: true, report: [{ business: string, outreachSuccess: bool }] }`

---

## Cron: Heartbeat Cycle
Source: `apps/api/hephae_api/routers/batch/heartbeat_cron.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/heartbeat-cycle` | CRON_SECRET | Run all due heartbeat cycles |

### GET /api/cron/heartbeat-cycle
Run all due heartbeat cycles. Called by Cloud Scheduler weekly. Queries for due heartbeats and re-runs capabilities for each.

**Response:** `{ processed: int, emailed: int, skipped: int, details: [...] }`

---

## Cron: Workflow Monitor
Source: `apps/api/hephae_api/routers/batch/workflow_monitor.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/workflow-monitor` | CRON_SECRET | Check for terminal workflows, send digest email |

### GET /api/cron/workflow-monitor
Check for recently completed/failed workflows and send a digest email. Called by Cloud Scheduler every 30 minutes.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `window` | `int` | `30` | Lookback window in minutes |

**Response:** `{ digested: int, emailed: bool, completed: int, failed: int, paused: int }`

---

## Cron: Batch Workflows
Source: `apps/api/hephae_api/routers/batch/batch_workflows.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/cron/batch-workflows` | CRON_SECRET | Create workflows in QUEUED state for sequential processing |

### POST /api/cron/batch-workflows
Create workflows in QUEUED state for the workflow-dispatcher cron to pick up one at a time.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `jobs` | `dict[]` | Yes | Array of `{ zipCode: string, businessType: string }` |

**Response:** `{ total: int, queued: int, failed: int, results: [...] }`

---

## Cron: Workflow Dispatcher
Source: `apps/api/hephae_api/routers/batch/workflow_dispatcher.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/workflow-dispatcher` | CRON_SECRET | Start the next queued workflow |

### GET /api/cron/workflow-dispatcher
Start the next queued workflow if no workflow is currently active. Called by Cloud Scheduler every 5 minutes. Ensures only one workflow runs at a time by checking for active phases (discovery, qualification, analysis, evaluation, outreach).

**Response:** `{ dispatched: bool, workflowId: string, reason: string, remainingQueued: int }`

---

## Cron: Pulse Batch
Source: `apps/api/hephae_api/routers/batch/pulse_batch.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/cron/pulse-batch-submit` | Firebase Admin | Create batch work items + launch Cloud Run Job |
| GET | `/api/cron/pulse-batch-status/{batch_id}` | Firebase Admin | Check batch progress |

### POST /api/cron/pulse-batch-submit
Create work items for all zip codes in a county and launch a batch pulse job.

**Request body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `county` | `string` | Yes | County name |
| `state` | `string` | Yes | State name or code |
| `businessType` | `string` | Yes | Business type |
| `weekOf` | `string` | No | ISO week (defaults to current) |

**Response:** `{ success: true, batchId: string, zipCount: int, message: string }`

### GET /api/cron/pulse-batch-status/{batch_id}
Get batch progress summary.

**Response:** Batch summary object from `get_batch_summary`

---

## Cron: Weekly Pulse
Source: `apps/api/hephae_api/routers/batch/pulse_cron.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/weekly-pulse` | CRON_SECRET | Trigger weekly pulse generation for all active zipcodes |
| GET | `/api/cron/weekly-pulse/status` | CRON_SECRET | Get cron status |

### GET /api/cron/weekly-pulse
Trigger weekly pulse generation for all active registered zipcodes. Called by Cloud Scheduler every Monday at 6am ET (11:00 UTC). Idempotent -- skips zipcodes that already have a pulse for the current week. Stagers pulse generation 30 seconds apart to avoid rate limits. Sends summary email on completion.

**Response:** `{ triggered: int, skipped: int }`

### GET /api/cron/weekly-pulse/status
Get cron status -- which zipcodes are scheduled, last/next run times.

**Response:**
```json
{
  "activeZipcodes": 5,
  "pausedZipcodes": 1,
  "nextRunAt": "2026-03-23T11:00:00Z",
  "schedule": "Every Monday 6:00 AM ET",
  "zipcodes": [{ "zipCode": "...", "businessTypes": [...], "city": "...", "status": "..." }],
  "recentRuns": [{ "jobId": "...", "status": "..." }]
}
```

---

## Cron: Industry Pulse (NEW)
Source: `apps/api/hephae_api/routers/batch/industry_pulse_cron.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/cron/industry-pulse` | CRON_SECRET | Generate industry pulses for all active registered industries |

### GET /api/cron/industry-pulse
Generate national-level industry pulses for all active registered industries. Called by Cloud Scheduler every Sunday at 3:00 AM ET (08:00 UTC), BEFORE the zip-level pulse cron on Monday. Idempotent -- skips industries that already have a pulse for the current week. Sends summary email on completion.

Each industry pulse:
1. Fetches national signals (BLS CPI, USDA prices, FDA recalls)
2. Computes impact multipliers
3. Matches industry playbooks
4. Generates an LLM trend summary
5. Saves to Firestore (`industry_pulses` collection)

Zip-level pulses then load this pre-computed data instead of re-fetching national signals.

**Response:**
```json
{
  "success": true,
  "generated": 3,
  "failed": 0,
  "results": [
    {
      "industryKey": "restaurant",
      "displayName": "Restaurants & Cafes",
      "status": "generated",
      "pulseId": "string",
      "signalCount": 12,
      "playbooksMatched": 2,
      "trendPreview": "string (first 200 chars)"
    }
  ]
}
```

---

## Router Registration Summary

Registered in `apps/api/hephae_api/main.py` via `_register_routers()`:

### Admin Routers (21 routers)
| # | Router | Prefix | Source File |
|---|--------|--------|-------------|
| 1 | workflows | `/api/workflows` | `admin/workflows.py` |
| 2 | workflow_stream | `/api/workflows` | `admin/workflow_stream.py` |
| 3 | workflow_actions | `/api/workflows` | `admin/workflow_actions.py` |
| 4 | research_businesses | `/api/research` | `admin/research_businesses.py` |
| 5 | zipcode_research | `/api/zipcode-research` | `admin/zipcode_research.py` |
| 6 | area_research | `/api/area-research` | `admin/area_research.py` |
| 7 | sector_research | `/api/sector-research` | `admin/sector_research.py` |
| 8 | combined_context | `/api/combined-context` | `admin/combined_context.py` |
| 9 | stats | `/api/stats` | `admin/stats.py` |
| 10 | fixtures | `/api/fixtures` | `admin/fixtures.py` |
| 11 | test_runner | `/api/run-tests` | `admin/test_runner.py` |
| 12 | food_prices | `/api/food-prices` | `admin/food_prices.py` |
| 13 | content | `/api/content` | `admin/content.py` |
| 14 | discovery_jobs | `/api/admin/discovery-jobs` | `admin/discovery_jobs.py` |
| 15 | tasks | `/api/research/tasks` | `admin/tasks.py` |
| 16 | weekly_pulse | `/api/weekly-pulse` | `admin/weekly_pulse.py` |
| 17 | pulse_admin | `/api/weekly-pulse/batches` | `admin/pulse_admin.py` |
| 18 | registered_zipcodes | `/api/registered-zipcodes` | `admin/registered_zipcodes.py` |
| 19 | zipcode_profiles | `/api/zipcode-profiles` | `admin/zipcode_profiles.py` |
| 20 | registered_industries | `/api/registered-industries` | `admin/registered_industries.py` |

### Batch / Cron Routers (8 routers)
| # | Router | Path | Source File |
|---|--------|------|-------------|
| 1 | cron | `/api/cron/run-analysis` | `batch/cron.py` |
| 2 | heartbeat_cron | `/api/cron/heartbeat-cycle` | `batch/heartbeat_cron.py` |
| 3 | workflow_monitor | `/api/cron/workflow-monitor` | `batch/workflow_monitor.py` |
| 4 | batch_workflows | `/api/cron/batch-workflows` | `batch/batch_workflows.py` |
| 5 | workflow_dispatcher | `/api/cron/workflow-dispatcher` | `batch/workflow_dispatcher.py` |
| 6 | pulse_batch | `/api/cron/pulse-batch-*` | `batch/pulse_batch.py` |
| 7 | pulse_cron | `/api/cron/weekly-pulse` | `batch/pulse_cron.py` |
| 8 | industry_pulse_cron | `/api/cron/industry-pulse` | `batch/industry_pulse_cron.py` |
