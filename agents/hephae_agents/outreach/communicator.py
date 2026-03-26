"""Communicator agent — formats and sends marketing outreach."""

from __future__ import annotations

import asyncio
import html as _html
import json
import logging
import os
from datetime import datetime

from google.adk.agents import LlmAgent

from hephae_api.config import AgentModels
from hephae_common.adk_helpers import run_agent_to_text
from hephae_db.firestore.businesses import get_business
from hephae_common.email import send_email
from hephae_common.firebase import get_db
from hephae_common.model_fallback import fallback_on_error

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


def _build_outreach_html(biz_name: str, body: str, unsub_url: str) -> str:
    """Wrap plain-text outreach body in a simple branded HTML email."""
    body_html = _html.escape(body).replace("\n", "<br/>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Insights for {_html.escape(biz_name)}</title>
</head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
          <tr>
            <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:28px 40px;text-align:center;">
              <div style="font-size:22px;font-weight:800;color:#fff;">Hephae</div>
              <div style="font-size:12px;color:rgba(255,255,255,0.7);">Surgical Intelligence for Local Businesses</div>
            </td>
          </tr>
          <tr>
            <td style="background:rgba(255,255,255,0.03);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:36px 40px;">
              <div style="font-size:15px;color:#e2e8f0;line-height:1.7;">{body_html}</div>
            </td>
          </tr>
          <tr>
            <td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 16px 16px;padding:20px 40px;text-align:center;">
              <div style="font-size:11px;color:rgba(226,232,240,0.3);line-height:1.6;">
                Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a> &mdash; Surgical intelligence, delivered.<br/>
                <a href="{_html.escape(unsub_url)}" style="color:rgba(226,232,240,0.3);text-decoration:underline;">Unsubscribe</a>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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

            # CAN-SPAM: check unsubscribe list before sending
            from hephae_db.firestore.email_unsubscribes import is_unsubscribed, generate_unsubscribe_token
            if await is_unsubscribed(email):
                logger.info(f"[Communicator] Skipping {email} — unsubscribed")
                return {"success": False, "sentTo": "", "error": "recipient_unsubscribed"}

            # Build unsubscribe URL and HTML email
            base_url = os.environ.get("FORGE_WEB_URL", "https://hephae.co")
            token = generate_unsubscribe_token(email)
            unsub_url = f"{base_url}/api/unsubscribe?email={_html.escape(email)}&token={token}"

            biz_name = identity.get("name", "Your Business")
            html_content = _build_outreach_html(biz_name, body, unsub_url)
            plain_text = body + f"\n\n---\nTo unsubscribe: {unsub_url}"

            await send_email(
                to=email,
                subject=f"Insights for {biz_name}",
                text=plain_text,
                html_content=html_content,
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
