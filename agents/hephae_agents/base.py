"""Base protocol for capability runners.

Every capability exposes a stateless async runner function:
    identity/context in → report dict out.

No HTTP, no DB writes, no side effects.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CapabilityRunner(Protocol):
    """Protocol that all capability runner functions satisfy."""

    async def __call__(
        self,
        identity: dict[str, Any],
        business_context: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]: ...
