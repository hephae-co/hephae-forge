# Firestore Schema
> Auto-generated from codebase on 2026-03-22. Do not edit manually.

All client access is denied (`allow read, write: if false`). All reads/writes happen server-side via the `hephae-db` package.

---

## Core Collections

### `businesses`

| Property | Description |
|---|---|
| **Document ID** | URL slug derived from business name (e.g., `joes-pizza`) |
| **Source files** | `lib/db/hephae_db/firestore/businesses.py`, `lib/db/hephae_db/firestore/discovery.py`, `lib/db/hephae_db/firestore/agent_results.py`, `lib/db/hephae_db/firestore/interactions.py` |

| Field | Type | Written by | Notes |
|---|---|---|---|
| `name` | `string` | `discovery.write_discovery` | Business name |
| `address` | `string` | `discovery.write_discovery` | Full street address |
| `officialUrl` | `string` | `discovery.write_discovery` | Primary website URL |
| `zipCode` | `string` | `discovery.write_discovery`, `agent_results.write_agent_result` | **First-class field** -- always top-level, never derived at query time |
| `coordinates` | `map{lat, lng}` | `discovery.write_discovery` | Latitude/longitude |
| `category` | `string` | queried by `businesses._get_businesses_paginated_sync` | Business category (e.g., "restaurant") |
| `businessType` | `string` | `fixtures.save_fixture_from_business` (read) | Alias for category in some contexts |
| `discoveryStatus` | `string` | queried by `stats`, `businesses` | Values: `scanned`, `discovered`, `analyzed` |
| `workflowId` | `string` | queried by `businesses.get_businesses_for_workflow` | Links business to its workflow |
| `phone` | `string` | `discovery.write_discovery` | Phone number |
| `email` | `string` | `discovery.write_discovery` | Contact email |
| `hours` | `string` | `discovery.write_discovery` | Operating hours |
| `googleMapsUrl` | `string` | `discovery.write_discovery` | Google Maps link |
| `socialLinks` | `map` | `discovery.write_discovery` | `{instagram, facebook, twitter, yelp, tiktok, ...}` |
| `logoUrl` | `string` | `discovery.write_discovery` | Logo image URL |
| `favicon` | `string` | `discovery.write_discovery` | Favicon URL |
| `primaryColor` | `string` | `discovery.write_discovery` | Brand primary color |
| `secondaryColor` | `string` | `discovery.write_discovery` | Brand secondary color |
| `persona` | `string` | `discovery.write_discovery` | AI-generated brand persona |
| `menuUrl` | `string` | `discovery.write_discovery` | Menu page URL |
| `menuScreenshotUrl` | `string` | `discovery.write_discovery` | GCS URL for menu screenshot |
| `menuHtmlUrl` | `string` | `discovery.write_discovery` | GCS URL for menu HTML |
| `competitors` | `array<map>` | `discovery.write_discovery` | `[{name, url, reason}]` |
| `socialProfileMetrics` | `map` | `discovery.write_discovery` | Per-platform social metrics |
| `news` | `array<map>` | `discovery.write_discovery` | `[{title, url, source, date, snippet}]` |
| `aiOverview` | `map` | `discovery.write_discovery` | AI-generated business summary |
| `validationReport` | `map` | `discovery.write_discovery` | URL validation stats |
| `identity` | `map` | `discovery.write_discovery` | Duplicate of enriched fields (kept for backward compat) |
| `latestOutputs` | `map` | `agent_results.write_agent_result` | Keyed by agent name (e.g., `latestOutputs.seo_auditor`) |
| `latestOutputs.{agent}` | `map` | `agent_results.write_agent_result` | `{score, summary, reportUrl, agentVersion, runAt, ...kpis}` |
| `crm` | `map` | `interactions.write_interaction`, `interactions.archive_business` | CRM state object |
| `crm.outreachCount` | `integer` | `interactions.write_interaction` | Number of outreach attempts |
| `crm.status` | `string` | `interactions.write_interaction`, `interactions.archive_business` | Values: `outreached`, `responded`, `archived` |
| `crm.lastOutreachAt` | `timestamp` | `interactions.write_interaction` | Last outreach timestamp |
| `crm.lastReportShared` | `string` | `interactions.write_interaction` | URL of last shared report |
| `crm.respondedAt` | `timestamp` | `interactions.write_interaction` | When business responded |
| `crm.archivedAt` | `timestamp` | `interactions.archive_business` | When business was archived |
| `crm.archiveReason` | `string` | `interactions.archive_business` | Reason for archiving |
| `createdAt` | `timestamp` | `discovery.write_discovery` (SERVER_TIMESTAMP) | Document creation time |
| `updatedAt` | `timestamp` | `discovery.write_discovery`, `agent_results.write_agent_result`, `interactions.write_interaction` | Last modification time |

