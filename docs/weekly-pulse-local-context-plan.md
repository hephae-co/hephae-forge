# Weekly Pulse — Local Context Gap & Restructure Plan

## Problem Statement

The pipeline captures rich local data but the final output is dominated by generic macro analysis. Specific local context gets lost in synthesis.

### Evidence (07110 Nutley, NJ — March 19, 2026 run)

**What the pipeline captured (rich local data):**

| Source | Local Data Found |
|--------|-----------------|
| Social Pulse | Italian Language Exchange at **Aromi Di Napoli** (246 Washington Ave, Sat 3/21), Chamber of Commerce mixer at All Glass NJ (Thu 3/26), specific restaurants: The Oakley, Cucina 355, Luna Wood Fire Tavern shifting to spring event bookings |
| Local News | 3 Bing articles about Nutley-specific developments |
| Local Scout | Correctly references Aromi Di Napoli event, spring menu transitions, private event bookings season starting |
| OSM Density | 10 restaurants within 1500m — specific POI data available |
| Weather | 70% rain Friday after 8pm, 60°F Saturday, 27°F tonight |
| Google Trends | DMA-level search trends for New York metro |
| Census | $95K median income, 28K population, 4.4% poverty rate |
| BLS CPI | 19 price series, dairy +1.05% MoM, pork +1.42%, seafood -4.33% |
| CDC PLACES | 33.3% short sleep, healthy profile |
| IRS SOI | $112K avg AGI, 18.7% self-employment rate |

**What made it into the 5 insights (mostly generic):**

| Insight | Local? | Problem |
|---------|--------|---------|
| "Cut pork and dairy to save margins" | No | Pure BLS number crunching — any restaurant in any zip gets this |
| "Launch Sleepless Saturday specials" | Partial | References CDC sleep data + Aromi event, but the connection is forced |
| "Pivot to delivery at 7:30 PM Friday" | Partial | Weather is local but the recommendation is generic |
| "Audit supply chain against FDA recalls" | No | State-level FDA data, nothing Nutley-specific |
| "Shift from processed to fresh vegetables" | No | BLS + QCEW, zero local context |

**Root cause:** The synthesis prompt treats local and macro data equally. Given 15 signals, the LLM takes the path of least resistance — BLS numbers are clean, structured, and easy to write about. Local context (social pulse text, news articles, competitor names) requires more effort to weave in, so the LLM skips it.

---

## Solution: Structured Output with Forced Local Sections

### Current Schema (flat)

```
WeeklyPulseOutput:
  headline: str
  insights: PulseInsight[]     ← LLM fills this with whatever's easiest (macro)
  quickStats: PulseQuickStats
```

### Proposed Schema (sectioned)

```
WeeklyPulseOutput:
  headline: str

  localBriefing:                      ← NEW: forced local section
    thisWeekInTown: LocalEvent[]      ← Events, openings, closures THIS week
    competitorWatch: CompetitorNote[] ← What nearby businesses are doing
    communityBuzz: str                ← 2-3 sentence summary of social chatter
    governmentWatch: str              ← Planning board, permits, road work

  insights: PulseInsight[]            ← Cross-signal analysis (now explicitly macro+local)
  quickStats: PulseQuickStats
```

**New sub-schemas:**

```python
class LocalEvent:
    what: str          # "Italian Language Exchange at Aromi Di Napoli"
    where: str         # "246 Washington Ave"
    when: str          # "Saturday March 21, 10am"
    businessImpact: str  # "Foot traffic boost for morning hours on Washington Ave"
    source: str        # "NJBulletin.com via Social Pulse"

class CompetitorNote:
    business: str      # "Luna Wood Fire Tavern"
    observation: str   # "Shifting marketing to spring private event bookings"
    implication: str   # "Private event demand is rising — consider adding a catering page"
    source: str        # "Social Pulse research"
```

### Why This Works

1. **Forced structure** — The LLM can't skip local data because `localBriefing` is a required section with required sub-fields. Empty = schema validation failure.

2. **Separation of concerns** — Local context (events, competitors, community) lives in `localBriefing`. Cross-signal analysis (BLS + Census + weather = actionable insight) lives in `insights`. No more competition for space.

3. **Different quality bars** — `localBriefing` is judged on specificity (named venues, dates, addresses). `insights` is judged on cross-signal reasoning (2+ data sources, quantified impact). The critique agent scores them differently.

4. **Frontend layout** — Admin UI shows `localBriefing` as a "This Week in [Town]" card at the top (before insights), making local context the first thing the user sees.

---

## Multi-Agent Pipeline (Updated)

