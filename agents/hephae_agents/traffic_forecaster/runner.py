"""Traffic Forecaster runner — stateless async function.

Delegates to ForecasterAgent.forecast() which already implements the runner pattern.
"""

from __future__ import annotations

from typing import Any

from hephae_agents.traffic_forecaster.agent import ForecasterAgent


async def run_traffic_forecast(
    identity: dict[str, Any],
    business_context: Any | None = None,
    skip_synthesis: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run traffic forecast pipeline.

    Args:
        identity: Enriched identity dict (must have name).
        business_context: Optional BusinessContext with admin data.
        skip_synthesis: If True, run gathering only and return deferred intel data.

    Returns:
        Forecast dict with business, summary, forecast array (or deferred intel if skip_synthesis).
    """
    if not identity.get("name"):
        raise ValueError("Missing identity name for Traffic Forecaster")

    return await ForecasterAgent.forecast(
        identity, business_context=business_context, skip_synthesis=skip_synthesis, **kwargs
    )
