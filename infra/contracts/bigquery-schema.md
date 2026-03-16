# BigQuery Schema
> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

**Dataset:** `{GCP_PROJECT_ID}.hephae`
**Project ID:** Set via `BIGQUERY_PROJECT_ID` or `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT` env var
**Write method:** DML INSERT (not streaming) via `bq_insert()` -- rows are immediately available for DML DELETE
**All tables are append-only.** Historical data lives here; Firestore stores only current state.

---

## Tables

### `hephae.discoveries`

Permanent record of every discovery agent run. One row per business discovered.

| Column | Type | Notes |
|---|---|---|
| `run_id` | `STRING` | Format: `discovery-{timestamp_ms}` |
| `business_slug` | `STRING` | URL slug of the business |
| `business_name` | `STRING` | Business name |
| `official_url` | `STRING` | Primary website URL |
| `address` | `STRING` | Full street address |
| `city` | `STRING` | City (currently always `null`) |
| `state` | `STRING` | State (currently always `null`) |
| `zip_code` | `STRING` | Zip code |
| `lat` | `FLOAT64` | Latitude |
| `lng` | `FLOAT64` | Longitude |
| `agent_name` | `STRING` | Always `discovery_orchestrator` |
| `agent_version` | `STRING` | Semantic version (e.g., `5.0.0`) |
| `run_at` | `TIMESTAMP` | When the discovery ran |
| `triggered_by` | `STRING` | `user` or `batch` |
| `raw_data` | `STRING` | JSON-serialized enriched profile (blobs stripped) |

| Property | Value |
|---|---|
| **Written by** | `lib/db/hephae_db/firestore/discovery.py` :: `write_discovery()` |
| **Write trigger** | Discovery agent completes enrichment of a business |
| **Fire-and-forget** | Yes -- BQ write runs in executor, failures logged but never block |

---

### `hephae.analyses`

Permanent history of all analysis agent outputs. One row per agent run per business.

| Column | Type | Notes |
|---|---|---|
| `analysis_id` | `STRING` | Format: `{agent_name}-{timestamp_ms}` |
| `business_slug` | `STRING` | URL slug of the business |
| `business_name` | `STRING` | Business name |
| `zip_code` | `STRING` | Zip code |
| `agent_name` | `STRING` | Agent key (e.g., `seo_auditor`, `margin_surgeon`, `traffic_forecaster`, `competitive_analyzer`) |
| `agent_version` | `STRING` | Semantic version from `AgentVersions` |
| `run_at` | `TIMESTAMP` | When the analysis ran |
| `triggered_by` | `STRING` | `user`, `batch`, or `workflow` |
| `score` | `FLOAT64` | Overall agent score (nullable) |
| `summary` | `STRING` | Agent summary text (nullable) |
| `report_url` | `STRING` | GCS/CDN URL to HTML report (nullable) |
| `total_leakage` | `FLOAT64` | Promoted KPI: margin surgeon total leakage (nullable) |
| `menu_item_count` | `INT64` | Promoted KPI: margin surgeon menu item count (nullable) |
| `seo_technical_score` | `FLOAT64` | Promoted KPI: SEO technical section score (nullable) |
| `seo_content_score` | `FLOAT64` | Promoted KPI: SEO content section score (nullable) |
| `seo_ux_score` | `FLOAT64` | Promoted KPI: SEO UX section score (nullable) |
| `seo_performance_score` | `FLOAT64` | Promoted KPI: SEO performance section score (nullable) |
| `seo_authority_score` | `FLOAT64` | Promoted KPI: SEO authority section score (nullable) |
| `peak_slot_score` | `FLOAT64` | Promoted KPI: traffic forecaster peak slot score (nullable) |
| `competitor_count` | `INT64` | Promoted KPI: competitive analyzer competitor count (nullable) |
| `avg_threat_level` | `FLOAT64` | Promoted KPI: competitive analyzer avg threat level (nullable) |
| `raw_data` | `STRING` | JSON-serialized full agent output (nullable) |

| Property | Value |
|---|---|
| **Written by** | `lib/db/hephae_db/firestore/agent_results.py` :: `write_agent_result()` |
| **Write trigger** | Any analysis agent completes a run |
| **KPI promotion** | `_extract_promoted_kpis()` pulls agent-specific metrics into top-level columns for efficient querying |
| **Fire-and-forget** | Yes -- BQ write runs in executor, failures logged but never block |

---

### `hephae.interactions`

Event log of all outreach and inbound response events.

| Column | Type | Notes |
|---|---|---|
| `interaction_id` | `STRING` | Format: `{event_type}-{business_slug}-{timestamp_ms}` |
| `occurred_at` | `TIMESTAMP` | Event timestamp |
| `business_slug` | `STRING` | Target business slug |
| `zip_code` | `STRING` | Zip code (nullable) |
| `event_type` | `STRING` | Event type: `report_sent`, `follow_up_sent`, `contact_form`, `email_replied` |
| `outreach_number` | `INT64` | Outreach attempt number (nullable) |
| `contact_email` | `STRING` | Email address used (nullable) |
| `subject` | `STRING` | Email subject line (nullable) |
| `report_url` | `STRING` | URL of shared report (nullable) |
| `responded` | `BOOL` | `true` if event is a genuine response (`contact_form` or `email_replied`) |

