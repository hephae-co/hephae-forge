# BigQuery Schema

> Dataset: `hephae-co-dev.hephae`
> All tables are append-only. Historical data lives here; Firestore stores only current state.
> Writes use DML INSERT via `bqInsert()` — not streaming.

---

## `hephae.analyses`

One row per agent run. Written by `writeAgentResult()`.

| Column | Type | Description |
|---|---|---|
| `analysis_id` | STRING | `{agent_name}-{timestamp}` unique ID |
| `business_slug` | STRING | Matches Firestore doc ID |
| `business_name` | STRING | Human-readable name |
| `zip_code` | STRING | 5-digit zip, nullable |
| `agent_name` | STRING | `margin_surgeon`, `seo_auditor`, `traffic_forecaster`, `competitive_analyzer`, `social_profiler`, `discovery_reviewer`, `news_discovery`, `marketing_swarm` |
| `agent_version` | STRING | Semver from `AgentVersions` in config |
| `run_at` | TIMESTAMP | When the agent ran |
| `triggered_by` | STRING | `user`, `weekly_job`, or `api_v1` |
| `score` | FLOAT | 0-100 overall score, nullable |
| `summary` | STRING | One-line summary, nullable |
| `report_url` | STRING | GCS public URL to HTML report, nullable |
| `total_leakage` | FLOAT | Promoted KPI (margin_surgeon only) |
| `menu_item_count` | INT64 | Promoted KPI (margin_surgeon only) |
| `seo_technical_score` | FLOAT | Promoted KPI (seo_auditor only) |
| `seo_content_score` | FLOAT | Promoted KPI (seo_auditor only) |
| `seo_ux_score` | FLOAT | Promoted KPI (seo_auditor only) |
| `seo_performance_score` | FLOAT | Promoted KPI (seo_auditor only) |
| `seo_authority_score` | FLOAT | Promoted KPI (seo_auditor only) |
| `peak_slot_score` | FLOAT | Promoted KPI (traffic_forecaster only) |
| `competitor_count` | INT64 | Promoted KPI (competitive_analyzer only) |
| `avg_threat_level` | FLOAT | Promoted KPI (competitive_analyzer only) |
| `raw_data` | STRING | Full agent JSON output (never contains blobs) |

## `hephae.discoveries`

One row per discovery run. Written by `writeDiscovery()`.

| Column | Type | Description |
|---|---|---|
| `run_id` | STRING | `discovery-{timestamp}` |
| `business_slug` | STRING | Matches Firestore doc ID |
| `business_name` | STRING | Human-readable name |
| `official_url` | STRING | Business website URL |
| `address` | STRING | Full street address, nullable |
| `city` | STRING | Reserved for future use (currently null) |
| `state` | STRING | Reserved for future use (currently null) |
| `zip_code` | STRING | 5-digit zip, nullable |
| `lat` | FLOAT | Latitude, nullable |
| `lng` | FLOAT | Longitude, nullable |
| `agent_name` | STRING | Always `discovery_orchestrator` |
| `agent_version` | STRING | From `AgentVersions.DISCOVERY_PIPELINE` |
| `run_at` | TIMESTAMP | When discovery ran |
| `triggered_by` | STRING | `user`, `weekly_job`, or `api_v1` |
| `raw_data` | STRING | Full enriched profile JSON (blobs stripped) |

## `hephae.interactions`

CRM event log. Written by `writeInteraction()`.

| Column | Type | Description |
|---|---|---|
| `interaction_id` | STRING | `{event_type}-{slug}-{timestamp}` |
| `occurred_at` | TIMESTAMP | Event time |
| `business_slug` | STRING | Matches Firestore doc ID |
| `zip_code` | STRING | 5-digit zip, nullable |
| `event_type` | STRING | See event types below |
| `outreach_number` | INT64 | 1, 2, or 3 — only for outbound events |
| `contact_email` | STRING | Nullable |
| `subject` | STRING | Email subject line, nullable |
| `report_url` | STRING | Shared report URL, nullable |
| `responded` | BOOLEAN | True only for `contact_form` and `email_replied` |

**Event types:** `report_sent`, `follow_up_sent`, `email_opened`, `report_link_clicked`, `contact_form`, `email_replied`
