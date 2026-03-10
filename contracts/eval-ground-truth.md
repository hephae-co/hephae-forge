# How Human-Marked Ground Truth Data Evaluates ADK Agents

> Explains how human-curated fixtures flow through the ADK evaluation pipeline.
> For runtime evaluator agents (score >= 80, hallucination checks), see `eval-standards.md`.

## Three Mechanisms (Only Two Are Evaluation)

### 1. Few-Shot Injection (Runtime — NOT Evaluation)

**What it does**: Improves agent output quality by showing examples of good outputs at runtime.

**Flow**:
```
Admin marks fixture as "grounding" in BusinessBrowser UI
  → Firestore test_fixtures collection (fixtureType="grounding")
  → HephaeExampleStore loads fixtures at runner call time
  → Converts to ADK Example objects (user prompt + model response pairs)
  → Injected into agent's InMemoryMemoryService
  → Agent sees examples of ideal outputs before generating its own
```

**Key files**: `packages/db/hephae_db/eval/example_store.py`, `packages/db/hephae_db/eval/grounding.py`

**This is NOT evaluation** — it's prompt engineering. The agent isn't scored, it's helped.

---

### 2. Rubric-Based Quality Scoring (LLM-as-Judge)

**What it does**: An LLM judge evaluates the agent's output against human-defined quality criteria (rubrics).

**Flow**:
```
Admin marks fixture as "test_case" in BusinessBrowser UI
  → Firestore test_fixtures (fixtureType="test_case", agentKey="seo_auditor")
  → FirestoreEvalSetsManager.get_eval_set() loads fixtures
  → Converts each to EvalCase:
      - user_content = reconstructed prompt from identity
      - final_response = saved agentOutput (the reference answer)
      - rubrics = agent-specific rubric list from rubrics.py
  → AgentEvaluator.evaluate_eval_set() runs the agent fresh
  → ADK's rubric_based_final_response_quality_v1 metric:
      - LLM judge scores each rubric (pass/fail)
      - Threshold: 60% of rubrics must pass
```

**Key files**:
- `packages/db/hephae_db/eval/firestore_eval_sets_manager.py` — Fixture → EvalCase conversion
- `packages/db/hephae_db/eval/rubrics.py` — 9 agent rubric sets (4 rubrics each)
- `packages/db/hephae_db/eval/prompt_builders.py` — Reconstructs agent input from identity
- `tests/evals/test_agent_evals_human.py` — Test runner (pytest)

**How ground truth is used**: The rubrics are **format/structure checks** (e.g., "has overallScore field", "includes at least 3 menu items"). They don't compare against the reference answer — they evaluate the output in isolation. The ground truth identity data drives what business the agent is tested against.

---

### 3. Response Match Score (Semantic Similarity)

**What it does**: Compares the agent's new output against the saved reference answer using semantic similarity.

**Flow**:
```
Same EvalCase as mechanism 2 (same fixture, same test run)
  → ADK's response_match_score metric:
      - Embeds both the saved agentOutput (reference) and the fresh output
      - Computes cosine similarity
      - Threshold: 0.3 (very lenient — generative outputs naturally vary)
```

**How ground truth is used**: The saved `agentOutput` IS the ground truth. If the agent's fresh output diverges too much from what was saved, the test fails. The low threshold (0.3) means this is a regression smoke test, not an accuracy check.

---

## The Full Picture

When you run `pytest tests/evals/test_agent_evals_human.py -m human_curated`:

1. For each agent (seo_auditor, traffic_forecaster, etc.):
2. Load all `test_case` fixtures from Firestore for that agent
3. For each fixture, reconstruct the input prompt and set the saved output as reference
4. Run the agent fresh against each input
5. Score with **both** metrics simultaneously:
   - `rubric_based_final_response_quality_v1 >= 0.6` (structural quality)
   - `response_match_score >= 0.3` (semantic regression check)

---

## Current Gap

The rubrics are **format-only** — they check structure (valid JSON, fields present, minimum counts) but never say "compare against the reference answer." The LLM judge doesn't know the ground truth exists.

The `response_match_score` does use ground truth, but at 0.3 it only catches catastrophic regressions.

**Result**: A model upgrade that produces structurally valid but factually wrong reports (wrong competitors, wrong scores) would pass both checks.

---

## Potential Improvements

1. **Ground-truth-aware rubrics**: Add rubrics like "The overallScore should be within 15 points of the reference answer" — the ADK rubric system passes both response AND reference to the judge
2. **Deterministic field comparison**: Compare specific fields (scores, competitor names, URLs) programmatically against ground truth, without LLM
3. **Gold standard differentiation**: The `isGoldStandard` flag exists in fixtures but is unused — gold fixtures could have stricter thresholds (0.5+ match score)
4. **Score history tracking**: Store eval scores over time to detect gradual quality drift across model/agent versions

---

## Verification

```bash
# List all test_case fixtures
pytest tests/evals/test_agent_evals_human.py -m human_curated -v --collect-only

# Run evals for a specific agent
pytest tests/evals/test_agent_evals_human.py::test_seo_auditor_human -v

# See rubric definitions
cat packages/db/hephae_db/eval/rubrics.py
```