### `workflows`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/workflows.py` |
| **Pydantic model** | `WorkflowDocument` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Same as document ID |
| `zipCode` | `string` | Primary zip code |
| `businessType` | `string \| null` | Target business type |
| `county` | `string \| null` | County name (if resolved from county) |
| `zipCodes` | `array<string> \| null` | All zip codes in scope |
| `resolvedFrom` | `"single" \| "county"` | How zip codes were determined |
| `phase` | `string` | `WorkflowPhase` enum: `queued`, `discovery`, `qualification`, `analysis`, `evaluation`, `approval`, `outreach`, `completed`, `failed` |
| `createdAt` | `timestamp` | Workflow creation time |
| `updatedAt` | `timestamp` | Last state change |
| `businesses` | `array<map>` | Embedded `BusinessWorkflowState` objects (see below) |
| `progress` | `map` | `WorkflowProgress` counters (see below) |
| `lastError` | `string \| null` | Last error message |
| `retryCount` | `integer` | Number of retries |

**`businesses[]` (BusinessWorkflowState):**

| Field | Type | Notes |
|---|---|---|
| `slug` | `string` | Business document ID |
| `name` | `string` | Business name |
| `address` | `string` | Address |
| `officialUrl` | `string` | Website URL |
| `sourceZipCode` | `string` | Originating zip code |
| `businessType` | `string` | Category |
| `phase` | `string` | `BusinessPhase` enum: `pending`, `enriching`, `analyzing`, `analysis_done`, `evaluating`, `evaluation_done`, `approved`, `rejected`, `outreaching`, `outreach_done`, `outreach_failed` |
| `capabilitiesCompleted` | `array<string>` | List of completed capability keys |
| `capabilitiesFailed` | `array<string>` | List of failed capability keys |
| `evaluations` | `map<string, EvaluationResult>` | `{score, isHallucinated, issues[]}` per capability |
| `qualityPassed` | `boolean` | Whether evaluation passed threshold |
| `enrichedProfile` | `map \| null` | Cached enriched profile data |
| `insights` | `map \| null` | `{summary, keyFindings[], recommendations[], generatedAt}` |
| `outreachError` | `string \| null` | Outreach failure message |
| `lastError` | `string \| null` | Last error for this business |

**`progress` (WorkflowProgress):**

| Field | Type | Notes |
|---|---|---|
| `totalBusinesses` | `integer` | Total businesses in workflow |
| `qualificationQualified` | `integer \| null` | Businesses that passed qualification |
| `qualificationParked` | `integer \| null` | Businesses parked during qualification |
| `qualificationDisqualified` | `integer \| null` | Businesses disqualified |
| `analysisComplete` | `integer` | Businesses with analysis done |
| `evaluationComplete` | `integer` | Businesses with evaluation done |
| `qualityPassed` | `integer` | Businesses passing quality threshold |
| `qualityFailed` | `integer` | Businesses failing quality threshold |
| `approved` | `integer` | Businesses approved for outreach |
| `outreachComplete` | `integer` | Businesses with outreach sent |
| `insightsComplete` | `integer \| null` | Businesses with insights generated |
| `zipCodesScanned` | `integer \| null` | Zip codes scanned so far |
| `zipCodesTotal` | `integer \| null` | Total zip codes to scan |

