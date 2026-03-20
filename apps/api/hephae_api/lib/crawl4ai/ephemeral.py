"""Ephemeral crawl4ai instance management for zipcode discovery.

Spins up a dedicated crawl4ai Cloud Run service for a discovery run,
then tears it down after completion. Prevents rate-limiting the shared
crawl4ai instance and allows parallel crawling.

Usage:
    url = await create_ephemeral_crawl4ai("discovery-07110")
    # ... use url for crawling ...
    await destroy_ephemeral_crawl4ai("discovery-07110")

The ephemeral service:
- Uses the same Docker image as the shared hephae-crawl4ai service
- Same service account, same region
- min-instances=1 (pre-warmed, no cold start)
- max-instances=1 (single instance, cheaper)
- Auto-deleted after use
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
REGION = "us-central1"
SERVICE_ACCOUNT = f"hephae-forge@{PROJECT_ID}.iam.gserviceaccount.com"
CRAWL4AI_IMAGE = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/cloud-run-source-deploy/hephae-crawl4ai:latest"


async def create_ephemeral_crawl4ai(name: str) -> str | None:
    """Deploy an ephemeral crawl4ai Cloud Run service.

    Args:
        name: Unique name for this instance (e.g., "discovery-07110").
              Will be prefixed with "crawl4ai-" for the service name.

    Returns:
        The service URL if successful, None on failure.
    """
    service_name = f"crawl4ai-{name}"

    logger.info(f"[EphemeralCrawl4ai] Creating {service_name}")

    try:
        from google.cloud import run_v2

        client = run_v2.ServicesAsyncClient()
        parent = f"projects/{PROJECT_ID}/locations/{REGION}"

        service = run_v2.Service(
            template=run_v2.RevisionTemplate(
                scaling=run_v2.RevisionScaling(
                    min_instance_count=1,
                    max_instance_count=5,  # 5 parallel crawlers
                ),
                containers=[
                    run_v2.Container(
                        image=CRAWL4AI_IMAGE,
                        ports=[run_v2.ContainerPort(container_port=11235)],
                        resources=run_v2.ResourceRequirements(
                            limits={"cpu": "2", "memory": "2Gi"},
                        ),
                    ),
                ],
                service_account=SERVICE_ACCOUNT,
                timeout={"seconds": 300},
            ),
        )

        operation = await client.create_service(
            parent=parent,
            service=service,
            service_id=service_name,
        )

        result = await operation.result(timeout=120)
        url = result.uri

        # Grant invoker access to our service account
        from google.iam.v1 import iam_policy_pb2, policy_pb2

        policy = await client.get_iam_policy(
            request={"resource": result.name}
        )
        policy.bindings.append(
            policy_pb2.Binding(
                role="roles/run.invoker",
                members=[f"serviceAccount:{SERVICE_ACCOUNT}"],
            )
        )
        await client.set_iam_policy(
            request=iam_policy_pb2.SetIamPolicyRequest(
                resource=result.name,
                policy=policy,
            )
        )

        logger.info(f"[EphemeralCrawl4ai] Created {service_name} at {url}")
        return url

    except Exception as e:
        logger.error(f"[EphemeralCrawl4ai] Failed to create {service_name}: {e}")

        # Fallback: use the shared crawl4ai instance
        shared_url = os.environ.get("CRAWL4AI_URL", "")
        if shared_url:
            logger.info(f"[EphemeralCrawl4ai] Falling back to shared: {shared_url}")
            return shared_url

        return None


async def destroy_ephemeral_crawl4ai(name: str) -> bool:
    """Delete an ephemeral crawl4ai Cloud Run service.

    Args:
        name: Same name used in create_ephemeral_crawl4ai.

    Returns:
        True if deleted, False on failure.
    """
    service_name = f"crawl4ai-{name}"

    logger.info(f"[EphemeralCrawl4ai] Destroying {service_name}")

    try:
        from google.cloud import run_v2

        client = run_v2.ServicesAsyncClient()
        service_path = f"projects/{PROJECT_ID}/locations/{REGION}/services/{service_name}"

        operation = await client.delete_service(name=service_path)
        await operation.result(timeout=60)

        logger.info(f"[EphemeralCrawl4ai] Deleted {service_name}")
        return True

    except Exception as e:
        logger.error(f"[EphemeralCrawl4ai] Failed to delete {service_name}: {e}")
        return False


async def get_ephemeral_crawl4ai_url(name: str) -> str | None:
    """Get the URL of an existing ephemeral crawl4ai service.

    Returns None if the service doesn't exist.
    """
    service_name = f"crawl4ai-{name}"

    try:
        from google.cloud import run_v2

        client = run_v2.ServicesAsyncClient()
        service_path = f"projects/{PROJECT_ID}/locations/{REGION}/services/{service_name}"

        service = await client.get_service(name=service_path)
        return service.uri

    except Exception:
        return None
