# Comprehensive Code Review — All Systems
Generated: 2026-03-22

## Summary

| Area | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Pulse Pipeline | 3 | 4 | 6 | 5 | 18 |
| Chatbot + Overview | 4 | 5 | 8 | 10 | 27 |
| Infrastructure + Data | 4 | 7 | 8 | 7 | 26 |
| **Total** | **11** | **16** | **22** | **22** | **71** |

---

## CRITICAL ISSUES (11)

### Pulse Pipeline
1. **Module-level agents reused across invocations** — `pulse_data_gatherer.py` exports module-level LlmAgent instances that violate ADK "one parent" rule. Will crash on second pulse run in same process.
2. **Signal fetch exceptions swallowed silently** — `asyncio.gather(*coros, return_exceptions=True)` catches all exceptions but only logs them. Synthesis proceeds with incomplete data unaware of failures.
3. **Playbook format strings reference non-existent variables** — `{closed_street}`, `{delivery_adoption_pct}`, `{trending_term}` have no corresponding computed values. Silent template failures.

### Chatbot + Overview
4. **20+ `as any` casts in page.tsx** — destroys TypeScript type safety across the main page component.
5. **`asyncio.gather` without `return_exceptions=True`** in overview runner — one failed data load kills the entire overview.
6. **Race condition in capability execution** — no guard prevents multiple simultaneous capability runs. User can trigger 2+ APIs at once.
7. **No wall-clock timeout on ADK overview pipeline** — if LLM hangs, request hangs until Cloud Run 540s timeout.

### Infrastructure
8. **Unprotected cron status endpoint** — `GET /api/cron/weekly-pulse/status` reveals active zipcodes, job results, errors without auth.
9. **Ephemeral crawl4ai instances may leak** — if discovery crashes, Cloud Run service is never destroyed. Orphaned services accumulate costs.
10. **Firestore timestamp deserialization inconsistency** — `pulse_jobs.py` checks 3 different timestamp formats; mismatch causes timeout detection to fail silently. Jobs hang indefinitely.
11. **Email notification fire-and-forget** — cron returns 200 before email sends. If email fails, no one knows.

---

## HIGH PRIORITY FIXES (Top 15)

| # | Issue | File | Fix | Effort |
|---|-------|------|-----|--------|
| 1 | Module-level agents | pulse_data_gatherer.py | Remove module-level instances, only export instruction builders | 30 min |
| 2 | Cron status auth | pulse_cron.py:287 | Add `if cron_token != Bearer...` check | 5 min |
| 3 | Race condition in capabilities | page.tsx:618 | Add `if (isTyping \|\| isDiscovering) return;` guard | 5 min |
| 4 | `asyncio.gather` crash | runner.py:215 | Add `return_exceptions=True`, handle None results | 10 min |
| 5 | Orphaned crawl4ai cleanup | ephemeral.py | Add cleanup cron to delete services >1h old | 1 hour |
| 6 | Broken playbook variables | pulse_playbooks.py:45 | Remove playbooks with non-computed variables | 30 min |
| 7 | Signal fetch visibility | pulse_fetch_tools.py:304 | Log each failed signal with source name | 15 min |
| 8 | Missing pre-synthesis validation | weekly_pulse_agent.py | Check macroReport/localReport exist before synthesis | 30 min |
| 9 | DMA mapping incomplete | weekly_pulse.py:87 | Add all 50 US states or use dynamic lookup | 30 min |
| 10 | JSON truncation corrupts data | pulse_domain_experts.py:76 | Limit records then re-serialize instead of char slice | 30 min |
| 11 | Dead code: OverviewCard.tsx | OverviewCard.tsx | Delete file (230 lines unused) | 5 min |
| 12 | Unbounded Firestore query | registered_zipcodes.py:107 | Add `.limit(1000)` | 5 min |
| 13 | BigQuery no timeout | public_data.py:37 | Add query timeout config | 15 min |
| 14 | Banned phrase enforcement | pulse_critique_agent.py:87 | Add deterministic post-critique scan | 30 min |
| 15 | Email recipient validation | email.py:137 | Add email format regex check | 10 min |

---

## MEDIUM ISSUES (selected)

- **InsightMerger 40-char dedup** too aggressive — distinct insights with similar titles get merged
- **Max 8 insights hardcoded** — not configurable per business type
- **Pulse history loads 12 docs** but only uses 2-3 — wasteful Firestore reads
- **BLS API v2→v1 fallback** silent — no warning when data quality degrades
- **Session state not persisted** across page refreshes — users lose everything on reload
- **Missing loading state** for zipcode validation — users don't know it's checking
- **Firebase project ID hardcoded** in Dockerfile — can't deploy to different GCP projects
- **Crawl4ai auth token** cached without expiry verification — edge case 401 errors
- **No missed cron run detection** — if scheduler is disabled, no alert

---

## QUICK WINS (can fix in 1 hour)

1. Add auth to cron status endpoint (5 min)
2. Add capability execution guard (5 min)
3. Delete OverviewCard.tsx (5 min)
4. Add `return_exceptions=True` to overview gather (10 min)
5. Add `.limit(1000)` to Firestore queries (5 min)
6. Add email validation regex (10 min)
7. Log signal fetch failures with source names (15 min)