### `tasks`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/tasks.py` |

| Field | Type | Notes |
|---|---|---|
| `businessId` | `string` | Business slug this task targets |
| `actionType` | `string` | Action type (e.g., `enrich`, `analyze`, `outreach`) |
| `status` | `string` | `queued`, `running`, `completed`, `failed`, `retry_queued` |
| `progress` | `integer` | Progress percentage (0-100) |
| `triggeredBy` | `string` | Who triggered the task (default: `admin`) |
| `priority` | `integer` | Task priority (default: 5) |
| `createdAt` | `timestamp` | Task creation time |
| `startedAt` | `timestamp \| null` | When task began executing |
| `completedAt` | `timestamp \| null` | When task finished |
| `metadata` | `map` | Arbitrary task metadata |
| `error` | `string \| null` | Error message on failure |

---

## Pulse Collections

### `zipcode_weekly_pulse`

| Property | Description |
|---|---|
| **Document ID** | `{zipCode}-{businessTypeSlug}-{YYYYMMDD}-{HHmmss}` |
| **Source file** | `lib/db/hephae_db/firestore/weekly_pulse.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | 5-digit zip code |
| `businessType` | `string` | Business type (e.g., "Restaurants") |
| `weekOf` | `string` | ISO date string for the week |
| `pulse` | `map` | Full pulse briefing object (`{headline, insights[], ...}`) |
| `signalsUsed` | `array<string>` | List of signal source names used |
| `diagnostics` | `map` | Pipeline diagnostics and timing data |
| `pipelineDetails` | `map \| null` | Detailed pipeline execution info |
| `testMode` | `boolean \| null` | If `true`, document is test data |
| `expireAt` | `timestamp \| null` | Firestore TTL -- auto-deletes test docs after 24h |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |

### `pulse_jobs`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/pulse_jobs.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | Target zip code |
| `businessType` | `string` | Target business type |
| `weekOf` | `string` | ISO date for the week |
| `force` | `boolean` | Whether to force regeneration |
| `status` | `string` | `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED` |
| `createdAt` | `timestamp` | Job creation time |
| `startedAt` | `timestamp \| null` | When job began executing |
| `completedAt` | `timestamp \| null` | When job finished |
| `timeoutAt` | `timestamp \| null` | Auto-fail deadline (15 min); checked on read |
| `result` | `map \| null` | Result data on completion |
| `error` | `string \| null` | Error message on failure |
| `testMode` | `boolean \| null` | If `true`, test mode (24h TTL via `expireAt`) |
| `expireAt` | `timestamp \| null` | Firestore TTL for test jobs |

**Auto-timeout:** `get_pulse_job()` checks `timeoutAt` on RUNNING jobs and marks them FAILED if exceeded.

### `industry_pulses`

| Property | Description |
|---|---|
| **Document ID** | `{industryKey}-{weekOf}` (e.g., `bakeries-2026-03-17`) |
| **Source file** | `lib/db/hephae_db/firestore/industry_pulse.py` |

| Field | Type | Notes |
|---|---|---|
| `industryKey` | `string` | Normalized industry identifier (e.g., `bakeries`) |
| `weekOf` | `string` | ISO date for the week |
| `nationalSignals` | `map` | National-level signal data |
| `nationalImpact` | `map` | Impact assessment at national level |
| `nationalPlaybooks` | `array<map>` | Recommended action playbooks |
| `trendSummary` | `string` | AI-generated trend narrative |
| `signalsUsed` | `array<string>` | List of signal source names used |
| `diagnostics` | `map` | Pipeline diagnostics |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |

### `registered_industries`

| Property | Description |
|---|---|
| **Document ID** | `{industryKey}` (e.g., `bakeries`) |
| **Source file** | `lib/db/hephae_db/firestore/registered_industries.py` |

| Field | Type | Notes |
|---|---|---|
| `industryKey` | `string` | Normalized industry identifier |
| `displayName` | `string` | Human-readable name (e.g., "Bakeries") |
| `status` | `string` | `active` or `paused` |
| `registeredAt` | `timestamp` | When the industry was registered |
| `lastPulseAt` | `timestamp \| null` | Timestamp of last successful pulse |
| `lastPulseId` | `string \| null` | Doc ID of last industry pulse |
| `pulseCount` | `integer` | Total pulses generated (uses `Increment`) |
| `createdBy` | `string` | Creator (default: `admin`) |

### `registered_zipcodes`

| Property | Description |
|---|---|
| **Document ID** | `{zipCode}` (e.g., `07110`) |
| **Source file** | `lib/db/hephae_db/firestore/registered_zipcodes.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | 5-digit zip code |
| `businessTypes` | `array<string>` | Business types to generate pulses for (default: `["Restaurants"]`). Uses `ArrayUnion`/`ArrayRemove`. |
| `city` | `string` | City name |
| `state` | `string` | State code |
| `county` | `string` | County name |
| `status` | `string` | `active` or `paused` |
| `onboardingStatus` | `string` | `onboarding` or `onboarded` |
| `onboardedAt` | `timestamp \| null` | When onboarding completed |
| `registeredAt` | `timestamp` | Registration time |
| `lastPulseAt` | `timestamp \| null` | Timestamp of last successful pulse |
| `lastPulseId` | `string \| null` | Doc ID of last pulse |
| `lastPulseHeadline` | `string` | Headline from last pulse |
| `lastPulseInsightCount` | `integer` | Number of insights in last pulse |
| `pulseCount` | `integer` | Total pulses generated (uses `Increment`) |
| `nextScheduledAt` | `timestamp` | Next Monday 06:00 ET (11:00 UTC) |
| `createdBy` | `string` | Creator (default: `admin`) |

