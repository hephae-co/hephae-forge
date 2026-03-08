"""Traffic Forecaster runner — stateless async function.

Delegates to ForecasterAgent.forecast() which already implements the runner pattern.
"""

from __future__ import annotations

from typing import Any

from hephae_capabilities.traffic_forecaster.agent import ForecasterAgent


async def run_traffic_forecast(
    identity: dict[str, Any],
    business_context: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run traffic forecast pipeline.

    Args:
        identity: Enriched identity dict (must have name).
        business_context: Optional BusinessContext with admin data.

    Returns:
        Forecast dict with business, summary, forecast array.
    """
    if not identity.get("name"):
        raise ValueError("Missing identity name for Traffic Forecaster")

    return await ForecasterAgent.forecast(identity, business_context=business_context)
