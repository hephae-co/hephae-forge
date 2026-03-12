"""Cloud Tasks enqueuer for agentic workflows."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from backend.config import settings

logger = logging.getLogger(__name__)

def _get_api_base_url() -> str:
    """Resolve the API service URL for Cloud Tasks callbacks.

    Priority: API_BASE_URL env var > Cloud Run K_SERVICE auto-detection > empty (error).
    """
    base = settings.API_BASE_URL
    if base:
        return base.rstrip("/")

    # Auto-detect on Cloud Run: K_SERVICE is set automatically
    k_service = os.environ.get("K_SERVICE")
    region = os.environ.get("CLOUD_RUN_REGION", "us-central1")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    if k_service:
        return f"https://{k_service}-{project}.{region}.run.app"

    return ""


def enqueue_agent_task(
    business_id: str,
    action_type: str,
    task_id: str,
    priority: int = 5,
    metadata: dict[str, Any] | None = None,
    dispatch_deadline_seconds: int | None = None,
) -> str | None:
    """Push a task into the Cloud Tasks queue for background execution."""

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    queue = "hephae-agent-queue"
    location = os.environ.get("CLOUD_RUN_REGION", "us-central1")

    base_url = _get_api_base_url()
    if not base_url:
        logger.error("[Tasks] Cannot enqueue: API_BASE_URL not set and not running on Cloud Run")
        return None

    url = f"{base_url}/api/research/tasks/execute"

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project, location, queue)

        payload: dict[str, Any] = {
            "businessId": business_id,
            "actionType": action_type,
            "taskId": task_id,
        }
        if metadata:
            payload["metadata"] = metadata

        task: dict[str, Any] = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
            }
        }

        # Add OIDC token for secure internal Cloud Run calls
        service_account_email = f"hephae-forge@{project}.iam.gserviceaccount.com"
        task["http_request"]["oidc_token"] = {"service_account_email": service_account_email}

        # Set dispatch deadline (default Cloud Tasks is 10 min, analysis can take longer)
        if dispatch_deadline_seconds:
            task["dispatch_deadline"] = {"seconds": dispatch_deadline_seconds}

        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"[Tasks] Enqueued {action_type} for {business_id} as {response.name}")
        return response.name

    except Exception as e:
        logger.error(f"[Tasks] Failed to enqueue task: {e}")
        return None