### `pulse_batch_work_items`

| Property | Description |
|---|---|
| **Document ID** | `{batchId}:{zipCode}` (e.g., `pulse-essex-2026-W12:07110`) |
| **Source file** | `lib/db/hephae_db/firestore/pulse_batch.py` |

| Field | Type | Notes |
|---|---|---|
| `batchId` | `string` | Parent batch identifier |
| `zipCode` | `string` | Target zip code |
| `businessType` | `string` | Target business type |
| `weekOf` | `string` | ISO week string |
| `status` | `string` | `QUEUED`, `FETCHING`, `RESEARCH`, `PRE_SYNTHESIS`, `SYNTHESIS`, `CRITIQUE`, `COMPLETED`, `FAILED` |
| `retryCount` | `integer` | Number of retries |
| `lastError` | `string \| null` | Last error message |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |
| `expireAt` | `timestamp` | Firestore TTL -- auto-deletes after 14 days |

### `pulse_signal_archive`

| Property | Description |
|---|---|
| **Document ID** | `{zipCode}-{weekOf}` (e.g., `07110-2026-W12`) |
| **Source file** | `lib/db/hephae_db/firestore/signal_archive.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | 5-digit zip code |
| `weekOf` | `string` | ISO week string |
| `collectedAt` | `timestamp` | When signals were collected |
| `sources` | `map` | Dict of `source_name` to `{raw, fetchedAt, version}` |
| `preComputedImpact` | `map \| null` | Pre-computed impact multipliers |

### `data_cache`

| Property | Description |
|---|---|
| **Document ID** | `{source}:{scopeKey}` (e.g., `census:07110`, `fda:NJ`, `qcew:34031-2024-Q1`) |
| **Source file** | `lib/db/hephae_db/firestore/data_cache.py` |

| Field | Type | Notes |
|---|---|---|
| `source` | `string` | Data source name (e.g., `census`, `fda`, `qcew`) |
| `scopeKey` | `string` | Scope identifier (zip code, state code, county FIPS) |
| `data` | `map` | Cached API response data |
| `fetchedAt` | `timestamp` | Cache write time |
| `ttlDays` | `integer` | Configured TTL in days |
| `expiresAt` | `timestamp` | Computed expiry time (checked on read) |

**TTL tiers:** `TTL_STATIC` = 90d (Census, FHFA, IRS, CDC, OSM), `TTL_SHARED` = 30d (QCEW, FBI, FDA, EIA, USDA), `TTL_WEEKLY` = 7d (NWS, news, trends, CPI, SBA), `TTL_DAILY` = 1d (reserved).

### `zipcode_profiles`

| Property | Description |
|---|---|
| **Document ID** | `{zipCode}` (e.g., `07110`) |
| **Source file** | `lib/db/hephae_db/firestore/zipcode_profiles.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | 5-digit zip code |
| `discoveredAt` | `timestamp` | When the profile was discovered |
| `refreshAfter` | `timestamp` | When the profile should be re-discovered |
| `...` | `any` | Additional fields from the capability registry manifest (sources, capabilities, etc.) |

