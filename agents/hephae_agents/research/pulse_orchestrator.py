"""PulseOrchestrator — top-level SequentialAgent tree for weekly pulse generation.

Wires the 4 stages into a single ADK agent tree:

  PulseOrchestrator (SequentialAgent)
  ├─ Stage 1: DataGatherer (ParallelAgent)
  │   ├─ BaseLayerFetcher (deterministic fetch)
  │   └─ ResearchFanOut (social pulse + local catalysts)
  ├─ Stage 2: PreSynthesis (ParallelAgent)
  │   ├─ PulseHistorySummarizer → trendNarrative
  │   ├─ EconomistAgent → macroReport
  │   └─ LocalScoutAgent → localReport
  ├─ Stage 3: WeeklyPulseAgent (synthesis, DEEP thinking)
  │   → pulseOutput
  └─ Stage 4: CritiqueLoop (max 2 iterations)
      ├─ PulseCritiqueAgent → critiqueResult
      └─ WeeklyPulseAgent (rewrite mode, if needed)

Usage:
    from hephae_agents.research.pulse_orchestrator import pulse_orchestrator
    # Use with ADK Runner in generate_pulse_interactive()
"""

from __future__ import annotations

from google.adk.agents import SequentialAgent

from hephae_agents.research.pulse_data_gatherer import data_gatherer
from hephae_agents.research.pulse_domain_experts import pre_synthesis
from hephae_agents.research.weekly_pulse_agent import WeeklyPulseAgent
from hephae_agents.research.pulse_critique_agent import critique_loop

pulse_orchestrator = SequentialAgent(
    name="PulseOrchestrator",
    description="5-stage weekly pulse pipeline: fetch → expert analysis → synthesis → critique.",
    sub_agents=[
        data_gatherer,     # Stage 1: Parallel data fetch + LLM research
        pre_synthesis,     # Stage 2: Domain expert reports
        WeeklyPulseAgent,  # Stage 3: Cross-signal synthesis
        critique_loop,     # Stage 4: Quality gate + rewrite loop
    ],
)
