# Evaluation Standards
> Auto-generated from codebase on 2026-03-15. Do not edit manually — run `/hephae-refresh-docs` to update.

## 1. Pass Threshold

All capability evaluations use the same pass gate:

- **Score >= 80** (out of 100)
- **`isHallucinated` == false**

Both conditions must be met simultaneously. If either fails, the capability evaluation is considered failed.

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py` line 143

## 2. Evaluator Configuration Table

All evaluators use the **PRIMARY** model tier (`gemini-3.1-flash-lite-preview`) with **MEDIUM** thinking (`ThinkingConfig(thinking_level="MEDIUM")`). Fallback on model error routes to `gemini-3-flash-preview`.

| Capability | Evaluator Class | Agent Name | Model Tier | Thinking Mode | Firestore Output Key | ADK App Name | Eval Compressor |
|---|---|---|---|---|---|---|---|
| `seo` | `SeoEvaluatorAgent` | `seo_evaluator` | PRIMARY (`gemini-3.1-flash-lite-preview`) | MEDIUM | `seo_auditor` | `wf_seo_eval` | Strips `rawPageSpeed`, `pagespeedData`, `lighthouseData`; truncates recommendations to 3 per section |
| `traffic` | `TrafficEvaluatorAgent` | `traffic_evaluator` | PRIMARY (`gemini-3.1-flash-lite-preview`) | MEDIUM | `traffic_forecaster` | `wf_traffic_eval` | None |
| `competitive` | `CompetitiveEvaluatorAgent` | `competitive_evaluator` | PRIMARY (`gemini-3.1-flash-lite-preview`) | MEDIUM | `competitive_analyzer` | `wf_comp_eval` | Strips full competitor profiles, keeps only `name`, `threat_level`, `summary`, `score` |
| `margin_surgeon` | `MarginSurgeonEvaluatorAgent` | `margin_surgeon_evaluator` | PRIMARY (`gemini-3.1-flash-lite-preview`) | MEDIUM | `margin_surgeon` | `wf_margin_eval` | None |

**Note:** The `social` capability does not have an evaluator and is excluded from evaluation.

> Sources:
> - `agents/hephae_agents/evaluators/*.py`
> - `apps/api/hephae_api/workflows/capabilities/registry.py` lines 205-254
> - `lib/common/hephae_common/model_config.py`

## 3. Per-Capability Evaluation Criteria

### 3.1 SEO (`SeoEvaluatorAgent`)

**Prompt input:** `TARGET_URL` (the business's official URL) and `ACTUAL_OUTPUT` (the SEO Auditor JSON).

**Evaluation criteria:**
- Output is coherent and well-structured
- Output actually belongs to the given URL (not a different site)
- Properly describes SEO aspects without hallucinating
- Fields are present and non-null

**Hallucination rules:**
- Standard — flag `isHallucinated=true` if output contains fabricated data or does not match the target URL

> Source: `agents/hephae_agents/evaluators/seo_evaluator.py`

### 3.2 Traffic Forecast (`TrafficEvaluatorAgent`)

**Prompt input:** `BUSINESS_IDENTITY` (full identity JSON), `ZIP_CODE`, `ACTUAL_OUTPUT` (Traffic Forecaster JSON), and optionally `RESEARCH_CONTEXT` with ground-truth weather/events data.

**Evaluation criteria (score 0-100):**
- **Geographic plausibility:** business type, address, and nearby POIs make sense together
- **Time slot logic:** scores align with business hours and day-of-week patterns
- **Weather consistency:** `weatherNote` should be plausible for the location and season
- **Event relevance:** `localEvents` should be real or plausible for the area
- **Score reasonability:** traffic scores should reflect a realistic pattern (not all high, not all identical)

**Hallucination rules (conservative):**
- ONLY flag `isHallucinated=true` if the output contains clearly fabricated data: invented addresses, impossible coordinates, business type contradictions, or events that could not plausibly exist in the area
- Do NOT flag as hallucinated just because you cannot independently verify a weather forecast or local event — the forecaster has access to real-time search tools
- If `RESEARCH_CONTEXT` is provided, cross-check weather/event claims against it. Contradictions with research data ARE grounds for hallucination flags
- Minor inaccuracies (slightly off weather, generic events) should reduce the score but NOT trigger `isHallucinated`

> Source: `agents/hephae_agents/evaluators/traffic_evaluator.py`

### 3.3 Competitive Analysis (`CompetitiveEvaluatorAgent`)

**Prompt input:** `BUSINESS_IDENTITY` (full identity JSON) and `ACTUAL_OUTPUT` (Competitive Analyzer JSON, compressed to summaries only).

**Evaluation criteria (score 0-100):**
- **Competitor plausibility:** named competitors should be real businesses that could exist in the area
- **Analysis depth:** pricing comparisons, market gaps, and positioning should be specific, not generic
- **Internal consistency:** competitor details should align with the business type and location
- **Actionable insights:** recommendations should be concrete and relevant

**Hallucination rules (conservative):**
- ONLY flag `isHallucinated=true` if competitors are clearly fabricated (impossible names, wrong business type, contradictory locations) or if the analysis contains demonstrably false claims
- The competitive analyzer has access to Google Search — it can find real competitors you may not know about. Do NOT flag as hallucinated just because you cannot verify a competitor exists
- Generic or shallow analysis should reduce the score but NOT trigger `isHallucinated`
- If the analysis names specific real-sounding businesses in the correct geographic area with plausible details, assume they are real unless clearly contradicted

> Source: `agents/hephae_agents/evaluators/competitive_evaluator.py`

### 3.4 Margin Surgeon (`MarginSurgeonEvaluatorAgent`)

**Prompt input:** `BUSINESS_IDENTITY` (full identity JSON) and `ACTUAL_OUTPUT` (Margin Surgeon JSON). Optionally includes `FOOD_PRICING_CONTEXT`.

**Evaluation criteria:**
- Menu items are plausible for the business type (no sushi items for a pizza shop)
- Strategic advice is coherent
- Scores are internally consistent
- Data is not hallucinated
- Watch for red flags: mismatched menu items, impossible margins, generic advice

**When `FOOD_PRICING_CONTEXT` is provided, also verify:**
- Strategic advice acknowledges current commodity cost trends
- Margin optimization suggestions are realistic given input cost changes
- Flag if advice recommends cost cuts on categories with >5% YoY increases without acknowledging the trend
- Award bonus score points if advice correctly references real cost data

> Source: `agents/hephae_agents/evaluators/margin_surgeon_evaluator.py`

## 4. Evaluation Flow

The evaluation phase is orchestrated by `run_evaluation_phase()` in `evaluation.py`:

1. **Business selection:** Only businesses in `ANALYSIS_DONE` or `EVALUATING` phase are evaluated. Phase is set to `EVALUATING` at the start.

2. **Capability filtering:** For each business, only capabilities that are (a) in `capabilitiesCompleted`, (b) have output in `latestOutputs`, and (c) have an evaluator configured are evaluated.

3. **Prompt construction:** Each evaluator's `build_prompt()` function constructs the prompt from the business identity and capability output. If an `eval_compressor` is configured, it strips large/verbose fields before sending to the evaluator.

4. **Execution modes:**
   - **Batch mode (default in production):** All eval prompts are collected and submitted via Vertex AI batch API with a configurable timeout. Controlled by `BATCH_EVAL_ENABLED` env var (defaults to `true`).
   - **Sequential fallback:** If batch submission fails or is disabled (or in debug mode), each evaluator runs sequentially via `run_agent_to_json()`.

5. **Result parsing:** Evaluator JSON output is parsed into an `EvaluationResult`. If parsing fails, a default failing result is created (`score=0, isHallucinated=true, issues=["Failed to parse evaluator output"]`).

6. **Feedback recording:** Each evaluation result is recorded to BigQuery via `record_evaluation_feedback()` (fire-and-forget async task) with business slug, capability name, agent version, eval score, hallucination flag, zip code, and business type.

7. **Phase finalization:** After all evaluations complete, `qualityPassed` is computed and phase is set to `EVALUATION_DONE`. The `onBusinessEvaluated` callback is invoked with the business slug and pass/fail status.

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py`

## 5. Quality Gate

`qualityPassed` is determined by the following logic (line 141-144 of `evaluation.py`):

```python
biz.qualityPassed = (
    len(eval_results) > 0
    and all(e.score >= 80 and not e.isHallucinated for e in eval_results)
)
```

This means:
- **ALL** evaluated capabilities must pass (score >= 80 AND not hallucinated)
- There must be **at least one** evaluation result (a business with zero evaluations fails)
- A single failing capability fails the entire business

If an error occurs during eval preparation (e.g., cannot fetch business data), `qualityPassed` is set to `false` immediately.

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py` lines 141-144

## 6. Result Schema

### `EvaluationResult` (Pydantic model)

| Field | Type | Default | Description |
|---|---|---|---|
| `score` | `float` | `0` | Quality score from 0-100 |
| `isHallucinated` | `bool` | `false` | Whether the evaluator detected fabricated data |
| `issues` | `list[str]` | `[]` | List of specific issues found by the evaluator |

> Source: `lib/common/hephae_common/models.py` line 402

### `EvaluationOutput` (ADK output schema used by evaluator agents)

| Field | Type | Default | Description |
|---|---|---|---|
| `score` | `int` | `0` | Quality score from 0-100 |
| `isHallucinated` | `bool` | `false` | Whether the evaluator detected fabricated data |
| `issues` | `list[str]` | `[]` | List of specific issues found by the evaluator |

> Source: `lib/db/hephae_db/schemas/agent_outputs.py` line 845

### Storage

- **In-memory:** `BusinessWorkflowState.evaluations` — `dict[str, EvaluationResult]` keyed by capability name (e.g., `{"seo": {...}, "traffic": {...}}`)
- **BigQuery:** Each evaluation is recorded as a feedback row via `record_evaluation_feedback()` with fields: `business_slug`, `capability`, `agent_name`, `agent_version`, `eval_score`, `is_hallucinated`, `zip_code`, `business_type`