---

## Research Collections

### `zipcode_research`

| Property | Description |
|---|---|
| **Document ID** | `{zipCode}-{YYYYMMDDHHmmss}` or legacy `{zipCode}` |
| **Source file** | `lib/db/hephae_db/firestore/research.py` |
| **Pydantic model** | `ZipCodeResearchDocument` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `zipCode` | `string` | The researched zip code |
| `report` | `map` | `ZipCodeReport` object with `summary`, `sections`, `sources`, etc. |
| `report.summary` | `string` | Executive summary |
| `report.sections` | `map` | `{geography, demographics, census_housing, business_landscape, economic_indicators, consumer_market, infrastructure, trending, events, seasonal_weather}` |
| `report.sources` | `array<map>` | `[{short_id, title, url, domain}]` |
| `createdAt` | `timestamp` | Research run time |
| `updatedAt` | `timestamp` | Last update time |

### `area_research`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/research.py` |
| **Pydantic model** | `AreaResearchDocument` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Same as document ID |
| `area` | `string` | Area name (e.g., county name) |
| `businessType` | `string` | Target business type |
| `areaKey` | `string` | Normalized `{area}-{businessType}` slug |
| `resolvedCountyName` | `string \| null` | Resolved county name |
| `resolvedState` | `string \| null` | Resolved state |
| `zipCodes` | `array<string>` | All zip codes in area |
| `completedZipCodes` | `array<string>` | Successfully researched zip codes |
| `failedZipCodes` | `array<string>` | Failed zip codes |
| `phase` | `string` | `AreaResearchPhase`: `resolving`, `researching`, `industry_intel`, `local_sector_analysis`, `synthesizing`, `completed`, `failed` |
| `summary` | `map \| null` | `AreaResearchSummary` with marketOpportunity, demographicFit, competitiveLandscape, etc. |
| `industryIntel` | `map \| null` | `IndustryIntelligence` data |
| `localSectorInsights` | `map \| null` | Local sector trend data |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |
| `lastError` | `string \| null` | Last error message |

### `sector_research`

| Property | Description |
|---|---|
| **Document ID** | Normalized `{sector}-{areaName}` slug (e.g., `restaurants-cook-county`) |
| **Source file** | `lib/db/hephae_db/firestore/research.py` |
| **Pydantic model** | `SectorResearchDocument` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Same as document ID |
| `sector` | `string` | Industry sector name |
| `zipCodes` | `array<string>` | Zip codes analyzed |
| `areaName` | `string \| null` | Geographic area name |
| `phase` | `string` | `SectorResearchPhase`: `analyzing`, `local_trends`, `synthesizing`, `completed`, `failed` |
| `summary` | `map \| null` | `SectorResearchSummary` with industryAnalysis, localTrends, synthesis |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |
| `lastError` | `string \| null` | Last error message |

### `combined_contexts`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/combined_context.py` |
| **Pydantic model** | `CombinedContext` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `sourceRunIds` | `array<string>` | IDs of zipcode_research runs that were combined |
| `sourceZipCodes` | `array<string>` | Zip codes included |
| `context` | `map` | `CombinedContextData`: `{summary, keySignals[], demographicHighlights[], marketGaps[], trendingTerms[]}` |
| `createdAt` | `timestamp` | Creation time |

