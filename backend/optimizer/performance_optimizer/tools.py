"""Performance Optimizer tools — static analysis of pipeline topology and bottlenecks."""

from __future__ import annotations

import importlib
import inspect
import logging
import re

logger = logging.getLogger(__name__)


async def scan_pipeline_structure() -> dict:
    """Scan all agent modules and map their execution topology.

    Returns:
        dict with pipelines list showing Sequential/Parallel composition.
    """
    pipelines = []

    # Discovery pipeline
    try:
        mod = importlib.import_module("backend.agents.discovery.agent")
        pipeline = getattr(mod, "discovery_pipeline", None)
        if pipeline:
            stages = []
            for sub in getattr(pipeline, "sub_agents", []):
                stage_info = {"name": sub.name, "type": type(sub).__name__}
                if hasattr(sub, "sub_agents"):
                    stage_info["sub_agents"] = [a.name for a in sub.sub_agents]
                    stage_info["count"] = len(sub.sub_agents)
                stages.append(stage_info)
            pipelines.append({
                "name": "DiscoveryPipeline",
                "type": "SequentialAgent",
                "stages": len(stages),
                "topology": stages,
            })
    except Exception as e:
        logger.warning(f"[PerfOptimizer] Could not analyze discovery pipeline: {e}")

    # Margin analyzer
    try:
        mod = importlib.import_module("backend.agents.margin_analyzer.agent")
        orch = getattr(mod, "margin_surgery_orchestrator", None)
        if orch:
            stages = [{"name": a.name, "type": type(a).__name__} for a in getattr(orch, "sub_agents", [])]
            pipelines.append({
                "name": "MarginSurgeryOrchestrator",
                "type": "SequentialAgent",
                "stages": len(stages),
                "topology": stages,
                "parallelization_opportunity": "BenchmarkerAgent + CommodityWatchdogAgent could run in parallel (both only need parsedMenuItems)",
            })
    except Exception as e:
        logger.warning(f"[PerfOptimizer] Could not analyze margin analyzer: {e}")

    # Traffic forecaster
    try:
        mod = importlib.import_module("backend.agents.traffic_forecaster.agent")
        # ForecasterAgent uses a ParallelAgent internally for context gathering
        pipelines.append({
            "name": "TrafficForecaster",
            "type": "Custom (ParallelAgent + synthesis)",
            "stages": 2,
            "topology": [
                {"name": "ContextGatheringPipeline", "type": "ParallelAgent",
                 "sub_agents": ["PoiGatherer", "WeatherGatherer", "EventsGatherer"], "count": 3},
                {"name": "Synthesis", "type": "direct Gemini call"},
            ],
        })
    except Exception as e:
        logger.warning(f"[PerfOptimizer] Could not analyze traffic forecaster: {e}")

    # SEO auditor
    pipelines.append({
        "name": "SEOAuditor",
        "type": "Single LlmAgent",
        "stages": 1,
        "topology": [{"name": "seoAuditor", "type": "LlmAgent"}],
        "note": "Pro model with flash-lite fallback",
    })

    # Competitive analysis
    pipelines.append({
        "name": "CompetitiveAnalysis",
        "type": "2 loose agents (no orchestrator)",
        "stages": 2,
        "topology": [
            {"name": "CompetitorProfilerAgent", "type": "LlmAgent"},
            {"name": "MarketPositioningAgent", "type": "LlmAgent"},
        ],
        "note": "Run sequentially in router code, not via SequentialAgent",
    })

    # Marketing swarm
    pipelines.append({
        "name": "MarketingSwarm",
        "type": "3 sequential agents (code-level orchestration)",
        "stages": 3,
        "topology": [
            {"name": "CreativeDirectorAgent", "type": "LlmAgent"},
            {"name": "PlatformRouterAgent", "type": "LlmAgent"},
            {"name": "CopywriterAgent (conditional)", "type": "LlmAgent"},
        ],
        "note": "Orchestrated by run_marketing_pipeline() function, not SequentialAgent",
    })

    return {
        "pipelines": pipelines,
        "total_pipelines": len(pipelines),
    }


