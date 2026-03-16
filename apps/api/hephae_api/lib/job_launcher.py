"""Cloud Run Job launcher — executes hephae-forge-batch as a Cloud Run Job.

Used by the interactive API service to offload heavy work (workflows,
area research) to the batch job which has more memory and Playwright.
"""

from __future__ import annotations

import logging
import os

from google.cloud import run_v2

logger = logging.getLogger(__name__)

JOB_NAME = "hephae-forge-batch"


def _get_job_path() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    region = os.environ.get("CLOUD_RUN_REGION", "us-central1")
    return f"projects/{project}/locations/{region}/jobs/{JOB_NAME}"


async def launch_batch_job(command: str, args: list[str] | None = None) -> str | None:
    """Launch hephae-forge-batch Cloud Run Job with the given command and args.

    Args:
        command: The batch subcommand (e.g. "dispatcher", "workflow", "area-research").
        args: Additional CLI arguments for the command.

    Returns:
        Execution name for tracking, or None on failure.
    """
    job_path = _get_job_path()
    full_args = ["python", "-m", "hephae_batch.main", command] + (args or [])

    logger.info(f"[JobLauncher] Launching {JOB_NAME}: {' '.join(full_args)}")

    try:
        client = run_v2.JobsAsyncClient()

        # Override the container command for this execution
        overrides = run_v2.types.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.types.RunJobRequest.Overrides.ContainerOverride(
                    args=full_args,
                )
            ],
        )

        request = run_v2.RunJobRequest(
            name=job_path,
            overrides=overrides,
        )

        operation = await client.run_job(request=request)
        # The operation returns a long-running operation — we don't wait for it
        execution_name = operation.metadata.name if operation.metadata else "unknown"
        logger.info(f"[JobLauncher] Launched execution: {execution_name}")
        return execution_name

    except Exception as e:
        logger.error(f"[JobLauncher] Failed to launch batch job: {e}")
        return None
