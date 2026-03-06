"""Capabilities registry — central definitions for all hephae-forge capabilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable

from backend.types import CapabilityDefinition

logger = logging.getLogger(__name__)


def _seo_adapter(raw: dict) -> dict:
    return {
        "score": raw.get("overallScore", 0),
        "summary": raw.get("summary", "No summary provided."),
        "reportUrl": raw.get("reportUrl"),
        "agentVersion": raw.get("agentVersion", "1.0.0"),
        "runAt": datetime.utcnow().isoformat(),
    }


def _traffic_adapter(raw: dict) -> dict:
    return {
        "score": raw.get("score", 70),
        "summary": raw.get("summary", "No summary provided."),
        "reportUrl": raw.get("reportUrl"),
        "agentVersion": raw.get("agentVersion", "1.0.0"),
        "peak_slot_score": raw.get("peak_slot_score"),
        "runAt": datetime.utcnow().isoformat(),
    }


def _competitive_adapter(raw: dict) -> dict:
    return {
        "score": raw.get("score"),
        "summary": raw.get("market_summary", "No summary provided."),
        "reportUrl": raw.get("reportUrl"),
        "agentVersion": raw.get("agentVersion", "1.0.0"),
        "competitor_count": len(raw.get("competitors", [])),
        "avg_threat_level": raw.get("avg_threat_level"),
        "runAt": datetime.utcnow().isoformat(),
    }


def _margin_surgeon_adapter(raw: dict) -> dict:
    return {
        "score": raw.get("overall_score", 0),
        "menu_items": raw.get("menu_items", []),
        "strategic_advice": raw.get("strategic_advice", []),
        "summary": raw.get("summary", "No summary provided."),
        "reportUrl": raw.get("reportUrl"),
        "agentVersion": raw.get("agentVersion", "1.0.0"),
        "total_leakage": raw.get("total_leakage"),
        "menu_item_count": len(raw.get("menu_items", [])),
        "runAt": datetime.utcnow().isoformat(),
    }


# Evaluator prompt builders
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
        api_version: str,
        endpoint_slug: str,
        firestore_output_key: str,
        response_adapter: Callable[[dict], dict],
        evaluator: EvaluatorConfig | None = None,
        enabled: bool = True,
        should_run: Callable[[dict], bool] | None = None,
        build_payload: Callable[[dict], dict] | None = None,
    ):
        self.name = name
        self.display_name = display_name
        self.api_version = api_version
        self.endpoint_slug = endpoint_slug
        self.firestore_output_key = firestore_output_key
        self.response_adapter = response_adapter
        self.evaluator = evaluator
        self.enabled = enabled
        self.should_run = should_run
        self.build_payload = build_payload


def _lazy_seo_evaluator():
    from backend.agents.evaluators.seo_evaluator import SeoEvaluatorAgent
    return SeoEvaluatorAgent


def _lazy_traffic_evaluator():
    from backend.agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent
    return TrafficEvaluatorAgent


def _lazy_competitive_evaluator():
    from backend.agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent
    return CompetitiveEvaluatorAgent


def _lazy_margin_evaluator():
    from backend.agents.evaluators.margin_surgeon_evaluator import MarginSurgeonEvaluatorAgent
    return MarginSurgeonEvaluatorAgent


CAPABILITY_REGISTRY: list[FullCapabilityDefinition] = [
    FullCapabilityDefinition(
        name="seo",
        display_name="SEO Audit",
        api_version="capabilities",
        endpoint_slug="seo",
        firestore_output_key="seo_auditor",
        response_adapter=_seo_adapter,
        evaluator=EvaluatorConfig(_lazy_seo_evaluator, _seo_eval_prompt, "wf-seo-eval"),
        enabled=True,
        should_run=lambda biz: bool(biz.get("officialUrl")),
    ),
    FullCapabilityDefinition(
        name="traffic",
        display_name="Traffic Forecast",
        api_version="capabilities",
        endpoint_slug="traffic",
        firestore_output_key="traffic_forecaster",
        response_adapter=_traffic_adapter,
        evaluator=EvaluatorConfig(_lazy_traffic_evaluator, _traffic_eval_prompt, "wf-traffic-eval"),
        enabled=True,
    ),
    FullCapabilityDefinition(
        name="competitive",
        display_name="Competitive Analysis",
        api_version="capabilities",
        endpoint_slug="competitive",
        firestore_output_key="competitive_analyzer",
        response_adapter=_competitive_adapter,
        evaluator=EvaluatorConfig(_lazy_competitive_evaluator, _competitive_eval_prompt, "wf-comp-eval"),
        enabled=True,
    ),
    FullCapabilityDefinition(
        name="margin_surgeon",
        display_name="Margin Surgeon",
        api_version="v1",
        endpoint_slug="analyze",
        firestore_output_key="margin_surgeon",
        response_adapter=_margin_surgeon_adapter,
        evaluator=EvaluatorConfig(_lazy_margin_evaluator, _margin_eval_prompt, "wf-margin-eval"),
        enabled=True,
        build_payload=lambda identity: {"identity": identity, "advancedMode": True},
    ),
]


def get_enabled_capabilities() -> list[FullCapabilityDefinition]:
    return [c for c in CAPABILITY_REGISTRY if c.enabled]


def get_evaluable_capabilities() -> list[FullCapabilityDefinition]:
    return [c for c in CAPABILITY_REGISTRY if c.enabled and c.evaluator]


def get_capability(name: str) -> FullCapabilityDefinition | None:
    return next((c for c in CAPABILITY_REGISTRY if c.name == name), None)


def build_endpoint_url(cap_def: FullCapabilityDefinition, base_url: str) -> str:
    if cap_def.api_version == "v1":
        return f"{base_url}/api/v1/{cap_def.endpoint_slug}"
    return f"{base_url}/api/capabilities/{cap_def.endpoint_slug}"
