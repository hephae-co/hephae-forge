"""Capabilities registry — maps capabilities to direct runner functions (no HTTP)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from hephae_api.types import CapabilityDefinition

logger = logging.getLogger(__name__)


# --- Response adapters (normalize runner output for Firestore) ---
# Each adapter preserves the full raw output and adds computed top-level fields.

def _seo_adapter(raw: dict) -> dict:
    adapted = {k: v for k, v in raw.items()}
    adapted["score"] = raw.get("overallScore", raw.get("score", 0))
    adapted.setdefault("summary", "No summary provided.")
    adapted["agentVersion"] = raw.get("agentVersion", "1.0.0")
    adapted["runAt"] = datetime.utcnow().isoformat()
    return adapted


def _traffic_adapter(raw: dict) -> dict:
    adapted = {k: v for k, v in raw.items()}
    adapted.setdefault("score", 70)
    adapted.setdefault("summary", "No summary provided.")
    adapted["agentVersion"] = raw.get("agentVersion", "1.0.0")
    adapted["runAt"] = datetime.utcnow().isoformat()
    return adapted


def _competitive_adapter(raw: dict) -> dict:
    adapted = {k: v for k, v in raw.items()}
    adapted["score"] = raw.get("score")
    adapted["summary"] = raw.get("market_summary", raw.get("summary", "No summary provided."))
    adapted["competitor_count"] = len(raw.get("competitors", []))
    adapted["avg_threat_level"] = raw.get("avg_threat_level")
    adapted["agentVersion"] = raw.get("agentVersion", "1.0.0")
    adapted["runAt"] = datetime.utcnow().isoformat()
    return adapted


def _margin_surgeon_adapter(raw: dict) -> dict:
    adapted = {k: v for k, v in raw.items()}
    adapted["score"] = raw.get("overall_score", raw.get("score", 0))
    adapted.setdefault("summary", "No summary provided.")
    adapted["menu_item_count"] = len(raw.get("menu_items", []))
    adapted["agentVersion"] = raw.get("agentVersion", "1.0.0")
    adapted["runAt"] = datetime.utcnow().isoformat()
    return adapted


def _social_adapter(raw: dict) -> dict:
    adapted = {k: v for k, v in raw.items()}
    adapted["score"] = raw.get("overall_score", raw.get("score", 0))
    adapted.setdefault("summary", "No summary provided.")
    adapted["platform_count"] = len(raw.get("platforms", []))
    adapted["agentVersion"] = raw.get("agentVersion", "1.0.0")
    adapted["runAt"] = datetime.utcnow().isoformat()
    return adapted


# --- Runner functions (lazy imports to avoid circular deps) ---

async def _run_seo(identity: dict, business_context: Any = None, **kwargs) -> dict:
    from hephae_agents.seo_auditor.runner import run_seo_audit
    return await run_seo_audit(identity, business_context, **kwargs)


async def _run_traffic(identity: dict, business_context: Any = None, **kwargs) -> dict:
    from hephae_agents.traffic_forecaster.runner import run_traffic_forecast
    return await run_traffic_forecast(identity, business_context, **kwargs)


async def _run_competitive(identity: dict, business_context: Any = None, **kwargs) -> dict:
    from hephae_agents.competitive_analysis.runner import run_competitive_analysis
    return await run_competitive_analysis(identity, business_context, **kwargs)


async def _run_margin(identity: dict, business_context: Any = None, **kwargs) -> dict:
    from hephae_agents.margin_analyzer.runner import run_margin_analysis
    return await run_margin_analysis(identity, business_context, advanced_mode=True, **kwargs)


async def _run_social(identity: dict, business_context: Any = None, **kwargs) -> dict:
    from hephae_agents.social.media_auditor.runner import run_social_media_audit
    return await run_social_media_audit(identity, business_context, **kwargs)


# --- Evaluator prompt builders ---

def _seo_eval_prompt(identity: dict, output: dict, biz: dict) -> str:
    return f"TARGET_URL: {biz.get('officialUrl', 'unknown')}\nACTUAL_OUTPUT: {json.dumps(output)}"


def _traffic_eval_prompt(identity: dict, output: dict, biz: dict) -> str:
    return f"BUSINESS_IDENTITY: {json.dumps(identity)}\nACTUAL_OUTPUT: {json.dumps(output)}"


def _competitive_eval_prompt(identity: dict, output: dict, biz: dict) -> str:
    return f"BUSINESS_IDENTITY: {json.dumps(identity)}\nACTUAL_OUTPUT: {json.dumps(output)}"


def _margin_eval_prompt(identity: dict, output: dict, biz: dict) -> str:
    return f"BUSINESS_IDENTITY: {json.dumps(identity)}\nACTUAL_OUTPUT: {json.dumps(output)}"


class EvaluatorConfig:
    def __init__(
        self,
        agent_factory: Callable,
        build_prompt: Callable[[dict, dict, dict], str],
        app_name: str,
    ):
        self.agent_factory = agent_factory
        self.build_prompt = build_prompt
        self.app_name = app_name


class FullCapabilityDefinition:
    def __init__(
        self,
        name: str,
        display_name: str,
        firestore_output_key: str,
        response_adapter: Callable[[dict], dict],
        runner: Callable,
        evaluator: EvaluatorConfig | None = None,
        enabled: bool = True,
        should_run: Callable[[dict], bool] | None = None,
    ):
        self.name = name
        self.display_name = display_name
        self.firestore_output_key = firestore_output_key
        self.response_adapter = response_adapter
        self.runner = runner
        self.evaluator = evaluator
        self.enabled = enabled
        self.should_run = should_run


# --- Lazy evaluator factories ---

def _lazy_seo_evaluator():
    from hephae_agents.evaluators.seo_evaluator import SeoEvaluatorAgent
    return SeoEvaluatorAgent


def _lazy_traffic_evaluator():
    from hephae_agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent
    return TrafficEvaluatorAgent


def _lazy_competitive_evaluator():
    from hephae_agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent
    return CompetitiveEvaluatorAgent


def _lazy_margin_evaluator():
    from hephae_agents.evaluators.margin_surgeon_evaluator import MarginSurgeonEvaluatorAgent
    return MarginSurgeonEvaluatorAgent


# --- Registry ---

CAPABILITY_REGISTRY: list[FullCapabilityDefinition] = [
    FullCapabilityDefinition(
        name="seo",
        display_name="SEO Audit",
        firestore_output_key="seo_auditor",
        response_adapter=_seo_adapter,
        runner=_run_seo,
        evaluator=EvaluatorConfig(_lazy_seo_evaluator, _seo_eval_prompt, "wf_seo_eval"),
        enabled=True,
        should_run=lambda biz: bool(biz.get("officialUrl")),
    ),
    FullCapabilityDefinition(
        name="traffic",
        display_name="Traffic Forecast",
        firestore_output_key="traffic_forecaster",
        response_adapter=_traffic_adapter,
        runner=_run_traffic,
        evaluator=EvaluatorConfig(_lazy_traffic_evaluator, _traffic_eval_prompt, "wf_traffic_eval"),
        enabled=True,
    ),
    FullCapabilityDefinition(
        name="competitive",
        display_name="Competitive Analysis",
        firestore_output_key="competitive_analyzer",
        response_adapter=_competitive_adapter,
        runner=_run_competitive,
        evaluator=EvaluatorConfig(_lazy_competitive_evaluator, _competitive_eval_prompt, "wf_comp_eval"),
        enabled=True,
        should_run=lambda biz: bool(biz.get("competitors")),
    ),
    FullCapabilityDefinition(
        name="margin_surgeon",
        display_name="Margin Surgeon",
        firestore_output_key="margin_surgeon",
        response_adapter=_margin_surgeon_adapter,
        runner=_run_margin,
        evaluator=EvaluatorConfig(_lazy_margin_evaluator, _margin_eval_prompt, "wf_margin_eval"),
        enabled=True,
        should_run=lambda biz: bool(biz.get("menuScreenshotBase64")),
    ),
    FullCapabilityDefinition(
        name="social",
        display_name="Social Media Insights",
        firestore_output_key="social_media_auditor",
        response_adapter=_social_adapter,
        runner=_run_social,
        enabled=True,
    ),
]


def get_enabled_capabilities() -> list[FullCapabilityDefinition]:
    return [c for c in CAPABILITY_REGISTRY if c.enabled]


def get_evaluable_capabilities() -> list[FullCapabilityDefinition]:
    return [c for c in CAPABILITY_REGISTRY if c.enabled and c.evaluator]


def get_capability(name: str) -> FullCapabilityDefinition | None:
    return next((c for c in CAPABILITY_REGISTRY if c.name == name), None)
