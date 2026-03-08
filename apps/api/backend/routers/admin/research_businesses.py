"""Business research endpoints — GET/DELETE /api/research/businesses, POST /api/research/actions."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.workflows.agents.discovery.zipcode_scanner import scan_zipcode
from backend.workflows.agents.outreach.communicator import draft_and_send_outreach
from hephae_db.firestore.businesses import get_businesses_paginated, get_business, delete_business
from hephae_db.firestore.fixtures import save_fixture_from_business
from hephae_common.firebase import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


# ---------------------------------------------------------------------------
# CDN asset generation for outreach content
# ---------------------------------------------------------------------------

# Map from latestOutputs keys to report type slugs used by social_card + CDN
_OUTPUT_KEY_TO_REPORT_TYPE = {
    "margin_surgeon": "margin",
    "seo_auditor": "seo",
    "traffic_forecaster": "traffic",
    "competitive_analyzer": "competitive",
    "marketing_swarm": "marketing",
}

# Headlines for social card generation per report type
_CARD_HEADLINES = {
    "margin": lambda d: f"${float(d.get('totalLeakage', 0)):,.0f}/mo" if d.get("totalLeakage") else f"{d.get('score', '?')}/100",
    "seo": lambda d: f"{d.get('score', '?')}/100",
    "traffic": lambda d: str(d.get("peak_slot_score", "Analyzed")),
    "competitive": lambda d: f"{d.get('competitor_count', '?')} Competitors",
    "marketing": lambda d: "Insights Ready",
}

_CARD_SUBTITLES = {
    "margin": "Profit Leakage Identified",
    "seo": "SEO Health Score",
    "traffic": "Peak Traffic Score",
    "competitive": "Competitive Landscape",
    "marketing": "Social Media Strategy",
}


async def _generate_cdn_assets(
    business_name: str,
    latest_outputs: dict,
) -> tuple[dict[str, str], dict[str, str]]:
    """Generate social cards and upload existing reports to CDN bucket.

    Returns (cdn_report_urls, cdn_card_urls) — both map report_type -> URL.
    """
    from hephae_db.gcs.storage import generate_slug, upload_social_card_to_cdn
    from hephae_common.social_card import generate_universal_social_card

    slug = generate_slug(business_name)
    cdn_report_urls: dict[str, str] = {}
    cdn_card_urls: dict[str, str] = {}

    tasks = []
    for output_key, report_type in _OUTPUT_KEY_TO_REPORT_TYPE.items():
        data = latest_outputs.get(output_key)
        if not data or not isinstance(data, dict):
            continue

        # Collect existing report URLs (already on GCS, just remap for context)
        if data.get("reportUrl"):
            cdn_report_urls[report_type] = data["reportUrl"]

        # Generate social card for each available report
        headline_fn = _CARD_HEADLINES.get(report_type, lambda d: "Report Ready")
        try:
            headline = headline_fn(data)
        except (ValueError, TypeError):
            headline = "Report Ready"
        subtitle = _CARD_SUBTITLES.get(report_type, "Analysis Complete")
        summary_text = str(data.get("summary", ""))[:80]

        async def _gen_and_upload(rt=report_type, hl=headline, st=subtitle, hi=summary_text):
            try:
                png_bytes = await generate_universal_social_card(
                    business_name=business_name,
                    report_type=rt,
                    headline=hl,
                    subtitle=st,
                    highlight=hi,
                )
                url = await upload_social_card_to_cdn(slug, rt, png_bytes)
                return rt, url
            except Exception as e:
                logger.warning(f"[CDN] Failed to generate card for {slug}/{rt}: {e}")
                return rt, ""

        tasks.append(_gen_and_upload())

    if tasks:
        results = await asyncio.gather(*tasks)
        for rt, url in results:
            if url:
                cdn_card_urls[rt] = url

    return cdn_report_urls, cdn_card_urls


class DiscoverRequest(BaseModel):
    zipCode: str


class ActionRequest(BaseModel):
    model_config = {"extra": "ignore"}

    action: str
    businessId: str | None = None
    businessIds: list[str] | None = None
    bulkAction: str | None = None
    zipCode: str | None = None
    channel: str | None = None
    fixtureType: str | None = None
    fixtureId: str | None = None
    notes: str | None = None
    agentName: str | None = None
    agentKey: str | None = None
    editedContent: str | None = None
    emailSubject: str | None = None


@router.get("/businesses")
async def get_businesses(
    zipCode: str = Query(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    category: str | None = Query(None),
    status: str | None = Query(None),
    hasEmail: bool | None = Query(None),
    name: str | None = Query(None),
):
    return await get_businesses_paginated(
        zip_code=zipCode,
        page=page,
        page_size=pageSize,
        category=category,
        status=status,
        has_email=hasEmail,
        name=name,
    )


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
                agentName=req.agentName,
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
        from backend.workflows.agents.insights.insights_agent import generate_insights
        insights = await generate_insights(biz_id)
        return {"success": True, "insights": insights}

    elif action == "outreach" and biz_id:
        channel = req.channel or "email"
        result = await draft_and_send_outreach(biz_id, channel)
        return result

    elif action == "generate-outreach-content" and biz_id:
        from hephae_capabilities.social.post_generator.runner import run_social_post_generation
        biz = await get_business(biz_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")
        identity = biz.get("identity") or {"name": biz.get("name", ""), "docId": biz_id}
        if "docId" not in identity:
            identity["docId"] = biz_id
        social_handles = {
            "instagram": (biz.get("socialLinks") or {}).get("instagram"),
            "twitter": (biz.get("socialLinks") or {}).get("twitter"),
            "facebook": (biz.get("socialLinks") or {}).get("facebook"),
        }
        latest_outputs = biz.get("latestOutputs") or {}
        business_name = identity.get("name", biz.get("name", ""))

        # Generate social cards and upload reports + cards to CDN
        cdn_report_urls, cdn_card_urls = await _generate_cdn_assets(
            business_name, latest_outputs
        )

        content = await run_social_post_generation(
            identity,
            latest_outputs=latest_outputs,
            social_handles=social_handles,
            cdn_report_urls=cdn_report_urls,
            cdn_card_urls=cdn_card_urls,
        )
        # Persist originals + CDN URLs to Firestore
        db = get_db()
        from datetime import datetime
        update_data = {
            "outreachContent.instagram.original": content["instagram"]["caption"],
            "outreachContent.instagram.reportLink": content["instagram"].get("reportLink", ""),
            "outreachContent.instagram.imageUrl": content["instagram"].get("imageUrl", ""),
            "outreachContent.facebook.original": content["facebook"]["post"],
            "outreachContent.facebook.reportLink": content["facebook"].get("reportLink", ""),
            "outreachContent.facebook.imageUrl": content["facebook"].get("imageUrl", ""),
            "outreachContent.twitter.original": content["twitter"]["tweet"],
            "outreachContent.twitter.reportLink": content["twitter"].get("reportLink", ""),
            "outreachContent.twitter.imageUrl": content["twitter"].get("imageUrl", ""),
            "outreachContent.email.original": content["email"]["body"],
            "outreachContent.email.subject": content["email"]["subject"],
            "outreachContent.contactForm.original": content["contactForm"]["message"],
            "outreachContent.cdnReportUrls": cdn_report_urls,
            "outreachContent.cdnCardUrls": cdn_card_urls,
            "outreachContent.generatedAt": datetime.utcnow(),
        }
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update, update_data
        )
        return {"success": True, "content": content}

    elif action == "save-outreach-draft" and biz_id:
        channel = req.channel or ""
        edited = req.editedContent or ""
        db = get_db()
        from datetime import datetime
        update_data = {
            f"outreachContent.{channel}.edited": edited,
            f"outreachContent.{channel}.savedAt": datetime.utcnow(),
        }
        if req.emailSubject and channel == "email":
            update_data["outreachContent.email.editedSubject"] = req.emailSubject
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update, update_data
        )
        # Save fixture for eval training
        from hephae_db.firestore.fixtures import save_fixture_from_business
        await save_fixture_from_business(
            biz_id,
            fixture_type="outreach_draft",
            notes=f"channel={channel}; edited by admin",
            agent_key=f"outreach_{channel}",
        )
        return {"success": True}

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
        fixture_id = await save_fixture_from_business(
            biz_id, fixture_type, req.notes, agent_key=req.agentKey
        )
        # Register with eval/grounding pipeline asynchronously
        import asyncio as _asyncio
        from hephae_db.eval.grounding import register_fixture
        _asyncio.ensure_future(register_fixture(fixture_id, fixture_type, req.agentKey))
        return {"success": True, "fixtureId": fixture_id}

    elif action == "remove-from-test-set":
        fixture_id = req.fixtureId
        if not fixture_id:
            raise HTTPException(status_code=400, detail="fixtureId required")
        from hephae_db.firestore.fixtures import delete_fixture
        await delete_fixture(fixture_id)
        return {"success": True}

    elif action == "start-discovery" and biz_id:
        from backend.workflows.phases.enrichment import enrich_business_profile
        from backend.workflows.phases.analysis import PROMOTE_KEYS

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
        from backend.workflows.phases.analysis import run_single_business_analysis

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

    elif action == "run-reviewer" and biz_id:
        from backend.workflows.agents.reviewer.runner import run_reviewer

        biz = await get_business(biz_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")

        identity = biz.get("identity") or {"name": biz.get("name", ""), "docId": biz_id}
        if "docId" not in identity:
            identity["docId"] = biz_id
        latest_outputs = biz.get("latestOutputs") or {}

        result = await run_reviewer(biz_id, identity, latest_outputs)
        if result:
            db = get_db()
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {"latestOutputs.reviewer": result},
            )
            return {"success": True, "result": result}
        return {"success": False, "error": "Reviewer returned no result"}

    elif action == "delete-agent-result" and biz_id:
        agent_key = req.agentKey
        if not agent_key:
            raise HTTPException(status_code=400, detail="agentKey required for delete-agent-result")
        from google.cloud.firestore import DELETE_FIELD
        db = get_db()
        await asyncio.to_thread(
            db.collection("businesses").document(biz_id).update,
            {f"latestOutputs.{agent_key}": DELETE_FIELD},
        )
        return {"success": True}

    elif action == "run-agent" and biz_id:
        from backend.workflows.capabilities.registry import get_capability
        from backend.workflows.phases.analysis import _run_capability

        agent_name = req.agentName
        if not agent_name:
            raise HTTPException(status_code=400, detail="agentName required for run-agent")

        cap_def = get_capability(agent_name)
        if not cap_def:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")

        biz = await get_business(biz_id)
        if not biz:
            raise HTTPException(status_code=404, detail="Business not found")

        identity: dict = biz.get("identity", {
            "name": biz.get("name", ""),
            "address": biz.get("address", ""),
            "docId": biz_id,
        })
        if "docId" not in identity:
            identity["docId"] = biz_id

        raw = await _run_capability(biz_id, cap_def, identity)
        if raw:
            result = cap_def.response_adapter(raw)
            db = get_db()
            await asyncio.to_thread(
                db.collection("businesses").document(biz_id).update,
                {f"latestOutputs.{cap_def.firestore_output_key}": result},
            )
            return {"success": True, "agentName": agent_name, "result": result}
        else:
            return {"success": False, "error": f"Agent {agent_name} returned no data"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