async def detect_bottlenecks() -> dict:
    """Scan the codebase for known performance bottlenecks.

    Returns:
        dict with bottlenecks list.
    """
    bottlenecks = []

    # Check for Playwright cold-start patterns
    for module_path in ["backend.routers.discover", "backend.routers.analyze"]:
        try:
            mod = importlib.import_module(module_path)
            source = inspect.getsource(mod)
            if "async_playwright" in source:
                bottlenecks.append({
                    "file": module_path.replace(".", "/") + ".py",
                    "pattern": "Playwright browser cold-start",
                    "severity": "medium",
                    "description": "Creates new browser context per request (~2-5s startup).",
                    "recommendation": "Pool browser instances or use a shared browser context.",
                })
        except Exception:
            pass

    # Check for inline httpx client creation
    for module_path in [
        "backend.agents.shared_tools.validate_url",
        "backend.agents.shared_tools.crawl4ai",
    ]:
        try:
            mod = importlib.import_module(module_path)
            source = inspect.getsource(mod)
            if "httpx.AsyncClient(" in source:
                bottlenecks.append({
                    "file": module_path.replace(".", "/") + ".py",
                    "pattern": "Inline httpx client creation",
                    "severity": "low",
                    "description": "Creates new httpx.AsyncClient per call — no connection reuse.",
                    "recommendation": "Use a module-level client with connection pooling.",
                })
        except Exception:
            pass

    # Check for hardcoded sleeps
    for module_path in ["backend.routers.discover", "backend.routers.analyze"]:
        try:
            mod = importlib.import_module(module_path)
            source = inspect.getsource(mod)
            sleep_matches = re.findall(r"wait_for_timeout\((\d+)\)", source)
            for ms in sleep_matches:
                bottlenecks.append({
                    "file": module_path.replace(".", "/") + ".py",
                    "pattern": f"Hardcoded sleep ({ms}ms)",
                    "severity": "low",
                    "description": f"await page.wait_for_timeout({ms}) adds fixed latency.",
                    "recommendation": "Use wait_for_selector or network idle detection instead.",
                })
        except Exception:
            pass

    # Check for sequential agents that could parallelize
    try:
        mod = importlib.import_module("backend.agents.margin_analyzer.agent")
        orch = getattr(mod, "margin_surgery_orchestrator", None)
        if orch and len(getattr(orch, "sub_agents", [])) >= 4:
            bottlenecks.append({
                "file": "backend/agents/margin_analyzer/agent.py",
                "pattern": "Sequential agents that could parallelize",
                "severity": "high",
                "description": "BenchmarkerAgent and CommodityWatchdogAgent both only depend on "
                               "parsedMenuItems but run sequentially. Could run in parallel.",
                "recommendation": "Wrap BenchmarkerAgent + CommodityWatchdogAgent in ParallelAgent, "
                                  "then SurgeonAgent reads both outputs, then AdvisorAgent.",
            })
    except Exception:
        pass

    # Large data injection
    bottlenecks.append({
        "file": "backend/agents/discovery/agent.py",
        "pattern": "Large context injection (30K chars)",
        "severity": "medium",
        "description": "_with_raw_data injects up to 30K chars into every fan-out agent. "
                       "Some agents (e.g. MapsAgent, ContactAgent) only need specific sections.",
        "recommendation": "Create targeted injection helpers that extract relevant sections "
                          "per agent instead of passing full raw data.",
    })

    return {
        "bottlenecks": bottlenecks,
        "total": len(bottlenecks),
    }


async def analyze_async_patterns() -> dict:
    """Analyze async/await patterns and concurrency issues in the codebase.

    Returns:
        dict with patterns list.
    """
    patterns = []

    # Scan for fire-and-forget asyncio.create_task
    for module_path in [
        "backend.routers.discover",
        "backend.routers.capabilities.seo",
        "backend.routers.capabilities.competitive",
        "backend.routers.capabilities.traffic",
        "backend.routers.capabilities.marketing",
    ]:
        try:
            mod = importlib.import_module(module_path)
            source = inspect.getsource(mod)
            task_count = source.count("asyncio.create_task(")
            if task_count > 0:
                patterns.append({
                    "file": module_path.replace(".", "/") + ".py",
                    "pattern": "fire_and_forget",
                    "count": task_count,
                    "issue": f"{task_count} fire-and-forget task(s) with no error tracking. "
                             "Exceptions in these tasks are silently swallowed.",
                    "recommendation": "Add a background task error handler or use TaskGroup for structured concurrency.",
                })
        except Exception:
            pass

    # Scan for run_in_executor
    for module_path in [
        "backend.lib.db.write_agent_result",
        "backend.lib.db.write_discovery",
        "backend.lib.db.write_interaction",
    ]:
        try:
            mod = importlib.import_module(module_path)
            source = inspect.getsource(mod)
            if "run_in_executor" in source:
                patterns.append({
                    "file": module_path.replace(".", "/") + ".py",
                    "pattern": "run_in_executor",
                    "issue": "Uses run_in_executor with asyncio.run() inside — creates a new event loop "
                             "per call. Could use direct async BQ client instead.",
                    "recommendation": "Use google-cloud-bigquery async client or aiohttp-based BQ insert.",
                })
        except Exception:
            pass

    return {
        "patterns": patterns,
        "total": len(patterns),
    }
