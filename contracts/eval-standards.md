# Evaluation Standards

> Defines the quality bar that web app agent outputs must meet.
> Admin evaluator agents enforce these thresholds.

## Pass Criteria

All capability evaluations use the same threshold:
- **Score >= 80** (out of 100)
- **isHallucinated == false**

Both conditions must be met. If either fails, the business is flagged for re-analysis.

## Evaluator Configuration

| Capability | Evaluator Agent | Model | Thinking |
|---|---|---|---|
| SEO | `SeoEvaluatorAgent` | ENHANCED (gemini-3.0-flash-preview) | MEDIUM |
| Traffic | `TrafficEvaluatorAgent` | ENHANCED | MEDIUM |
| Competitive | `CompetitiveEvaluatorAgent` | ENHANCED | MEDIUM |
| Margin Surgeon | `MarginSurgeonEvaluatorAgent` | ENHANCED | MEDIUM |

## What Evaluators Check

- **Completeness:** All expected fields present and non-null
- **Plausibility:** Scores and numbers within reasonable ranges
- **Hallucination:** Cross-reference claims against input data (does the report reference real menu items, real competitors, real addresses?)
- **Actionability:** Recommendations are specific and reference actual data points

## When to Update

If you change a web app agent's output schema (new fields, removed fields, renamed fields):
1. Bump the agent version in `web/backend/config.py`
2. Update the corresponding evaluator in `admin/backend/agents/evaluators/`
3. Update `contracts/api-web.md` if the API response shape changed
4. Log the change in `contracts/changelog.md`
