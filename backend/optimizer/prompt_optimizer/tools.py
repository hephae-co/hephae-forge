"""Prompt Optimizer tools — scan prompts, call Vertex AI optimizer, compare quality."""

from __future__ import annotations

import importlib
import logging
import os

logger = logging.getLogger(__name__)

# Prompt modules to scan — (module_path, file_name_hint)
PROMPT_MODULES = [
    ("backend.agents.discovery.prompts", "discovery"),
    ("backend.agents.margin_analyzer.prompts", "margin_analyzer"),
    ("backend.agents.traffic_forecaster.prompts", "traffic_forecaster"),
    ("backend.agents.competitive_analysis.prompts", "competitive_analysis"),
    ("backend.agents.marketing_swarm.prompts", "marketing_swarm"),
    ("backend.agents.seo_auditor.prompt", "seo_auditor"),
]


async def list_all_prompts() -> dict:
    """Scan all backend/agents/*/prompts.py files and return a registry of prompt constants.

    Finds all module-level string constants ending in '_INSTRUCTION'.

    Returns:
        dict with prompts list and total_count.
    """
    prompts = []

    for module_path, domain in PROMPT_MODULES:
        try:
            mod = importlib.import_module(module_path)
        except Exception as e:
            logger.warning(f"[PromptOptimizer] Could not import {module_path}: {e}")
            continue

        for attr_name in sorted(dir(mod)):
            if not attr_name.endswith("_INSTRUCTION"):
                continue
            val = getattr(mod, attr_name, None)
            if not isinstance(val, str):
                continue
            prompts.append({
                "name": attr_name,
                "module_path": module_path,
                "domain": domain,
                "char_count": len(val),
                "preview": val[:200].replace("\n", " ").strip(),
            })

    return {
        "prompts": prompts,
        "total_count": len(prompts),
    }


async def optimize_prompt_vertex(
    prompt_text: str,
    prompt_name: str,
    strategy: str = "zero_shot",
) -> dict:
    """Call Vertex AI Prompt Optimizer to optimize a given prompt.

    Args:
        prompt_text: The full prompt text to optimize.
        prompt_name: Human-readable name (e.g. "SITE_CRAWLER_INSTRUCTION").
        strategy: "zero_shot" (default) or "few_shot".

    Returns:
        dict with optimized_prompt, strategy_used, improvement_notes.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        return {
            "optimized_prompt": prompt_text,
            "strategy_used": "none",
            "improvement_notes": ["GOOGLE_CLOUD_PROJECT env var not set — cannot call Vertex AI Prompt Optimizer"],
            "error": "missing_project",
        }

    try:
        from vertexai import Client

        client = Client(project=project, location="us-central1")

        if strategy == "zero_shot":
            response = client.prompt_optimizer.optimize_prompt(prompt=prompt_text)
            optimized = getattr(response, "suggested_prompt", None) or prompt_text
            return {
                "optimized_prompt": optimized,
                "strategy_used": "zero_shot",
                "improvement_notes": [
                    f"Vertex AI zero-shot optimization applied to {prompt_name}",
                    f"Original length: {len(prompt_text)} chars → Optimized length: {len(optimized)} chars",
                ],
            }

        elif strategy == "few_shot":
            # Few-shot requires rubrics or target responses — attempt zero_shot as fallback
            try:
                response = client.prompt_optimizer.optimize_prompt(
                    prompt=prompt_text,
                )
                optimized = getattr(response, "suggested_prompt", None) or prompt_text
                return {
                    "optimized_prompt": optimized,
                    "strategy_used": "zero_shot_fallback",
                    "improvement_notes": [
                        "Few-shot requires labeled examples — fell back to zero-shot",
                        f"Original length: {len(prompt_text)} chars → Optimized length: {len(optimized)} chars",
                    ],
                }
            except Exception as e:
                logger.warning(f"[PromptOptimizer] Few-shot fallback failed: {e}")
                return {
                    "optimized_prompt": prompt_text,
                    "strategy_used": "none",
                    "improvement_notes": [f"Both few-shot and zero-shot failed: {e}"],
                    "error": str(e),
                }

        else:
            return {
                "optimized_prompt": prompt_text,
                "strategy_used": "none",
                "improvement_notes": [f"Unknown strategy '{strategy}' — no optimization applied"],
            }

    except ImportError:
        return {
            "optimized_prompt": prompt_text,
            "strategy_used": "none",
            "improvement_notes": ["vertexai package not available — install with 'pip install google-cloud-aiplatform'"],
            "error": "import_error",
        }
    except Exception as e:
        logger.error(f"[PromptOptimizer] Vertex AI call failed for {prompt_name}: {e}")
        return {
            "optimized_prompt": prompt_text,
            "strategy_used": "none",
            "improvement_notes": [f"Vertex AI optimizer failed: {e}"],
            "error": str(e),
        }


async def compare_prompt_quality(
    original: str,
    optimized: str,
    prompt_name: str,
) -> dict:
    """Use Gemini to compare an original prompt with an optimized version.

    Args:
        original: The original prompt text.
        optimized: The optimized prompt text.
        prompt_name: Name of the prompt constant.

    Returns:
        dict with improvement_areas, risk_assessment, recommendation.
    """
    if original == optimized:
        return {
            "prompt_name": prompt_name,
            "improvement_areas": [],
            "risk_assessment": "No changes made",
            "recommendation": "skip",
            "reason": "Optimized prompt is identical to original",
        }

    try:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {
                "prompt_name": prompt_name,
                "improvement_areas": ["Cannot compare — GEMINI_API_KEY not set"],
                "risk_assessment": "unknown",
                "recommendation": "review",
            }

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Compare these two agent prompts and assess the optimization quality.\n\n"
                f"ORIGINAL PROMPT ({prompt_name}):\n{original[:3000]}\n\n"
                f"OPTIMIZED PROMPT:\n{optimized[:3000]}\n\n"
                f"Return ONLY valid JSON with keys: "
                f'"improvement_areas" (list of specific improvements), '
                f'"risk_assessment" (potential risks of switching), '
                f'"recommendation" ("apply", "review", or "skip")'
            ),
            config={"response_mime_type": "application/json"},
        )

        import json
        result = json.loads(response.text)
        result["prompt_name"] = prompt_name
        return result

    except Exception as e:
        logger.error(f"[PromptOptimizer] Comparison failed for {prompt_name}: {e}")
        return {
            "prompt_name": prompt_name,
            "improvement_areas": [f"Comparison failed: {e}"],
            "risk_assessment": "unknown",
            "recommendation": "review",
        }
