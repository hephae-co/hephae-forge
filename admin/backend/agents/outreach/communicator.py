"""Communicator agent — formats and sends marketing outreach."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from google.adk.agents import LlmAgent

from backend.config import AgentModels
from backend.lib.adk_helpers import run_agent_to_text
from backend.lib.db.businesses import get_business
from backend.lib.email import send_email
from backend.lib.firebase import get_db
from backend.lib.model_fallback import fallback_on_error

logger = logging.getLogger(__name__)

CommunicatorAgent = LlmAgent(
    name="communicator",
    model=AgentModels.PRIMARY_MODEL,
    description="Formats marketing content for professional outreach.",
    instruction="""You are a professional marketing content formatter. Given raw marketing content and a business profile, create a polished outreach message.

Format the content as a professional email that:
- Opens with a personalized greeting using the business name
- Highlights 2-3 key findings from the analysis
- Includes a clear call to action
- Maintains a professional but friendly tone
- Is concise (under 300 words)

Return the formatted message body as plain text (not JSON).""",
    on_model_error_callback=fallback_on_error,
)


async def draft_and_send_outreach(
    business_slug: str,
    channel: str = "email",
) -> dict:
    """Draft outreach content and send via the specified channel.

    Returns {"success": bool, "sentTo": str, "error": str | None}
    """
    try:
        biz = await get_business(business_slug)
        if not biz:
            return {"success": False, "sentTo": "", "error": f"Business {business_slug} not found"}

        identity = biz.get("identity", biz)
        outputs = biz.get("latestOutputs", {})
        insights = biz.get("insights", {})

        # Check for pre-drafted content
        db = get_db()
        draft_doc = await asyncio.to_thread(
            db.collection("marketing_drafts").document(business_slug).get
        )
        draft_content = draft_doc.to_dict() if draft_doc.exists else None

        # Build prompt for the communicator
        prompt_parts = [
            f"BUSINESS: {json.dumps({k: identity.get(k) for k in ['name', 'address', 'email', 'phone'] if identity.get(k)})}",
            f"CHANNEL: {channel}",
        ]
        if draft_content:
            prompt_parts.append(f"PRE-DRAFTED CONTENT:\n{json.dumps(draft_content)}")
        if insights:
            prompt_parts.append(f"INSIGHTS:\n{json.dumps(insights)}")
        if outputs:
            # Include summaries of capability outputs
            summaries = {k: v.get("summary", "") for k, v in outputs.items() if isinstance(v, dict) and v.get("summary")}
            if summaries:
                prompt_parts.append(f"CAPABILITY SUMMARIES:\n{json.dumps(summaries)}")

        prompt = "\n\n".join(prompt_parts)

        # Format via agent
        body = await run_agent_to_text(CommunicatorAgent, prompt, app_name="communicator")

        if not body or len(body) < 50:
            return {"success": False, "sentTo": "", "error": "Agent produced insufficient content"}

        # Send via channel
        sent_to = ""
        if channel == "email":
            email = identity.get("email") or biz.get("email")
            if not email:
                return {"success": False, "sentTo": "", "error": "No email address available"}

            await send_email(
                to=email,
                subject=f"Insights for {identity.get('name', 'Your Business')}",
                text=body,
            )
            sent_to = email
        else:
            # For social channels, just log for now
            logger.info(f"[Communicator] Would send to {channel} for {business_slug}: {body[:100]}...")
            sent_to = f"{channel}:{business_slug}"

        # Update CRM state in Firestore
        crm_update = {
            "crm.status": "contacted",
            "crm.lastOutreachAt": datetime.utcnow(),
            "crm.lastChannel": channel,
        }
        await asyncio.to_thread(
            db.collection("businesses").document(business_slug).update,
            crm_update,
        )

        logger.info(f"[Communicator] Outreach sent to {sent_to} for {business_slug}")
        return {"success": True, "sentTo": sent_to, "error": None}

    except Exception as e:
        logger.error(f"[Communicator] Failed for {business_slug}: {e}")
        return {"success": False, "sentTo": "", "error": str(e)}
