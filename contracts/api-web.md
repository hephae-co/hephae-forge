# Web App API (published by `web/`)

> These are the endpoints that `admin/` calls. This file is the contract.
> When changing any endpoint, update this file in the same commit.
> The auto-generated `web/ADMIN_APP_API.md` has full type definitions.

## Base URL

```
# Local: http://localhost:3000
# Production: https://hephae-forge-1096334123076.us-east1.run.app
```

## Authentication

- **V1 endpoints:** `x-api-key` header
- **Capability endpoints:** HMAC-SHA256 via `x-forge-timestamp` + `x-forge-signature` headers
- **Secret:** `FORGE_API_SECRET` environment variable

---

## Discovery & Enrichment

### `POST /api/v1/discover`

Full 4-stage discovery pipeline. Returns enriched business profile.

```json
// Request
{ "query": "Bosphorus Nutley NJ" }

// Response
{ "success": true, "data": EnrichedProfile }
```

---

## Capability Endpoints

All accept `{ "identity": EnrichedProfile }` and return capability-specific reports.

### `POST /api/capabilities/seo`
Returns: `SeoReport` — `{ overallScore, summary, sections[], reportUrl }`

### `POST /api/capabilities/traffic`
Returns: `ForecastResponse` — `{ summary, forecast[], reportUrl }`

### `POST /api/capabilities/competitive`
Returns: `CompetitiveReport` — `{ market_summary, competitors[], recommendations[], reportUrl }`

### `POST /api/v1/analyze` (Margin Surgeon)
Accepts: `{ "identity": EnrichedProfile, "advancedMode": true }`
Returns: `SurgicalReport` — `{ identity, menu_items[], strategic_advice[], overall_score, reportUrl }`

---

## Data Flow

```
admin/                                web/
  |                                     |
  |  POST /api/v1/discover              |
  |  { name, address, docId }          |
  | ----------------------------------> |
  |  <- EnrichedProfile                 |
  |                                     |
  |  POST /api/capabilities/seo         |
  |  { identity: EnrichedProfile }      |
  | ----------------------------------> |
  |  <- SeoReport                       |
  |                                     |
  |  POST /api/capabilities/traffic     |
  | ----------------------------------> |
  |  <- ForecastResponse                |
  |                                     |
  |  POST /api/capabilities/competitive |
  | ----------------------------------> |
  |  <- CompetitiveReport               |
  |                                     |
  |  POST /api/v1/analyze               |
  | ----------------------------------> |
  |  <- SurgicalReport                  |
```
