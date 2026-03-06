# Changelog — Breaking Changes

> Log breaking changes here so both apps stay aware.
> Format: date, what changed, which app(s) affected.

---

## 2026-03-06 — Monorepo restructure

- Merged `hephae-admin` into this repo as `admin/`
- Moved all forge code into `web/`
- Created `packages/common-python/` and `packages/common-ts/` (stubs, extraction TODO)
- Created `contracts/` with shared schemas extracted from `web/ADMIN_APP_API.md` and `admin/docs/FORGE_REQUIREMENTS.md`
