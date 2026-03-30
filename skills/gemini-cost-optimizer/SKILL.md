---
name: gemini-cost-optimizer
description: Systematically optimize Gemini API usage for cost efficiency. Use when designing new agents, refactoring prompts, or auditing model selections to reduce token burn while maintaining quality.
---

# Gemini Cost Optimizer

## Overview
This skill provides a systematic approach to minimizing Gemini API costs through model tiering, context caching, and batch mode utilization.

## 1. Model Selection Strategy (The "Flash-First" Rule)
Always select the smallest model that can reliably perform the task. Cost difference between Flash-Lite and Pro is typically >10x.

### Decision Tree:
- **Simple Task (Extraction, Summarization, Basic Translation):** Use `gemini-3.1-flash-lite-preview` (Primary).
- **Nuanced Analysis (Reasoning, Multi-step Logic, Coding):** Use `gemini-3-flash-preview` (Synthesis).
- **High-Fidelity Complex Tasks (Architectural Design, Deep Creative Writing):** Only then consider Gemini 2.5/3.1 Pro.

## 2. Context Caching (The 90% Discount)
Leverage caching for large, stable prefixes (e.g., massive system prompts or reference docs).

- **Implicit Caching**: Automatic for prefixes >1,024 tokens (Flash) or >4,096 tokens (Pro). Ensure "Prefix Alignment" by keeping dynamic variables (like the current date) at the **end** of the prompt.
- **Explicit Caching**: Best for static knowledge bases >32k tokens used multiple times per hour. 
- **See also**: [references/caching-guide.md](references/caching-guide.md) for technical thresholds and break-even analysis.

## 3. Batch Mode (The 50% Discount)
For non-urgent, high-volume tasks (e.g., nightly processing), use the Gemini Batch API.

- **Benefit**: 50% discount on standard token rates.
- **Trade-off**: 24-hour SLA (not for interactive use).
- **See also**: [references/batch-mode.md](references/batch-mode.md) for technical workflow and GCS integration.

## 4. Token Management & Prompt Efficiency
- **Negative Constraints**: Be precise. Tell the model what **not** to do to avoid verbose, irrelevant output.
- **Structured Output**: Use `response_mime_type: "application/json"` with a strict `response_schema`. This forces the model to be concise and eliminates the token cost of conversational filler.
- **Example-Based Prompting**: 2-3 concise examples (few-shot) are often more token-efficient than long paragraphs of instructions.

## 5. Workflow: Auditing an Agent for Cost
1.  **Check Model Tier**: Is the agent using a Pro model when a Flash model could suffice? Is it using `gemini-3.1-flash-lite-preview` for simple extraction?
2.  **Verify Context Caching**:
    - **Prefix Alignment**: Are dynamic variables (dates, names) at the start of the prompt? Move them to the end to enable cache hits.
    - **Volume Audit**: Is the prompt >32k tokens and used >3x/hr? If so, recommend Explicit Caching.
3.  **Evaluate Batch Usage**: Can this task be deferred to a 24-hour window? If yes, recommend Batch API.
4.  **Audit Prompt Length**: Are there redundant instructions or verbose explanations that could be shortened?
5.  **Evaluate Output Length**: Is `max_output_tokens` set appropriately to prevent "rambling"?
6.  **Usage Monitoring**: Check `usage_metadata` for `cached_content_token_count` to verify that caching is actually working.