```
PulseOrchestrator (SequentialAgent)
│
├─ Stage 1: DataGatherer (ParallelAgent)
│  ├─ BaseLayerFetcher (custom BaseAgent — deterministic, no LLM)
│  │   ├─ 15+ API/BQ data sources with cache-through
│  │   ├─ Computes pre-computed impact multipliers (Python math)
│  │   └─ Matches strategy playbooks
│  └─ ResearchFanOut (ParallelAgent)
│     ├─ SocialPulseResearch (LlmAgent + google_search)
│     │   → Searches Reddit, Patch, TapInto, X for local chatter
│     └─ LocalCatalystResearch (LlmAgent + google_search + crawl4ai)
│         → Searches town council agendas, planning board, grants
│
├─ Stage 2: PreSynthesis (ParallelAgent)
│  ├─ PulseHistorySummarizer (LlmAgent)
│  │   → Reads last 12 weeks of pulse history for trend detection
│  │   → output_key: "trendNarrative"
│  ├─ EconomistAgent (LlmAgent)
│  │   → Reads: BLS, Census, IRS, SBA, QCEW, Trends, CDC, FHFA
│  │   → output_key: "macroReport"
│  └─ LocalScoutAgent (LlmAgent)
│      → Reads: weather, news, social pulse, catalysts, legal notices
│      → output_key: "localReport"
│
├─ Stage 3: DualModelSynthesis (custom BaseAgent)
│  │
│  │  Both models receive the SAME context:
│  │  - macroReport, localReport, trendNarrative
│  │  - preComputedImpact (31 variables)
│  │  - matchedPlaybooks
│  │  - rawSignals (for detail lookups)
│  │
│  ├─ Gemini Flash (gemini-3-flash-preview + HIGH thinking)
│  │   → Produces: localBriefing + insights (structured JSON)
│  ├─ Claude Sonnet 4 (via Anthropic Messages API)
│  │   → Produces: localBriefing + insights (structured JSON)
│  └─ Combiner (deterministic Python)
│      ├─ localBriefing: merge events (dedupe by venue+date),
│      │   merge competitor notes, pick richer communityBuzz
│      ├─ insights: merge all, dedupe by title, keep higher score
│      └─ Cap at 8 insights, re-rank by impactScore
│
├─ Stage 4: CritiqueLoop (LoopAgent, max_iterations=2)
│  ├─ PulseCritiqueAgent (LlmAgent)
│  │   → TWO critique passes:
│  │   │
│  │   │  Pass A: Local Briefing Quality
│  │   │  - Are events specific? (venue name, date, address)
│  │   │  - Are competitor notes about NAMED businesses?
│  │   │  - Is communityBuzz based on actual social data?
│  │   │
│  │   │  Pass B: Insight Quality (existing 3 tests)
│  │   │  - Obviousness (< 30 to pass)
│  │   │  - Actionability (>= 70 to pass)
│  │   │  - Data density (>= 60 to pass)
│  │   │
│  │   └─ If any fail → writes rewriteFeedback to state
│  │
│  ├─ CritiqueRouter (custom BaseAgent — deterministic)
│  │   → escalate on pass, write feedback on fail
│  └─ WeeklyPulseAgent (rewrite mode)
│      → Revises only failing sections/insights
│
└─ Stage 5: Save to Firestore + archive raw signals
   ├─ zipcode_weekly_pulse: final output + pipeline details
   ├─ pulse_signal_archive: raw signals for retroactive recomputation
   └─ pulse_jobs: job status for async polling
```

---

## Data Flow Example (07110 Nutley, Restaurants)

### Stage 1 Output → session.state

```
rawSignals: {
  blsCpi: {...19 series...},
  censusDemographics: {pop: 28428, income: $95,259, ...},
  osmDensity: {totalBusinesses: 10, nearby: [{name: "Luna Wood Fire Tavern"}, ...]},
  weather: {forecast: [{Fri: 70% rain after 8pm}, {Sat: 60°F sunny}, ...]},
  fdaRecalls: {recentRecallCount: 14, ...},
  localNews: {articles: [{headline: "Nutley Spring Festival Announced"}, ...]},
  trends: {topTerms: ["meal prep", "outdoor dining"], ...},
  ...
}

socialPulse: "Italian Language Exchange at Aromi Di Napoli (246 Washington Ave, Sat)..."
localCatalysts: {summary: "No significant catalysts", catalysts: []}

preComputedImpact: {
  dairy_mom_pct: 1.05, pork_mom_pct: 1.42, seafood_mom_pct: -4.33,
  competitor_count: 10, median_income: 95259, ...
}
```

### Stage 2 Output → session.state

```
macroReport: "Dairy +1.05% MoM, pork +1.42%, but seafood -4.33% creates
             substitution opportunity. Median income $95K supports premium..."

localReport: "Aromi Di Napoli hosting Italian Language Exchange Saturday.
             Luna Wood Fire Tavern shifting to spring event bookings.
             70% rain Friday after 8pm, 60°F Saturday..."

trendNarrative: "First pulse for this zip — no historical trends available."
```

### Stage 3 Output (proposed) → pulseOutput