---

## Other Collections

### `users`

| Property | Description |
|---|---|
| **Document ID** | Firebase Auth UID |
| **Source file** | `lib/db/hephae_db/firestore/users.py` |

| Field | Type | Notes |
|---|---|---|
| `email` | `string \| null` | User email |
| `displayName` | `string \| null` | User display name |
| `photoURL` | `string \| null` | Profile photo URL |
| `createdAt` | `timestamp` | First login time |
| `lastLoginAt` | `timestamp` | Updated on every login |
| `businesses` | `array<string>` | List of business slugs owned by this user (uses `ArrayUnion` for adds) |

### `heartbeats`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/heartbeats.py` |

| Field | Type | Notes |
|---|---|---|
| `uid` | `string` | Owner user ID |
| `businessSlug` | `string` | Watched business slug |
| `businessName` | `string` | Business display name |
| `capabilities` | `array<string>` | Capability keys to run (e.g., `["seo_auditor", "traffic_forecaster"]`) |
| `frequency` | `string` | Always `"weekly"` |
| `dayOfWeek` | `integer` | 0=Mon through 6=Sun |
| `active` | `boolean` | Whether heartbeat is enabled |
| `createdAt` | `timestamp` | Creation time |
| `lastRunAt` | `timestamp \| null` | Last execution time |
| `nextRunAfter` | `timestamp` | When scheduler should next fire |
| `lastSnapshot` | `map` | Results from last run (may contain `deltas` key) |
| `totalRuns` | `integer` | Counter (uses `Increment`) |
| `consecutiveOks` | `integer` | Consecutive runs with no deltas (uses `Increment`, resets to 0 on delta) |

**Unique constraint:** One heartbeat per `uid` + `businessSlug` (enforced in application code).

### `test_fixtures`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/fixtures.py` |
| **Pydantic model** | `TestFixture` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `fixtureType` | `string` | `grounding` or `failure_case` |
| `isGoldStandard` | `boolean` | If true, syncs to Vertex AI Example Store |
| `sourceWorkflowId` | `string` | Originating workflow ID |
| `sourceZipCode` | `string \| null` | Source zip code |
| `businessType` | `string \| null` | Business type |
| `savedAt` | `timestamp` | When fixture was saved |
| `notes` | `string \| null` | Human notes |
| `businessState` | `map` | Snapshot of `BusinessWorkflowState` |
| `identity` | `map` | `{name, address, email, officialUrl, category, socialLinks, competitors, menuData, coordinates, docId}` |
| `latestOutputs` | `map` | Snapshot of all agent outputs |
| `agentKey` | `string \| null` | Specific agent this fixture targets |
| `agentOutput` | `map \| null` | Output for `agentKey` if specified |

### `discovery_jobs`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/discovery_jobs.py` |

| Field | Type | Notes |
|---|---|---|
| `name` | `string` | Human-readable job name |
| `status` | `string` | `pending`, `running`, `review_required`, `outreach_pending`, `completed`, `failed`, `cancelled` |
| `targets` | `array<map>` | List of target descriptors (zip codes, categories, etc.) |
| `progress` | `map` | `{totalZips, completedZips, totalBusinesses, qualified, skipped, failed}` |
| `createdAt` | `timestamp` | Job creation time |
| `startedAt` | `timestamp \| null` | When job began executing |
| `completedAt` | `timestamp \| null` | When job finished |
| `createdBy` | `string` | Creator (default: `admin`) |
| `notifyEmail` | `string` | Email for completion notification |
| `settings` | `map` | `{freshnessDiscoveryDays, freshnessAnalysisDays, rateLimitSeconds}` |
| `skipReasons` | `array<string>` | Sampled skip reasons (max 50, uses `ArrayUnion`) |
| `error` | `string \| null` | Error message on failure |

