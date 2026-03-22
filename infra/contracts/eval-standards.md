# Evaluation Standards
> Auto-generated from codebase on 2026-03-22. Do not edit manually — run `/hephae-refresh-docs` to update.

## 1. Pass Threshold

All capability evaluations use the same pass gate:

- **Score >= 80** (out of 100)
- **`isHallucinated` == false**

Both conditions must be met simultaneously. If either fails, the capability evaluation is considered failed.

A business passes overall evaluation only if **all** its evaluable capabilities pass:

```python
biz.qualityPassed = (
    len(eval_results) > 0
    and all(e.score >= 80 and not e.isHallucinated for e in eval_results)
)
```

If a business has zero evaluable outputs, it is marked `evaluation_done` with `qualityPassed = False`.

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py` lines 158-161

---

## 2. Evaluator Configuration

All four evaluators share the same model and thinking preset:

| Evaluator | Agent Name | Model | Thinking | App Name |
|-----------|-----------|-------|----------|----------|
| SEO Evaluator | `seo_evaluator` | `gemini-3.1-flash-lite-preview` | MEDIUM | `wf_seo_eval` |
| Traffic Evaluator | `traffic_evaluator` | `gemini-3.1-flash-lite-preview` | MEDIUM | `wf_traffic_eval` |
| Competitive Evaluator | `competitive_evaluator` | `gemini-3.1-flash-lite-preview` | MEDIUM | `wf_comp_eval` |
| Margin Surgeon Evaluator | `margin_surgeon_evaluator` | `gemini-3.1-flash-lite-preview` | MEDIUM | `wf_margin_eval` |

**Social Media Insights (`social`)** has no evaluator and is not evaluated.

All evaluators use `ThinkingPresets.MEDIUM` and `AgentModels.PRIMARY_MODEL`. All have `on_model_error_callback=fallback_on_error` for automatic model fallback on 429/503/529.

**Output schema** (shared across all evaluators — `EvaluationOutput`):

```json
{
    "score": number (0-100),
    "isHallucinated": boolean,
    "issues": string[]
}
```

> Source: `agents/hephae_agents/evaluators/`

---

## 3. Evaluation Modes

The evaluation phase supports two modes:

| Mode | Description | Controlled By |
|------|-------------|---------------|
| **Batch** (default) | Collects all eval prompts across all businesses, submits via Vertex AI batch API | `BATCH_EVAL_ENABLED=true` (env var) |
| **Sequential** (fallback) | Runs each evaluator one at a time | Fallback when batch fails, or `debug=True` |

Batch mode settings:
- `BATCH_EVAL_GCS_BUCKET`: `hephae-batch-evaluations` (default)
- `BATCH_EVAL_FALLBACK_TIMEOUT`: 300 seconds (default)

If batch submission fails, the system falls back to sequential evaluation transparently.

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py`

---

## 4. Per-Capability Evaluation Criteria

### 4.1 SEO Evaluator

**Input**: `TARGET_URL` + `ACTUAL_OUTPUT` JSON

**Criteria**: Review the SEO audit output for completeness and hallucinations. Verify the output is coherent, belongs to the given URL, and properly describes SEO aspects without fabricating data.

**Eval compressor**: Strips `rawPageSpeed`, `pagespeedData`, `lighthouseData`. Truncates recommendations to 3 per section.

> Source: `agents/hephae_agents/evaluators/seo_evaluator.py`

### 4.2 Traffic Evaluator

**Input**: `BUSINESS_IDENTITY` + `ZIP_CODE` + `ACTUAL_OUTPUT` JSON

**Criteria** (scored 0-100):
1. **Geographic plausibility** — business type, address, and nearby POIs make sense together
2. **Time slot logic** — scores align with business hours and day-of-week patterns
3. **Weather consistency** — weatherNote should be plausible for the location and season
4. **Event relevance** — localEvents should be real or plausible for the area
5. **Score reasonability** — traffic scores should reflect realistic patterns (not all high, not all identical)

**Hallucination rules** (conservative):
- ONLY flag `isHallucinated=true` for clearly fabricated data: invented addresses, impossible coordinates, business type contradictions, events that could not plausibly exist
- Do NOT flag as hallucinated because a weather forecast or event cannot be independently verified (the forecaster has search tools)
- If `RESEARCH_CONTEXT` is provided, cross-check weather/event claims — contradictions with research data ARE grounds for hallucination flags
- Minor inaccuracies reduce score but do NOT trigger `isHallucinated`

> Source: `agents/hephae_agents/evaluators/traffic_evaluator.py`

### 4.3 Competitive Evaluator

**Input**: `BUSINESS_IDENTITY` + `ACTUAL_OUTPUT` JSON

**Criteria** (scored 0-100):
1. **Competitor plausibility** — named competitors should be real businesses in the area
2. **Analysis depth** — pricing comparisons, market gaps, positioning should be specific, not generic
3. **Internal consistency** — competitor details should align with business type and location
4. **Actionable insights** — recommendations should be concrete and relevant

**Hallucination rules** (conservative):
- ONLY flag `isHallucinated=true` for clearly fabricated competitors (impossible names, wrong business type, contradictory locations) or demonstrably false claims
- The competitive analyzer has Google Search — do NOT flag because a competitor cannot be independently verified
- Generic/shallow analysis reduces score but does NOT trigger `isHallucinated`
- Specific real-sounding businesses with plausible details in the correct area are assumed real unless clearly contradicted

**Eval compressor**: Strips full competitor profiles, keeps only `name`, `threat_level`, `summary`, `score` per competitor.

> Source: `agents/hephae_agents/evaluators/competitive_evaluator.py`

### 4.4 Margin Surgeon Evaluator

**Input**: `BUSINESS_IDENTITY` + `ACTUAL_OUTPUT` JSON

**Criteria**: Validate that menu items are plausible for the business type, strategic advice is coherent, scores are consistent, and data is not hallucinated. Red flags: sushi items for a pizza shop, impossible margins, generic advice.

**Food pricing context validation** (when `FOOD_PRICING_CONTEXT` is provided):
- Strategic advice should acknowledge current commodity cost trends
- Margin optimization suggestions should be realistic given input cost changes
- Flag if advice recommends cost cuts on categories with > 5% YoY increases without acknowledging the trend
- Award bonus score points if advice correctly references real cost data

> Source: `agents/hephae_agents/evaluators/margin_surgeon_evaluator.py`

---

## 5. Evaluation Feedback Pipeline

Every evaluation result is recorded to BigQuery (fire-and-forget) for long-term analysis:

| Field | Value |
|-------|-------|
| `business_slug` | Business identifier |
| `capability` | Capability name (seo, traffic, competitive, margin_surgeon) |
| `agent_name` | Firestore output key |
| `agent_version` | From `latestOutputs.{cap}.agentVersion` |
| `eval_score` | 0-100 score |
| `is_hallucinated` | Boolean |
| `zip_code` | Source zip code |
| `business_type` | Business type |

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py` lines 142-152

---

## 6. Score Coercion

Evaluators sometimes return non-numeric scores (e.g., `"85/100"`). The evaluation phase coerces scores:

```python
raw_score = result.get("score", 0)
score = float(raw_score) if not isinstance(raw_score, (int, float)) else raw_score
```

If coercion fails, the score defaults to 0 (evaluation fails).

> Source: `apps/api/hephae_api/workflows/phases/evaluation.py` lines 124-129
