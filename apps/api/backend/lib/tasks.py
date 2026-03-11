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

def enqueue_agent_task(
    business_id: str,
    action_type: str,
    task_id: str,
    priority: int = 5
) -> str | None:
    """Push a task into the Cloud Tasks queue for background execution."""
    
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")
    queue = "hephae-agent-queue"
    location = os.environ.get("CLOUD_RUN_REGION", "us-central1")
    url = f"{settings.API_BASE_URL}/api/research/tasks/execute"

    # Use client from environment
    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project, location, queue)

        payload = {
            "businessId": business_id,
            "actionType": action_type,
            "taskId": task_id
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
            }
        }
        
        # Add OIDC token for secure internal Cloud Run calls
        service_account_email = f"hephae-api-sa@{project}.iam.gserviceaccount.com"
        task["http_request"]["oidc_token"] = {"service_account_email": service_account_email}

        response = client.create_task(request={"parent": parent, "task": task})
        logger.info(f"[Tasks] Enqueued {action_type} for {business_id} as {response.name}")
        return response.name

    except Exception as e:
        logger.error(f"[Tasks] Failed to enqueue task: {e}")
        # In local dev, we might not have the client, so we log and continue
        return None
