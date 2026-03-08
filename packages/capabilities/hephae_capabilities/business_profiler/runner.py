"""Business Profiler runner — delegates to ProfilerAgent.profile()."""

from __future__ import annotations

from typing import Any

from hephae_capabilities.business_profiler.agent import ProfilerAgent


async def run_business_profile(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Profile a business from a base identity.

    Args:
        identity: Base identity dict.
        business_context: Unused.

    Returns:
        Enriched identity dict with theme, social links, etc.
    """
    return await ProfilerAgent.profile(identity)
