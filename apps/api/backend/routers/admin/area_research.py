"""Area research endpoints — POST/GET /api/area-research, GET stream."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from hephae_db.firestore.research import load_area_research, list_area_research, delete_area_research
from backend.workflows.orchestrators.area_research import start_area_research, get_active_orchestrator
from backend.types import AreaResearchProgressEvent
from backend.routers.admin import _serialize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/area-research", tags=["area-research"])

TERMINAL_PHASES = {"completed", "failed"}


class CreateAreaResearchRequest(BaseModel):
    area: str
    businessType: str
    maxZipCodes: int | None = 10


@router.post("")
async def create_area_research_endpoint(req: CreateAreaResearchRequest):
    max_zips = min(req.maxZipCodes or 10, 15)

    result = await start_area_research(req.area, req.businessType, max_zips)
    return {
        "areaId": result["areaId"],
        "status": "started",
        "area": req.area,
        "businessType": req.businessType,
    }


@router.get("")
async def list_area_research_endpoint():
    docs = await list_area_research(limit=20)
    return [_serialize(d) for d in docs]


@router.get("/{area_id}")
async def get_area_research_endpoint(area_id: str):
    doc = await load_area_research(area_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Area research not found")
    return _serialize(doc)


@router.delete("/{area_id}")
async def delete_area_research_endpoint(area_id: str):
    # Block deletion if actively running
    if get_active_orchestrator(area_id):
        raise HTTPException(status_code=400, detail="Cannot delete — orchestrator is running")
    await delete_area_research(area_id)
    return {"success": True}


@router.get("/{area_id}/stream")
async def stream_area_research(area_id: str):
    async def event_generator():
        doc = await load_area_research(area_id)
        if not doc:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Not found'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'initial', 'document': _serialize(doc)})}\n\n"

        phase = doc.get("phase", "")
        if phase in TERMINAL_PHASES:
            yield f"data: {json.dumps({'type': 'done', 'phase': phase})}\n\n"
            return

        # Try in-process streaming
        orchestrator = get_active_orchestrator(area_id)
        if orchestrator:
            queue: asyncio.Queue[AreaResearchProgressEvent | None] = asyncio.Queue()

            def on_event(event: AreaResearchProgressEvent):
                queue.put_nowait(event)

            orchestrator.add_listener(on_event)
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        if event is None:
                            break
                        yield f"data: {json.dumps(_serialize(event))}\n\n"
                        evt_phase = event.phase if hasattr(event, "phase") else event.get("phase", "")
                        if evt_phase in TERMINAL_PHASES:
                            break
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            finally:
                orchestrator.remove_listener(on_event)
            return

        # Fallback: Firestore polling
        last_phase = phase
        for _ in range(600):
            await asyncio.sleep(3)
            doc = await load_area_research(area_id)
            if not doc:
                break

            phase = doc.get("phase", "")
            if phase != last_phase:
                yield f"data: {json.dumps({'type': 'phase_changed', 'phase': phase})}\n\n"
                last_phase = phase

            if phase in TERMINAL_PHASES:
                yield f"data: {json.dumps({'type': 'done', 'phase': phase})}\n\n"
                return

            progress = {
                "totalZipCodes": len(doc.get("zipCodes", [])),
                "completedZipCodes": len(doc.get("completedZipCodes", [])),
                "failedZipCodes": len(doc.get("failedZipCodes", [])),
            }
            yield f"data: {json.dumps({'type': 'poll', 'progress': progress})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
