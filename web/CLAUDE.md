# CLAUDE.md — Web App (customer-facing)

> Part of the hephae-forge monorepo. See `../CLAUDE.md` for cross-app standards.
> See `../contracts/` for shared schemas, API contracts, and eval standards.

This is the customer-facing product at hephae.co. It analyzes restaurants using AI agents and generates "Surgical Intelligence" reports.

## Core Architecture: The "High-Impact Funnel"

1. **Funnel (Gemini Flash):** Broad menu scraping and identity discovery. Picks the **Top 5 High-Volatility Items** (Beef, Poultry, Seafood, Eggs, Dairy) for deep analysis.
2. **Surgical Analysis (Gemini Pro):** Deep reasoning on those 5 items using USDA trends and neighborhood proxies.
3. **Data Layer:** Firestore as a **Zip Code Knowledge Graph** for cross-prospect caching.

## Tech Stack

- **Frontend:** Next.js 16 (React 19), TypeScript, Tailwind CSS v4
- **Backend:** FastAPI (Python 3.11+), Google ADK agents
- **Database:** Firebase/Firestore + BigQuery
- **Storage:** GCS (`everything-hephae` bucket)

## Commands

```bash
npm install && npm run dev          # Frontend (localhost:3000)
pip install -e . && uvicorn backend.main:app --reload  # Backend (localhost:8000)
npm run build                       # Production build
npm run test                        # Vitest
npm run test:integration            # Integration tests (5 levels, 97 tests)
```

## Model Configuration (`backend/config.py`)

See `../CLAUDE.md` for the full model tier table. This app's config:
- `AgentModels.PRIMARY`: All standard agents
- `AgentModels.ENHANCED`: SEO auditor
- `AgentModels.CREATIVE_VISION`: Image generation

## Deterministic Math Requirement

- **Never** perform arithmetic for "Annual Profit Leakage" or "Margin %" in LLM prompts.
- Extract variables into structured JSON, pipe to deterministic functions in `backend/math/`.

## The "Sassy Advisor" Persona

- **Tone:** Professional, data-backed, but provocative.
- **Focus:** Highlight the "Invisible Bleed" — the money the owner is losing right now.

## MCP Integration

`mcp-servers/market-truth` provides:
- `get_usda_wholesale_prices`: Live commodity costs
- `get_bls_cpi_data` / `get_fred_economic_indicators`: Macro trends
- `get_weather_hourly`: Hourly precipitation (Open-Meteo)
- `get_nearby_anchors`: Traffic anchors (OpenStreetMap Overpass API)

## Agent Versioning

See `../CLAUDE.md` for the versioning protocol. The `AgentVersions` map in `backend/config.py` is this app's source of truth. Every `writeAgentResult()` call must pass `agentVersion`.

## API Documentation

- `ADMIN_APP_API.md` in this directory has the full auto-generated API reference with TypeScript interfaces.
- Run `python scripts/sync-api-doc.py` to update from OpenAPI spec.
- Run `python scripts/sync-api-doc.py --check` in CI to detect staleness.
- Shared contract: `../contracts/api-web.md`

## Data Strategy

- Use `backend/lib/data/standard_recipes.json` for "Standard Industry Benchmarks" to estimate COGS without internal recipes.

## Proxy Reasoning

If Gemini Flash cannot find a specific competitor price, it provides a `Neighborhood Proxy`. Gemini Pro uses this to build a "Market Gravity" argument.
