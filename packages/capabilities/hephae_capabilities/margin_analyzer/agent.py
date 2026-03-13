"""
Margin analyzer agents — 5 LlmAgents + SequentialAgent orchestrator.

Pipeline: VisionIntake → Benchmarker → CommodityWatchdog → Surgeon → Advisor
"""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from hephae_common.model_config import AgentModels
from hephae_common.model_fallback import fallback_on_error
from hephae_common.adk_callbacks import log_agent_start, log_agent_complete
from hephae_db.schemas.agent_outputs import (
    MenuIntakeOutput,
    BenchmarkOutput,
    CommodityOutput,
    AdvisorOutput,
)
from hephae_capabilities.margin_analyzer.prompts import (
    VISION_INTAKE_INSTRUCTION,
    BENCHMARKER_INSTRUCTION,
    COMMODITY_WATCHDOG_INSTRUCTION,
    SURGEON_INSTRUCTION,
    ADVISOR_INSTRUCTION,
)
from hephae_capabilities.margin_analyzer.tools import (
    benchmark_tool,
    commodity_inflation_tool,
    surgery_tool,
)


# ---------------------------------------------------------------------------
# Individual agents
# ---------------------------------------------------------------------------

vision_intake_agent = LlmAgent(
    name="VisionIntakeAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=VISION_INTAKE_INSTRUCTION,
    output_key="parsedMenuItems",
    output_schema=MenuIntakeOutput,
    on_model_error_callback=fallback_on_error,
)

benchmarker_agent = LlmAgent(
    name="BenchmarkerAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=BENCHMARKER_INSTRUCTION,
    tools=[benchmark_tool],
    output_key="competitorBenchmarks",
    output_schema=BenchmarkOutput,
    on_model_error_callback=fallback_on_error,
)

commodity_watchdog_agent = LlmAgent(
    name="CommodityWatchdogAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=COMMODITY_WATCHDOG_INSTRUCTION,
    tools=[commodity_inflation_tool],
    output_key="commodityTrends",
    output_schema=CommodityOutput,
    on_model_error_callback=fallback_on_error,
)

surgeon_agent = LlmAgent(
    name="SurgeonAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=SURGEON_INSTRUCTION,
    tools=[surgery_tool],
    output_key="menuAnalysis",
    on_model_error_callback=fallback_on_error,
)

advisor_agent = LlmAgent(
    name="AdvisorAgent",
    model=AgentModels.PRIMARY_MODEL,
    instruction=ADVISOR_INSTRUCTION,
    output_key="strategicAdvice",
    output_schema=AdvisorOutput,
    on_model_error_callback=fallback_on_error,
)


# ---------------------------------------------------------------------------
# Parallel fan-out: Benchmarker + CommodityWatchdog (both read parsedMenuItems)
# ---------------------------------------------------------------------------

benchmark_and_commodity = ParallelAgent(
    name="BenchmarkAndCommodity",
    description="Run Benchmarker and CommodityWatchdog in parallel — both read parsedMenuItems, write to independent keys.",
    sub_agents=[benchmarker_agent, commodity_watchdog_agent],
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

margin_surgery_orchestrator = SequentialAgent(
    name="MarginSurgeryOrchestrator",
    description="Executes the full margin surgeon pipeline: VisionIntake → (Benchmarker || CommodityWatchdog) → Surgeon → Advisor.",
    sub_agents=[
        vision_intake_agent,
        benchmark_and_commodity,
        surgeon_agent,
        advisor_agent,
    ],
    before_agent_callback=log_agent_start,
    after_agent_callback=log_agent_complete,
)
