# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev       # Start Next.js dev server
npm run build     # Production build
npm run start     # Start production server
npm run lint      # Run ESLint
```

There is no test runner command — tests are run via API endpoints in `src/app/api/tests/` or directly executed as TypeScript scripts in `src/tests/`.

## Required Environment Variables

```
GEMINI_API_KEY=   # Google Gemini API key (required for all agents)
```

Additional variables for Firebase, SerpAPI, and other integrations may be needed depending on the feature being developed.

## Architecture

This is a **Next.js 16 App Router** application with a multi-agent AI backend powered by **Google ADK** (`@google/adk`) and **Gemini models**.

### Agent Framework

All agents live in `src/agents/` and are built using Google ADK patterns:
- **`LlmAgent`** — conversational agents with system instructions and tools
- **`ParallelAgent`** — runs sub-agents concurrently and merges session state
- **`SequentialAgent`** — chains agents where output of one feeds the next
- **`FunctionTool`** — wraps deterministic functions as agent-callable tools
- Agents write results to `InMemorySessionService` via `outputKey`; callers read state back from the session after the `Runner` completes

### Model Configuration (`src/agents/config.ts`)

Three model tiers are defined here:
- `DEFAULT_FAST_MODEL` — `gemini-2.5-flash` (most agents)
- `DEEP_ANALYST_MODEL` — `gemini-2.5-pro` (SEO auditor, competitive analyzer)
- `CREATIVE_VISION_MODEL` — `gemini-3-pro-image-preview` (marketing visuals)

Always import models from `config.ts` rather than hardcoding strings.

### MCP Integration

`src/agents/mcpClient.ts` connects via stdio transport to `mcp-servers/market-truth/build/index.js` — a custom Node.js MCP server that exposes economic data tools (`get_usda_wholesale_prices`, `get_bls_cpi_data`, `get_fred_economic_indicators`). The Benchmarker and CommodityWatchdog agents use this.

### Core User Flow

```
User query → /api/chat (LocatorAgent, Google Search)
  → BaseIdentity resolved
  → /api/discover (ParallelAgent: menu scraper + social + competitors + maps)
  → EnrichedProfile ready, 4 capability buttons unlock in UI
  → User picks capability:
      /api/analyze          → VisionIntake → Benchmarker → CommodityWatchdog → Surgeon → Advisor
      /api/capabilities/traffic → POI + Weather + Events agents → heatmap
      /api/capabilities/seo → SeoAuditorAgent (deep analysis, 5 categories)
      /api/capabilities/competitive → CompetitorProfiler → MarketPositioning
```

### API Routes

Long-running routes (`/api/analyze`, `/api/capabilities/*`) set `export const maxDuration = 60` for Vercel deployment.

### Agent Output Convention

Agents are instructed to return **strict JSON only** (no markdown fences). API routes use regex cleanup (`/```json\n?|\n?```/g`) before `JSON.parse()` to handle LLM slippage. Follow this pattern when adding new agents.

### Type System

- `src/lib/types.ts` — shared frontend/API types (`BaseIdentity`, `EnrichedProfile`, `SurgicalReport`, `SeoReport`, etc.)
- `src/agents/types.ts` — agent-specific types (`MenuItem`, `MenuAnalysisItem`, `CommodityTrend`, etc.)

### UI

`src/app/page.tsx` is a large client component that owns the full session state (chat messages, enriched profile, all analysis results). It passes data down to dashboard components in `src/components/Chatbot/`. Feature access is gated by an email capture wall (`EmailWall.tsx`) with localStorage persistence.

### Browser Automation

Playwright (chromium) is used inside Next.js API routes (server-side) to screenshot restaurant menus. Screenshots are returned as base64 and passed to the VisionIntakeAgent.
