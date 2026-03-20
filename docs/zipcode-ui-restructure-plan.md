# Zipcode UI Restructure Plan

## Current State (Problems)

1. **No onboarding status** — Registered zipcodes have no concept of "onboarded" (discovery complete, ready for production). A zip registered 5 minutes ago looks identical to one that's been running weekly for months.

2. **Test and production runs are mixed** — Test mode pulses (24h TTL) and real weekly runs appear in the same list. An admin can't quickly see "what ran in production this week" vs "what I was testing yesterday."

3. **No run schedule visibility** — There's no view showing "these 5 zips will run Friday 6 AM" with their last run status. The cron status section exists but doesn't tie runs back to specific zip outcomes.

4. **Pulse list is zip-agnostic** — The Weekly Pulse sub-tab shows a flat list of all pulses across all zips. There's no way to see "show me all runs for 07110" without scrolling.

5. **Chat UI connection unclear** — Onboarded zips should be the same ones available in the customer-facing chat UI. This connection isn't modeled anywhere.

---

## Target State

### Zipcodes Tab — 3 Sub-tabs

```
Zipcodes (top-level tab)
├── Onboarded Zips (default sub-tab)
│   ├── Registration form (same as today)
│   ├── Onboarded zipcodes table
│   │   ├── Status: onboarding | onboarded | paused
│   │   ├── Last pulse date + headline preview
│   │   ├── Next scheduled run
│   │   ├── Pulse count
│   │   └── Actions: Run Now, Pause, View Latest, Unregister
│   └── Cron Schedule card (next run, active count)
│
├── Weekly Runs (sub-tab)
│   ├── Upcoming Runs section
│   │   └── List of active zips with next run date + last run status
│   ├── Latest Run Results section
│   │   └── Per-zip cards: headline, insight count, critique pass/fail
│   │   └── Click to expand → full pulse viewer
│   └── Run History (collapsible)
│       └── Filter by zip, date range
│       └── Paginated list of past production runs
│
└── Test Runs (sub-tab)
    ├── Generate Test Pulse form (zip + business type + test mode forced ON)
    ├── Active test jobs (polling status)
    └── Recent test results (24h TTL, auto-cleanup)
        └── Same pulse viewer but with "TEST" badge
```

---

## Data Model Changes

### 1. Onboarding Status on Registered Zipcodes

Add `onboardingStatus` field to `registered_zipcodes` collection:

```
{
  ...existing fields...
  "onboardingStatus": "onboarding" | "onboarded" | "failed",
  "onboardedAt": timestamp | null,
  "discoveryRunId": str | null,      // links to the initial discovery/first pulse
  "chatEnabled": true,               // available in customer chat UI
}
```

**Transition flow**:
1. `POST /api/registered-zipcodes` → creates doc with `onboardingStatus: "onboarding"`
2. First successful pulse (test or production) → sets `onboardingStatus: "onboarded"`, `onboardedAt: now`
3. Admin can manually toggle `chatEnabled`

**Why not require a separate "discovery" step?** The first pulse run IS the discovery — it fetches all 15 data sources, resolves geography, runs social pulse + local catalyst research. If it succeeds, the zip is onboarded.

### 2. Distinguish Test vs Production Runs

Already implemented via `testMode: true` + `expireAt` on pulse documents. Need to:
- Add `testMode` filter to the `list_pulses()` query
- Add `GET /api/weekly-pulse?testMode=false` filter param
- Frontend separates test vs production in different sub-tabs

### 3. Per-Zip Latest Pulse

Add endpoint: `GET /api/registered-zipcodes/with-latest-pulse`
- Returns registered zipcodes enriched with their latest non-test pulse headline + date
- Single query instead of N+1

---

## API Changes

### Modified Endpoints

| Endpoint | Change |
|----------|--------|
| `POST /api/registered-zipcodes` | Add `onboardingStatus: "onboarding"` to created doc |
| `GET /api/registered-zipcodes` | Add `onboardingStatus` to response |
| `GET /api/weekly-pulse` | Add `?testMode=true\|false` filter param |

