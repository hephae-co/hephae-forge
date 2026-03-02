# CLAUDE.md

This file provides guidance to any LLM (including Claude 3.5 Sonnet) working on this project as a reference for the latest Hephae Forge architecture.

## Model Strategy (Gemini-First)

This project standardizes on **Google Gemini 2.5** for all core operations:
- **Gemini 2.5 Flash:** High-volume "workhorse" tasks (Scraping, OCR, Discovery, Initial Profiler).
- **Gemini 2.5 Pro:** Strategic synthesis and deep reasoning (Surgeon, Advisor, SEO Auditor).

## Core Architecture: The "High-Impact Funnel"

The pipeline follows a strict sequence to generate high-conviction "Surgical Intelligence" reports:
1.  **Funnel (Gemini Flash):** Broad menu scraping and identity discovery. It picks the **Top 5 High-Volatility Items** (Beef, Poultry, Seafood, Eggs, Dairy) for deep analysis.
2.  **Surgical Analysis (Gemini Pro):** Deep reasoning on those 5 items using USDA trends and neighborhood proxies.
3.  **Data Layer:** Firestore is used as a **Zip Code Knowledge Graph** for cross-prospect caching.

## Deterministic Math Requirement
- **Arithmetic Prohibition:** Do not perform calculations for "Annual Profit Leakage" or "Margin %" within the prompt. 
- **Action:** Extract the necessary variables (Prospect Price, Commodity Cost, Neighborhood Average) into a structured JSON. 
- **Logic:** These variables are piped into deterministic TypeScript functions in `src/lib/math/`. Your job is to interpret the *result* of those calculations.

## Model Configuration (`src/agents/config.ts`)
- `DEFAULT_FAST_MODEL` (Gemini 2.5 Flash): Scraping, Discovery, Vision.
- `STRATEGIC_LOGIC_MODEL` (Gemini 2.5 Pro): Surgeon, Advisor, SEO Auditor.
- `DEEP_ANALYST_MODEL` (Gemini 2.5 Pro): Complex SEO/Market positioning.

## MCP Integration
`mcp-servers/market-truth` provides:
- `get_usda_wholesale_prices`: Live commodity costs.
- `get_bls_cpi_data` / `get_fred_economic_indicators`: Macro trends.
- `get_weather_hourly`: Hourly precipitation probability (via Open-Meteo).
- `get_nearby_anchors`: Traffic anchors (via OpenStreetMap Overpass API).

## The "Sassy Advisor" Persona
- **Tone:** Professional, data-backed, but provocative and "sassy."
- **Focus:** Highlight the "Invisible Bleed"—the money the owner is losing right now.
- **Example:** "You're essentially giving away a free burger for every table of four on Friday nights. Here is the math to stop the bleed."

## Handling Gaps
- **Proxy Reasoning:** If Gemini Flash cannot find a specific competitor price, it provides a `Neighborhood Proxy`. Gemini Pro must use this to build a "Market Gravity" argument. "You are $3.00 under the neighborhood average for this zip code."

## Data Strategy
- Use `src/lib/data/standard_recipes.json` for "Standard Industry Benchmarks" to estimate COGS without internal recipes.

## Database Rules (strictly enforced)

### No blobs in Firestore or BigQuery
Never write binary data to Firestore or BigQuery. This includes:
- `menuScreenshotBase64` or any base64-encoded image
- Raw HTML report content
- Any logo, favicon, or image buffer
Always upload binary assets to GCS first (`everything-hephae` bucket), then store only the resulting `https://storage.googleapis.com/everything-hephae/...` URL.

### Agent Versioning — mandatory on breaking changes
Every agent definition in `src/agents/` has an `agentVersion` string in `src/agents/config.ts` under `AgentVersions`. When making any of the following changes to an agent, you MUST increment its semantic version:
- Adding, removing, or renaming output fields
- Changing the JSON schema of the agent's output
- Changing the agent's model tier (e.g. Flash → Pro)
- Splitting one agent into two or merging two agents

Version format: `MAJOR.MINOR.PATCH`
- MAJOR: output schema change (fields added/removed/renamed)
- MINOR: logic change, same schema
- PATCH: prompt wording, no logic change

The `AgentVersions` map in `src/agents/config.ts` is the single source of truth. Every call to `writeAgentResult()` must pass `agentVersion: AgentVersions.AGENT_NAME`.

### Zip code is a first-class field
Always parse and store `zipCode` as an explicit top-level field — never derive it from the address string at query time. This applies to both Firestore `businesses/{slug}` and all BigQuery tables. The weekly analysis pipeline operates at zipcode granularity.

### Firestore document size
The `businesses/{slug}` top-level document must never contain arrays that grow over time (no `reports[]`, no `analyses[]`). All historical data lives in BigQuery. Firestore stores only current state via `latestOutputs.{agentName}` map keys.

### Keep `ADMIN_APP_API.md` in sync
`ADMIN_APP_API.md` is the external contract for the Hephae Admin App. When you change any of the following, you MUST update `ADMIN_APP_API.md` in the same commit:
- API request/response shapes (any route under `src/app/api/`)
- Firestore document schema (`businesses/{slug}`, `hub_searches/{id}`)
- BigQuery table columns (`analyses`, `discoveries`, `interactions`)
- TypeScript interfaces in `src/agents/types.ts` or `src/lib/types.ts`
- Agent registry entries or version keys in `src/agents/config.ts`
- GCS path conventions in `src/lib/reportStorage.ts`
