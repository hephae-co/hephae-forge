# CLAUDE.md — Admin App (internal dashboard UI)

> Part of the hephae-forge monorepo. See `../../CLAUDE.md` for cross-app standards.

This is the internal admin dashboard UI. It proxies all `/api/*` requests to the unified backend at `apps/api/`.

## Architecture

- **Next.js 14.1** frontend only — no Python backend here
- All API calls proxy to the unified API service (`apps/api/`)
- Workflow engine, agents, and orchestrators are in `apps/api/hephae_api/workflows/`

## Commands

```bash
npm install && npm run dev          # Frontend (localhost:3000, proxies /api/* to unified API)
npm run build                       # Production build
npm run lint                        # ESLint
npm run test                        # Vitest unit tests
npm run test:e2e                    # Playwright E2E tests
```

## Tech Stack

- **Frontend:** Next.js 14.1 (App Router), TypeScript, Tailwind CSS
- **Path alias:** `@/*` maps to `./src/*`

## Multi-Agent Pipeline (5 workflow phases)

All phases run in the unified API (`apps/api/hephae_api/workflows/`):

1. **Discovery** — Scans zip codes for businesses (direct runner call)
2. **Enrichment** — Gets full profiles (direct runner call)
3. **Analysis** — Runs 4 capabilities directly (SEO, traffic, competitive, margin)
4. **Evaluation** — 4 QA evaluator agents validate outputs
5. **Approval** — Pauses for human review
6. **Outreach** — Formats content, sends via Resend email API

Note: Capabilities are now direct Python imports in the unified API — no HTTP calls between backends.
