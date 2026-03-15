#!/usr/bin/env python3
"""Discovery batch entrypoint — run by the discovery-batch Cloud Run Job.

On each execution, claims the next pending discovery job from Firestore
and processes it to completion. If no pending jobs exist, exits cleanly.

The Cloud Scheduler controls how often this runs (daily, weekly, etc.).
The job itself is stateless — all state lives in Firestore.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on path
_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("discovery_batch")

# ADK / Gemini setup
os.environ.setdefault("GEMINI_API_KEY", os.environ.get("GOOGLE_GENAI_API_KEY", ""))


async def main() -> int:
    from hephae_api.workflows.scheduled_discovery.orchestrator import run_next_pending_job

    logger.info("=== Discovery batch started ===")

    found = await run_next_pending_job()

    if found:
        logger.info("=== Discovery batch complete ===")
        return 0
    else:
        logger.info("=== No pending jobs — nothing to do ===")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
