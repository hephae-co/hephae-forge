"""AI Cost Optimizer tools — static analysis of agent model configs and cost estimation."""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Gemini pricing per 1M tokens (as of 2025)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash-lite": {"input": 0.01875, "output": 0.075},
    "gemini-3-pro-image-preview": {"input": 1.25, "output": 5.00},
}

# Agent modules to scan and their expected LlmAgent instance names
AGENT_MODULES: list[dict[str, Any]] = [
    {
        "module": "backend.agents.discovery.agent",
        "agents": [
            "site_crawler_agent", "theme_agent", "contact_agent",
            "social_media_agent", "menu_agent", "maps_agent",
            "competitor_agent", "news_agent", "social_profiler_agent",
            "discovery_reviewer_agent",
        ],
    },
    {
        "module": "backend.agents.margin_analyzer.agent",
        "agents": [
            "vision_intake_agent", "benchmarker_agent",
            "commodity_watchdog_agent", "surgeon_agent", "advisor_agent",
        ],
    },
    {
        "module": "backend.agents.seo_auditor.agent",
        "agents": ["seo_auditor_agent"],
    },
    {
        "module": "backend.agents.traffic_forecaster.agent",
        "agents": ["poi_gatherer", "weather_gatherer", "events_gatherer"],
    },
    {
        "module": "backend.agents.competitive_analysis.agent",
        "agents": ["competitor_profiler_agent", "market_positioning_agent"],
    },
    {
        "module": "backend.agents.marketing_swarm.agent",
        "agents": [
            "creative_director_agent", "platform_router_agent",
            "instagram_copywriter_agent", "blog_copywriter_agent",
        ],
    },
]

# Data injection sizes (chars) per agent — estimated from _with_raw_data, _with_social_urls, etc.
DATA_INJECTION_ESTIMATES: dict[str, int] = {
    "ThemeAgent": 30000,
    "ContactAgent": 30000,
    "SocialMediaAgent": 30000,
    "MenuAgent": 30000,
    "MapsAgent": 30000,
    "CompetitorAgent": 30000,
    "NewsAgent": 30000,
    "SocialProfilerAgent": 5000,
    "DiscoveryReviewerAgent": 40000,
}


async def scan_agent_configs() -> dict:
    """Scan all agent modules and extract model assignments for every LlmAgent.

    Returns:
        dict with agents list, model_distribution counts, and total.
    """
    agents_found: list[dict[str, str]] = []

    for entry in AGENT_MODULES:
        module_path = entry["module"]
        try:
            mod = importlib.import_module(module_path)
        except Exception as e:
            logger.warning(f"[AICostOptimizer] Could not import {module_path}: {e}")
            continue

        for attr_name in entry["agents"]:
            agent = getattr(mod, attr_name, None)
            if agent is None:
                continue
            model = getattr(agent, "model", "unknown")
            name = getattr(agent, "name", attr_name)
            agents_found.append({
                "name": name,
                "model": model,
                "module": module_path.split(".")[-2],  # e.g. "discovery"
                "attr": attr_name,
            })

    # Build distribution
    distribution: dict[str, int] = {}
    for a in agents_found:
        distribution[a["model"]] = distribution.get(a["model"], 0) + 1

    return {
        "agents": agents_found,
        "model_distribution": distribution,
        "total": len(agents_found),
    }


async def estimate_token_usage(
    agent_name: str,
    prompt_char_count: int,
    data_injection_chars: int = 0,
) -> dict:
    """Estimate input/output token usage and per-call cost for a given agent.

    Args:
        agent_name: The agent name (for context).
        prompt_char_count: Character count of the agent's instruction prompt.
        data_injection_chars: Estimated chars injected via dynamic helpers (e.g. _with_raw_data).

    Returns:
        dict with input_tokens, output_tokens_est, and cost estimates per model.
    """
    # ~4 chars per token for English text
    input_tokens = (prompt_char_count + data_injection_chars) // 4
    # Estimate output as ~20% of input for most agents
    output_tokens_est = max(input_tokens // 5, 500)

    costs: dict[str, float] = {}
    for model, prices in MODEL_PRICING.items():
        cost = (input_tokens * prices["input"] / 1_000_000) + (
            output_tokens_est * prices["output"] / 1_000_000
        )
        costs[model] = round(cost, 6)

    return {
        "agent_name": agent_name,
        "input_tokens": input_tokens,
        "output_tokens_est": output_tokens_est,
        "cost_per_call": costs,
    }


async def calculate_cost_savings(
    current_model: str,
    proposed_model: str,
    monthly_calls: int,
    avg_input_tokens: int,
    avg_output_tokens: int,
) -> dict:
    """Calculate monthly cost savings from switching models.

    Args:
        current_model: Current model string (e.g. "gemini-2.5-flash").
        proposed_model: Proposed cheaper model.
        monthly_calls: Estimated monthly invocations.
        avg_input_tokens: Average input tokens per call.
        avg_output_tokens: Average output tokens per call.

    Returns:
        dict with current_cost, proposed_cost, savings_usd, savings_pct.
    """
    current_prices = MODEL_PRICING.get(current_model, {"input": 0.075, "output": 0.30})
    proposed_prices = MODEL_PRICING.get(proposed_model, {"input": 0.01875, "output": 0.075})

    def _monthly_cost(prices: dict[str, float]) -> float:
        per_call = (avg_input_tokens * prices["input"] / 1_000_000) + (
            avg_output_tokens * prices["output"] / 1_000_000
        )
        return per_call * monthly_calls

    current_cost = _monthly_cost(current_prices)
    proposed_cost = _monthly_cost(proposed_prices)
    savings = current_cost - proposed_cost
    savings_pct = (savings / current_cost * 100) if current_cost > 0 else 0

    return {
        "current_model": current_model,
        "proposed_model": proposed_model,
        "monthly_calls": monthly_calls,
        "current_cost_usd": round(current_cost, 4),
        "proposed_cost_usd": round(proposed_cost, 4),
        "savings_usd": round(savings, 4),
        "savings_pct": round(savings_pct, 1),
    }