### New Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/registered-zipcodes/with-latest-pulse` | Registered zips + latest production pulse per zip |
| `POST /api/registered-zipcodes/{zip}/{biz}/mark-onboarded` | Manual override to mark as onboarded |
| `POST /api/registered-zipcodes/{zip}/{biz}/toggle-chat` | Toggle chatEnabled flag |

### Auto-Onboarding Hook

In `_run_pulse_job()` (weekly_pulse.py router), after successful completion:
- Check if the zip's `onboardingStatus` is still `"onboarding"`
- If so, update to `"onboarded"` + set `onboardedAt`

---

## Frontend Changes

### Sub-tab 1: Onboarded Zips (default)

**Registration form** — same as today, no changes.

**Zipcodes table** — enhanced columns:

| Column | What |
|--------|------|
| Zip Code | Badge with zip + city name |
| Status | `onboarding` (yellow spinner), `onboarded` (green check), `paused` (amber) |
| Chat | Toggle switch for `chatEnabled` |
| Last Pulse | Headline preview + relative time ("2h ago") |
| Next Run | "Friday 6 AM" or "Paused" |
| Count | Total production pulse count |
| Actions | Run Now, Pause/Resume, View Latest, Unregister |

**Cron card** — keep existing, add "Next run in X hours" countdown.

### Sub-tab 2: Weekly Runs

**Upcoming Runs section**:
- Card per active zip showing: zip, city, business type, last run status (pass/fail), next scheduled date
- Green = last run passed critique, amber = last run had revisions, gray = never run

**Latest Results section**:
- After Friday cron runs, shows per-zip result cards:
  - Headline, insight count, local events count, critique verdict
  - "View Full Report" button → expands to full PulseViewer inline
- Most recent run per zip only (not historical)

**Run History** (collapsible or separate view):
- Filter: zip code dropdown, date range picker
- Table: zip, date, headline, insights, critique, actions (view/delete)
- Only shows `testMode: false` runs

### Sub-tab 3: Test Runs

**Generate form**:
- Same fields as today (zip, business type, date)
- `testMode` is forced ON (no toggle — this tab is always test mode)
- "Generate Test Pulse" button

**Active jobs**:
- Shows currently running test jobs with polling spinner + job ID
- Auto-removes when complete

**Recent test results**:
- Shows test pulses from last 24h
- Same PulseViewer component but with orange "TEST" banner
- Clear note: "Test data auto-deletes after 24 hours"

---

## Implementation Order

### Phase 1: Backend (30 min)
1. Add `onboardingStatus`, `onboardedAt`, `chatEnabled` fields to `register_zipcode()`
2. Add auto-onboarding hook in `_run_pulse_job()`
3. Add `testMode` filter to `list_pulses()` and `GET /api/weekly-pulse`
4. Add `GET /api/registered-zipcodes/with-latest-pulse` endpoint

### Phase 2: Frontend — Onboarded Zips sub-tab (1 hr)
5. Update zipcodes table with onboarding status badges + chat toggle
6. Enhance cron card with countdown

### Phase 3: Frontend — Weekly Runs sub-tab (1.5 hr)
7. Build Upcoming Runs section
8. Build Latest Results section with inline PulseViewer
9. Build Run History with filters

### Phase 4: Frontend — Test Runs sub-tab (1 hr)
10. Move test pulse generation here
11. Active jobs section with polling
12. Recent test results with TEST badge

### Phase 5: Wire sub-tabs (30 min)
13. Replace current 2 sub-tabs (Manage/Pulse) with 3 new ones
14. Migrate existing functionality into new structure

---

## What This Enables

1. **Clear onboarding flow**: Register → first pulse runs → auto-marked as "onboarded" → appears in chat UI
2. **Clean separation**: Test experiments in one tab, production results in another
3. **Schedule visibility**: "These 5 zips run Friday 6 AM, here's what happened last Friday"
4. **Per-zip focus**: Click a zip → see its history, latest pulse, upcoming run
5. **Chat UI connection**: `chatEnabled` flag controls which zips are available to end users
