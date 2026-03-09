"""SSE streaming endpoint for workflow progress — GET /api/workflows/{id}/stream."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from backend.lib.auth import verify_admin_request

from hephae_db.firestore.workflows import load_workflow
from backend.types import WorkflowDocument, WorkflowPhase, ProgressEvent
from backend.workflows.engine import get_active_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflow-stream"], dependencies=[Depends(verify_admin_request)])

TERMINAL_PHASES = {WorkflowPhase.COMPLETED, WorkflowPhase.FAILED, WorkflowPhase.APPROVAL}


@router.get("/{workflow_id}/stream")
async def stream_workflow(workflow_id: str):
    async def event_generator():
        # Send initial state
        workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
        if not workflow:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Workflow not found'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'initial', 'workflow': workflow.model_dump(mode='json')})}\n\n"

        if workflow.phase in TERMINAL_PHASES:
            yield f"data: {json.dumps({'type': 'done', 'phase': workflow.phase.value})}\n\n"
            return

        # Try in-process streaming first
        engine = get_active_engine(workflow_id)
        if engine:
            queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()

            def on_event(event: ProgressEvent):
                queue.put_nowait(event)

            engine.add_listener(on_event)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        if event is None:
                            break
                        yield f"data: {event.model_dump_json()}\n\n"
                        if event.phase in TERMINAL_PHASES:
                            break
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            finally:
                engine.remove_listener(on_event)
            return

        # Fallback: Firestore polling (3s intervals, max 30 min)
        last_phase = workflow.phase
        for _ in range(600):  # 600 * 3s = 30 min
            await asyncio.sleep(3)

            workflow = await load_workflow(workflow_id, model_class=WorkflowDocument)
            if not workflow:
                break

            if workflow.phase != last_phase:
                yield f"data: {json.dumps({'type': 'phase_changed', 'phase': workflow.phase.value, 'progress': workflow.progress.model_dump(mode='json')})}\n\n"
                last_phase = workflow.phase

            if workflow.phase in TERMINAL_PHASES:
                yield f"data: {json.dumps({'type': 'done', 'phase': workflow.phase.value, 'workflow': workflow.model_dump(mode='json')})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'poll', 'progress': workflow.progress.model_dump(mode='json')})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
