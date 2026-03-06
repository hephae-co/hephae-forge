"""Business research endpoints — GET/DELETE /api/research/businesses, POST /api/research/actions."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.agents.discovery.zipcode_scanner import scan_zipcode
from backend.agents.outreach.communicator import draft_and_send_outreach
from backend.lib.db.businesses import get_businesses_in_zipcode, get_business, delete_business
from backend.lib.db.fixtures import save_fixture_from_business
from backend.lib.firebase import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


class DiscoverRequest(BaseModel):
    zipCode: str


class ActionRequest(BaseModel):
    action: str
    businessId: str | None = None
    businessIds: list[str] | None = None
    bulkAction: str | None = None
    zipCode: str | None = None
    channel: str | None = None
    fixtureType: str | None = None
    notes: str | None = None


@router.get("/businesses")
async def get_businesses(zipCode: str = Query(...)):
    businesses = await get_businesses_in_zipcode(zipCode, limit=50)
    return businesses


@router.post("/businesses")
async def discover_businesses(req: DiscoverRequest):
    businesses = await scan_zipcode(req.zipCode, force=True)
    return {"count": len(businesses), "businesses": [b.model_dump() for b in businesses]}


@router.delete("/businesses")
async def delete_business_endpoint(id: str = Query(...)):
    await delete_business(id)
    return {"success": True}


@router.get("/discovery-status")
async def get_discovery_status(zipCode: str = Query(...)):
    db = get_db()
    doc = await asyncio.to_thread(db.collection("discovery_progress").document(zipCode).get)
    if doc.exists:
        return {"success": True, "progress": doc.to_dict()}
    return {"success": False, "progress": None}


@router.post("/actions")
async def execute_action(req: ActionRequest):
    action = req.action

    # Bulk actions
    if action == "bulk" and req.businessIds:
        bulk_action = req.bulkAction or "deep-dive"
        results = []
        for biz_id in req.businessIds:
            sub_req = ActionRequest(
                action=bulk_action, businessId=biz_id,
                channel=req.channel, fixtureType=req.fixtureType,
            )
            try:
                result = await _execute_single_action(sub_req)
                results.append({"businessId": biz_id, "success": True, **result})
            except Exception as e:
                results.append({"businessId": biz_id, "success": False, "error": str(e)})
        return {"success": True, "results": results}

    return await _execute_single_action(req)


async def _execute_single_action(req: ActionRequest) -> dict:
    action = req.action
    biz_id = req.businessId

    if action == "deep-dive" and biz_id:
        # Import here to avoid circular imports
        from backend.agents.insights.insights_agent import generate_insights
        insights = await generate_insights(biz_id)
        return {"success": True, "insights": insights}

    elif action == "outreach" and biz_id:
        channel = req.channel or "email"
        result = await draft_and_send_outreach(biz_id, channel)
        return result

    elif action == "delete" and biz_id:
        await delete_business(biz_id)
        return {"success": True}

    elif action == "rediscover" and biz_id:
        biz = await get_business(biz_id)
        if biz:
            zip_code = biz.get("zipCode", "")
            await delete_business(biz_id)
            if zip_code:
                businesses = await scan_zipcode(zip_code)
                return {"success": True, "discovered": len(businesses)}
        return {"success": False, "error": "Business not found"}

    elif action == "save-fixture" and biz_id:
        fixture_type = req.fixtureType or "grounding"
        fixture_id = await save_fixture_from_business(biz_id, fixture_type, req.notes)
        return {"success": True, "fixtureId": fixture_id}

    elif action == "start-discovery" and biz_id:
        from backend.workflow.phases.enrichment import enrich_business_profile
        from backend.workflow.phases.analysis import PROMOTE_KEYS

        biz = await get_business(biz_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")

        # Set status to discovering
        db = get_db()
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update,
            {"discoveryStatus": "discovering"},
        )

        try:
            enriched = await enrich_business_profile(
                biz.get("name", ""), biz.get("address", ""), biz_id
            )
            if enriched:
                top_level = {k: enriched[k] for k in PROMOTE_KEYS if k in enriched}
                await asyncio.to_thread(
                    db.collection("businesses").document(biz_id).update,
                    {
                        **top_level,
                        "identity": {**enriched, "docId": biz_id},
                        "discoveryStatus": "discovered",
                    },
                )
                return {"success": True, "discoveryStatus": "discovered"}
            else:
                await asyncio.to_thread(
                    db.collection("businesses").document(biz_id).update,
                    {"discoveryStatus": "failed"},
                )
                return {"success": False, "error": "Enrichment returned no data"}
        except Exception as e:
            logger.error(f"[Discovery] Failed for {biz_id}: {e}")
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {"discoveryStatus": "failed"},
            )
            raise HTTPException(status_code=500, detail=str(e))

    elif action == "run-analysis" and biz_id:
        from backend.workflow.phases.analysis import run_single_business_analysis

        biz = await get_business(biz_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")

        # Guard: must be discovered first (has identity or discoveryStatus == discovered)
        status = biz.get("discoveryStatus", "")
        has_identity = bool(biz.get("identity"))
        if status not in ("discovered", "analyzed") and not has_identity:
            raise HTTPException(
                status_code=400,
                detail="Business must be discovered first. Run start-discovery before analysis.",
            )

        db = get_db()
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update,
            {"discoveryStatus": "analyzing"},
        )

        try:
            result = await run_single_business_analysis(biz_id)
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {"discoveryStatus": "analyzed"},
            )
            return {"success": True, "discoveryStatus": "analyzed", **result}
        except Exception as e:
            logger.error(f"[Analysis] Failed for {biz_id}: {e}")
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {"discoveryStatus": "failed"},
            )
            raise HTTPException(status_code=500, detail=str(e))

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
