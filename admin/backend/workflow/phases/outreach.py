"""Outreach phase — sends marketing outreach for approved businesses."""

from __future__ import annotations

import logging
from typing import Callable

from backend.agents.outreach.communicator import draft_and_send_outreach
from backend.types import BusinessWorkflowState, BusinessPhase

logger = logging.getLogger(__name__)


async def run_outreach_phase(
    businesses: list[BusinessWorkflowState],
    callbacks: dict[str, Callable],
) -> None:
    """Run outreach for approved businesses.

    callbacks: {onBusinessOutreachDone: async (slug, success) -> None}
    """
    approved = [b for b in businesses if b.phase == BusinessPhase.APPROVED]

    for biz in approved:
        biz.phase = BusinessPhase.OUTREACHING

        try:
            result = await draft_and_send_outreach(biz.slug)
            success = result.get("success", False)

            if success:
                biz.phase = BusinessPhase.OUTREACH_DONE
            else:
                biz.phase = BusinessPhase.OUTREACH_FAILED
                biz.outreachError = result.get("error", "Unknown error")
        except Exception as e:
            logger.error(f"[Outreach] Failed for {biz.slug}: {e}")
            biz.phase = BusinessPhase.OUTREACH_FAILED
            biz.outreachError = str(e)

        if callbacks.get("onBusinessOutreachDone"):
            await callbacks["onBusinessOutreachDone"](biz.slug, biz.phase == BusinessPhase.OUTREACH_DONE)