| Property | Value |
|---|---|
| **Written by** | `lib/db/hephae_db/firestore/interactions.py` :: `write_interaction()` |
| **Write trigger** | Outreach email sent, follow-up sent, or inbound response received |
| **Fire-and-forget** | Yes -- BQ write runs in executor, failures logged but never block |

---

### `hephae.agent_feedback`

Structured feedback signals from every agent run -- used by the learning cycle for pattern extraction.

| Column | Type | Notes |
|---|---|---|
| `feedback_id` | `STRING` | Format: `{agent_name}-{business_slug}-{unix_seconds}` |
| `business_slug` | `STRING` | Target business slug |
| `agent_name` | `STRING` | Agent name (e.g., `seo_auditor`, `crawl4ai`, `approval_gate`) |
| `agent_version` | `STRING` | Semantic version (nullable) |
| `capability` | `STRING` | Capability name (e.g., `seo`, `margin`, `discovery`, `approval`) |
| `zip_code` | `STRING` | Zip code (nullable) |
| `business_type` | `STRING` | Business type/industry (nullable) |
| `recorded_at` | `TIMESTAMP` | When feedback was recorded |
| `eval_score` | `FLOAT64` | Evaluator score (nullable) |
| `is_hallucinated` | `BOOL` | Evaluator hallucination flag (nullable) |
| `human_decision` | `STRING` | `approve` or `reject` (nullable) |
| `auto_approved` | `BOOL` | Whether approval was automatic (nullable) |
| `crawl_strategy` | `STRING` | Crawl strategy used (nullable) |
| `crawl_success` | `BOOL` | Whether crawl succeeded (nullable) |
| `crawl_content_length` | `INT64` | Crawled content length in bytes (nullable) |
| `crawl_duration_ms` | `INT64` | Crawl duration in milliseconds (nullable) |
| `site_platform` | `STRING` | Detected site platform (e.g., `wix`, `squarespace`, `wordpress`) (nullable) |
| `run_duration_ms` | `INT64` | Agent run duration in milliseconds (nullable) |

| Property | Value |
|---|---|
| **Written by** | `lib/db/hephae_db/bigquery/feedback.py` :: `record_feedback()` and convenience wrappers |
| **Read by** | `lib/db/hephae_db/bigquery/feedback_reader.py` -- aggregate queries for learning cycle |
| **Convenience wrappers** | `record_evaluation_feedback()`, `record_approval_feedback()`, `record_crawl_feedback()`, `record_run_feedback()` |

---

## External Datasets (Read-Only)

### `bigquery-public-data.google_trends.top_terms`

| Column | Type | Notes |
|---|---|---|
| `term` | `STRING` | Search term |
| `rank` | `INT64` | Rank within DMA |
| `score` | `FLOAT64` | Relative search interest |
| `week` | `DATE` | Week of data |
| `dma_name` | `STRING` | DMA region name |
| `refresh_date` | `DATE` | Data refresh date |

### `bigquery-public-data.google_trends.top_rising_terms`

| Column | Type | Notes |
|---|---|---|
| `term` | `STRING` | Search term |
| `percent_gain` | `FLOAT64` | Percentage increase in search interest |
| `rank` | `INT64` | Rank within DMA |
| `score` | `FLOAT64` | Relative search interest |
| `week` | `DATE` | Week of data |
| `dma_name` | `STRING` | DMA region name |
| `refresh_date` | `DATE` | Data refresh date |

| Property | Value |
|---|---|
| **Read by** | `lib/db/hephae_db/bigquery/reader.py` :: `query_google_trends()`, `query_industry_trends()` |
| **Filter** | Data within last 3 days of refresh, filtered by DMA name |
| **Industry keywords** | Mapped in `INDUSTRY_KEYWORDS` dict (bakeries, restaurants, laundromats, etc.) |

---

## Feedback Reader Queries

The `feedback_reader.py` module provides aggregate analytics over `agent_feedback`:

| Function | Groups by | Returns |
|---|---|---|
| `get_approval_rates_by_industry()` | `business_type` | `{business_type, total, approved, rejected, approval_rate}` |
| `get_approval_rates_by_zip()` | `zip_code` | `{zip_code, total, approved, approval_rate}` |
| `get_crawl_success_by_platform()` | `site_platform, crawl_strategy` | `{site_platform, crawl_strategy, total, successes, success_rate, avg_content_length, avg_duration_ms}` |
| `get_eval_score_distribution()` | `capability, agent_name` | `{capability, agent_name, avg_score, median_score, min_score, max_score, total, hallucination_rate}` |
| `get_agent_run_durations()` | `agent_name, capability` | `{agent_name, capability, avg_duration_ms, p50_duration_ms, p95_duration_ms, total}` |
| `get_feedback_summary()` | *(none)* | `{total_rows, unique_businesses, avg_eval_score, hallucination_rate, approval_rate, crawl_success_rate, avg_run_duration_ms}` |

Source: `lib/db/hephae_db/bigquery/feedback_reader.py`