**Transactional claim:** `claim_next_pending_job` uses a Firestore transaction to atomically set `status=running`.

### `content_posts`

| Property | Description |
|---|---|
| **Document ID** | Auto-generated Firestore ID |
| **Source file** | `lib/db/hephae_db/firestore/content.py` |
| **Pydantic model** | `ContentPost` in `lib/common/hephae_common/models.py` |

| Field | Type | Notes |
|---|---|---|
| `id` | `string` | Same as document ID |
| `type` | `string` | `social` or `blog` |
| `platform` | `string` | `x`, `instagram`, `facebook`, `blog` |
| `status` | `string` | `draft`, `published`, `failed` |
| `sourceType` | `string` | `zipcode_research`, `area_research`, `combined_context` |
| `sourceId` | `string` | ID of source research document |
| `sourceLabel` | `string` | Human-readable source label |
| `content` | `string` | Post body text |
| `title` | `string \| null` | Title (for blog posts) |
| `hashtags` | `array<string>` | Hashtag list |
| `publishedAt` | `timestamp \| null` | Publication timestamp |
| `createdAt` | `timestamp` | Creation time |
| `updatedAt` | `timestamp` | Last update time |
| `platformPostId` | `string \| null` | ID from the publishing platform |
| `error` | `string \| null` | Publishing error message |

### `food_price_cache`

| Property | Description |
|---|---|
| **Document ID** | `{source}_{industry}` or `usda_{industry}_{state}` |
| **Source file** | `lib/db/hephae_db/firestore/food_prices.py` |

| Field | Type | Notes |
|---|---|---|
| `source` | `string` | Data source (`bls` or `usda`) |
| `industry` | `string` | Industry category |
| `state` | `string` | US state (USDA only) |
| `data` | `map` | Cached API response data |
| `fetchedAt` | `timestamp` | Cache write time (TTL: 24 hours) |

### `test_runs`

| Property | Description |
|---|---|
| **Document ID** | `runId` from the test summary |
| **Source file** | `lib/db/hephae_db/firestore/test_runs.py` |

| Field | Type | Notes |
|---|---|---|
| `runId` | `string` | Test run identifier |
| `createdAt` | `timestamp` | Run start time |
| `...` | `any` | All fields from the test summary dict are spread into the document |

**TTL:** Documents older than 7 days are lazily deleted on list/read.

### `adk_sessions`

| Property | Description |
|---|---|
| **Document ID** | UUID (auto-generated or caller-provided) |
| **Source file** | `lib/db/hephae_db/firestore/session_service.py` |

| Field | Type | Notes |
|---|---|---|
| `appName` | `string` | ADK application name |
| `userId` | `string` | User identifier |
| `state` | `map` | Agent session state (arbitrary key-value) |
| `updatedAt` | `timestamp` | Last state update |
| `deleteAt` | `timestamp` | TTL expiry: 24h for guests, 30d for logged-in users |
| `isPermanent` | `boolean` | `true` for logged-in users, `false` for guests |

**Heavy field pruning:** `prune_session()` removes `state.rawSiteData`, `state.markdown`, `state.html`, `state.screenshot_base64`, `state.gemini_cache_name` using `DELETE_FIELD`.

---

## Database Rules

1. **No blobs in Firestore or BigQuery** -- upload binary assets to GCS, store only the resulting URL. The `strip_blobs()` function in `discovery.py` enforces this for menu screenshots.
2. **`zipCode` is first-class** -- always a top-level field on `businesses` documents, never derived from address at query time. Both `write_discovery` and `write_agent_result` set it.
3. **No growing arrays in Firestore** -- no `reports[]`, no `analyses[]`. Historical agent results go to BigQuery (`hephae.analyses`). Firestore stores only `latestOutputs.{agent}` (current state).
4. **Use `update()` with dotted paths** for nested fields (e.g., `crm.status`, `latestOutputs.seo_auditor`, `state.{key}`). `set({merge:True})` is used only for new document creation in `discovery.write_discovery` and `businesses.save_business`.
