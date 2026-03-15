# CLAUDE.md — Web App (customer-facing UI)

> Part of the hephae-forge monorepo. See `../../CLAUDE.md` for cross-app standards.

This is the customer-facing UI at hephae.co. It proxies all `/api/*` requests to the unified backend at `apps/api/`.

## Architecture

- **Next.js 16** (React 19) frontend only — no Python backend here
- All API calls proxy to the unified API service (`apps/api/`)
- Backend logic is in `apps/api/`, AI agents are in `agents/`

## Commands

```bash
npm install && npm run dev          # Frontend (localhost:3000)
npm run build                       # Production build
npm run test                        # Vitest
```

## Tech Stack

- **Frontend:** Next.js 16 (React 19), TypeScript, Tailwind CSS v4
- **Path alias:** `@/*` maps to `./src/*`

## The "Sassy Advisor" Persona

- **Tone:** Professional, data-backed, but provocative.
- **Focus:** Highlight the "Invisible Bleed" — the money the owner is losing right now.

## Deterministic Math Requirement

- **Never** perform arithmetic for "Annual Profit Leakage" or "Margin %" in LLM prompts.
- Extract variables into structured JSON, pipe to deterministic functions in `agents/hephae_agents/math/`.
