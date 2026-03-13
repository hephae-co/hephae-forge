"""ADK observability callbacks — before/after hooks for agent execution timing and logging.

Apply to top-level and stage-boundary agents (not every sub-agent in a ParallelAgent).

Usage:
    agent = LlmAgent(
        name="MyAgent",
        before_agent_callback=log_agent_start,
        after_agent_callback=log_agent_complete,
        ...
    )
"""

from __future__ import annotations

import logging
import time


class _TraceIdFilter(logging.Filter):
    """Ensure trace_id exists on log records for Cloud Run structured logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = ""  # type: ignore[attr-defined]
        return True


logger = logging.getLogger("hephae.adk")
logger.addFilter(_TraceIdFilter())

# Also add to root logger so ALL loggers get trace_id
logging.getLogger().addFilter(_TraceIdFilter())

# Module-level dict to track start times by agent invocation
_agent_start_times: dict[str, float] = {}


def _agent_key(callback_context) -> str:
    """Build a unique key for an agent invocation from callback context."""
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"
    session_id = ""
    state = getattr(callback_context, "state", None)
    if state:
        session_id = str(id(state))
    return f"{agent_name}:{session_id}"


def log_agent_start(callback_context) -> None:
    """before_agent_callback — logs agent name and records start time."""
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"
    key = _agent_key(callback_context)
    _agent_start_times[key] = time.monotonic()
    logger.info(f"[ADK] Agent started: {agent_name}")


def log_agent_complete(callback_context) -> None:
    """after_agent_callback — logs agent name, duration, and output size."""
    agent_name = getattr(callback_context, "agent_name", None) or "unknown"
    key = _agent_key(callback_context)
    start = _agent_start_times.pop(key, None)
    duration_ms = round((time.monotonic() - start) * 1000) if start else None

    # Try to get output size from state
    output_size = None
    state = getattr(callback_context, "state", None)
    if state and isinstance(state, dict):
        # Check common output keys for size estimation
        for val in state.values():
            if isinstance(val, str) and len(val) > 10:
                output_size = len(val)
                break

    parts = [f"[ADK] Agent completed: {agent_name}"]
    if duration_ms is not None:
        parts.append(f"duration={duration_ms}ms")
    if output_size is not None:
        parts.append(f"output_size={output_size}chars")

    logger.info(" | ".join(parts))