```json
{
  "headline": "Seafood down 4.3% while 70% Friday rain pushes delivery — swap specials and push DoorDash",

  "localBriefing": {
    "thisWeekInTown": [
      {
        "what": "Italian & English Language Exchange",
        "where": "Aromi Di Napoli, 246 Washington Ave",
        "when": "Saturday March 21, morning",
        "businessImpact": "Foot traffic boost on Washington Ave — if you're nearby, run a brunch special",
        "source": "NJBulletin.com via Social Pulse"
      },
      {
        "what": "Chamber of Commerce Business Mixer",
        "where": "All Glass NJ",
        "when": "Thursday March 26",
        "businessImpact": "Networking opportunity — local restaurant owners attending",
        "source": "NJNetworkingEvents.com via Social Pulse"
      }
    ],
    "competitorWatch": [
      {
        "business": "Luna Wood Fire Tavern",
        "observation": "Shifting marketing to spring private event bookings and catering",
        "implication": "Private event season is starting — add a catering/events page if you don't have one",
        "source": "Social Pulse"
      },
      {
        "business": "Cucina 355",
        "observation": "Promoting spring menu refresh on social media",
        "implication": "Spring menu refresh is becoming table stakes — don't be the last to update",
        "source": "Social Pulse"
      }
    ],
    "communityBuzz": "Nutley's restaurant scene is stable — no new openings or closures in 30 days. Community focus is on spring events and language exchange meetups. No significant complaints or excitement about dining options.",
    "governmentWatch": "No planning board or zoning changes affecting restaurants. Monitor nutleynj.org for Spring 2026 outdoor seating permit renewals."
  },

  "insights": [
    {
      "rank": 1,
      "title": "Swap cream pasta for grilled seafood — save $1.80/plate on the price swing",
      "analysis": "Dairy is up 1.05% MoM (BLS index 283.4) while fish & seafood dropped 4.33% — the widest gap in 6 months. With 10 restaurants within 1500m (OSM), most will be slow to adjust menus. Your median customer earns $95K (Census) and eats out 2-3x/week — they'll notice fresher seafood before they notice cream is gone.",
      "recommendation": "Replace your top 2 cream/cheese-heavy specials with grilled fish alternatives this week. At current BLS prices, this saves approximately $1.80/plate on food cost. Post 'fresh catch' positioning on Instagram.",
      "impactScore": 88,
      "signalSources": ["blsCpi", "osmDensity", "censusDemographics"]
    },
    ...
  ]
}
```

---

## Implementation Plan

### Phase 1: Schema + Synthesis Prompt (1-2 hours)

| # | File | Change |
|---|------|--------|
| 1 | `lib/db/hephae_db/schemas/agent_outputs.py` | Add `LocalEvent`, `CompetitorNote`, `LocalBriefing` models. Add `localBriefing` field to `WeeklyPulseOutput`. |
| 2 | `agents/hephae_agents/research/weekly_pulse_agent.py` | Update `WEEKLY_PULSE_CORE_INSTRUCTION` to require `localBriefing` section with specific sub-field instructions. Add examples. |
| 3 | `agents/hephae_agents/research/pulse_orchestrator.py` | Update `DualModelSynthesis._run_claude()` system prompt to include new schema. Update combiner to merge `localBriefing` sections. |

### Phase 2: Critique Update (30 min)

| # | File | Change |
|---|------|--------|
| 4 | `agents/hephae_agents/research/pulse_critique_agent.py` | Add local briefing quality checks: events must have venue+date, competitors must be named, communityBuzz must cite social data. |

### Phase 3: Frontend (1 hour)

| # | File | Change |
|---|------|--------|
| 5 | `apps/admin/src/components/WeeklyPulse.tsx` | Add "This Week in [Town]" card above insights. Show events with venue/date/impact. Show competitor watch notes. Show community buzz summary. |

### Phase 4: Deploy + Test

- Deploy API + admin
- Run pulse for 07110 (Nutley) — verify local briefing is populated
- Run pulse for a different zip (e.g., 07042 Montclair) — verify different local data

---

## Key Design Decisions

### Why forced sections, not just better prompts?

We already tried prompt improvements (banned flowery language, required numbers). The LLM still gravitates toward macro data because it's easier to write about structured BLS numbers than unstructured social media text. Structural enforcement via schema is the only reliable way to guarantee local content.

### Why not a separate "Local Agent"?

We already have the LocalScoutAgent (Stage 2) that produces a local report. The problem isn't data collection — it's that the synthesis stage ignores the local report in favor of macro data. The fix is in the output schema and synthesis prompt, not in adding another agent.

### Why merge localBriefing from both models?

Gemini and Claude notice different things in the same local data. Gemini might pick up the Chamber of Commerce mixer while Claude catches the competitor menu shifts. Merging both gives more complete local coverage.

### What if there's no local data?

The schema allows empty arrays for `thisWeekInTown` and `competitorWatch`. The `communityBuzz` field can say "No significant local chatter this week." This is honest and useful — the owner knows there's nothing to worry about locally, and the insights section still delivers macro value.
