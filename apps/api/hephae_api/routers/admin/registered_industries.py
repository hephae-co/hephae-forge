"""Admin API for managing registered industries."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from hephae_api.lib.auth import verify_admin_request

router = APIRouter(
    prefix="/api/registered-industries",
    tags=["registered-industries"],
    dependencies=[Depends(verify_admin_request)],
)


class RegisterIndustryRequest(BaseModel):
    industryKey: str
    displayName: str


@router.get("")
async def list_industries(status: str | None = None):
    """List all registered industries."""
    from hephae_db.firestore.registered_industries import list_registered_industries
    industries = await list_registered_industries(status=status)
    return {"industries": industries}


@router.post("")
async def register_industry(body: RegisterIndustryRequest):
    """Register a new industry for weekly national pulse generation."""
    from hephae_db.firestore.registered_industries import register_industry as db_register
    from hephae_api.workflows.orchestrators.industries import resolve, RESTAURANT

    # Validate the industry config exists
    config = resolve(body.industryKey)
    if config is RESTAURANT and body.industryKey != "restaurant":
        return {"success": False, "error": f"No IndustryConfig found for '{body.industryKey}'. Run /hephae-industry-profile first."}

    result = await db_register(body.industryKey, body.displayName)
    return {"success": True, "industry": result}


@router.get("/{industry_key}")
async def get_industry(industry_key: str):
    """Get a registered industry."""
    from hephae_db.firestore.registered_industries import get_registered_industry
    industry = await get_registered_industry(industry_key)
    if not industry:
        return {"error": "Not found"}, 404
    return industry


@router.delete("/{industry_key}")
async def unregister_industry(industry_key: str):
    """Unregister an industry."""
    from hephae_db.firestore.registered_industries import unregister_industry as db_unregister
    await db_unregister(industry_key)
    return {"success": True}


@router.post("/{industry_key}/pause")
async def pause_industry(industry_key: str):
    """Pause an industry (skip in cron)."""
    from hephae_db.firestore.registered_industries import pause_industry as db_pause
    await db_pause(industry_key)
    return {"success": True, "status": "paused"}


@router.post("/{industry_key}/resume")
async def resume_industry(industry_key: str):
    """Resume a paused industry."""
    from hephae_db.firestore.registered_industries import resume_industry as db_resume
    await db_resume(industry_key)
    return {"success": True, "status": "active"}


@router.post("/{industry_key}/generate-now")
async def generate_now(industry_key: str):
    """Manually trigger an industry pulse for this week."""
    from hephae_api.workflows.orchestrators.industry_pulse import generate_industry_pulse
    from hephae_db.firestore.registered_industries import update_last_industry_pulse

    pulse = await generate_industry_pulse(industry_key, force=True)
    pulse_id = pulse.get("id", "")
    await update_last_industry_pulse(industry_key, pulse_id)

    return {
        "success": True,
        "pulseId": pulse_id,
        "signalCount": len(pulse.get("signalsUsed", [])),
        "playbooksMatched": len(pulse.get("nationalPlaybooks", [])),
        "trendSummary": pulse.get("trendSummary", "")[:200],
    }


@router.get("/{industry_key}/latest-pulse")
async def get_latest_pulse(industry_key: str):
    """Get the most recent industry pulse for an industry."""
    from hephae_db.firestore.industry_pulse import get_latest_industry_pulse
    pulse = await get_latest_industry_pulse(industry_key)
    if not pulse:
        return {"pulse": None}
    return {
        "pulse": {
            "id": pulse.get("id"),
            "weekOf": pulse.get("weekOf"),
            "trendSummary": pulse.get("trendSummary", ""),
            "signalsUsed": pulse.get("signalsUsed", []),
            "playbooksMatched": len(pulse.get("nationalPlaybooks", [])),
            "createdAt": pulse.get("createdAt"),
        }
    }


@router.get("/{industry_key}/latest-tech-intel")
async def get_latest_tech_intel(industry_key: str):
    """Get the most recent tech intelligence profile for an industry."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence
    profiles = await list_tech_intelligence(vertical=industry_key, limit=1)
    if not profiles:
        return {"profile": None}
    p = profiles[0]
    return {
        "profile": {
            "id": p.get("id"),
            "weekOf": p.get("weekOf"),
            "weeklyHighlight": p.get("weeklyHighlight", {}),
            "aiOpportunitiesCount": len(p.get("aiOpportunities", [])),
            "platformsCount": len(p.get("platforms", {})),
            "generatedAt": p.get("generatedAt"),
        }
    }


@router.post("/{industry_key}/generate-tech-intel")
async def generate_tech_intel_now(industry_key: str):
    """Manually trigger tech intelligence generation for an industry."""
    from hephae_api.workflows.orchestrators.tech_intelligence import generate_tech_intelligence
    result = await generate_tech_intelligence(industry_key)
    if result.get("error"):
        return {"success": False, "error": result["error"]}
    return {
        "success": True,
        "weekOf": result.get("weekOf"),
        "aiOpportunitiesCount": len(result.get("aiOpportunities", [])),
        "platformsCount": len(result.get("platforms", {})),
        "weeklyHighlight": (result.get("weeklyHighlight") or {}).get("title", ""),
    }
