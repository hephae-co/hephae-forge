"""Heartbeat runner — re-run capabilities, compute deltas, send email digests."""

from __future__ import annotations
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Map user-facing capability names to registry names
_CAP_NAME_MAP = {
    "margin": "margin_surgeon",
}


def compute_delta(cap_name: str, prev: dict | None, current: dict) -> dict:
    """Compare previous and current snapshots for a capability."""
    if not prev:
        return {
            "capability": cap_name, "significant": True, "type": "first_run",
            "direction": "new", "scoreChange": 0,
            "prevScore": None, "newScore": current.get("score"),
            "newSummary": current.get("summary"),
            "reportUrl": current.get("reportUrl"),
        }

    prev_score = prev.get("score") or 0
    new_score = current.get("score") or 0
    score_change = new_score - prev_score
    significant = abs(score_change) >= 5
    direction = "improved" if score_change > 0 else "declined" if score_change < 0 else "stable"

    return {
        "capability": cap_name,
        "significant": significant,
        "direction": direction,
        "scoreChange": score_change,
        "prevScore": prev.get("score"),
        "newScore": current.get("score"),
        "newSummary": current.get("summary"),
        "reportUrl": current.get("reportUrl"),
    }


async def run_heartbeat_cycle(heartbeat: dict) -> dict:
    """Re-run selected capabilities for a business, compute deltas, send email."""
    from hephae_db.firestore.businesses import get_business
    from hephae_db.firestore.users import get_user
    from hephae_db.firestore.heartbeats import record_heartbeat_run
    from hephae_db.context.business_context import build_business_context
    from backend.workflows.capabilities.registry import get_capability

    heartbeat_id = heartbeat["id"]
    biz = await get_business(heartbeat["businessSlug"])
    if not biz:
        logger.warning(f"[Heartbeat] Business not found: {heartbeat['businessSlug']}")
        return {"status": "skipped", "reason": "business_not_found"}

    identity = biz.get("identity", biz)
    # get_user is synchronous (Firestore sync SDK)
    user = get_user(heartbeat["uid"])
    user_email = user.get("email") if user else None

    if not user_email:
        logger.warning(f"[Heartbeat] No email for user {heartbeat['uid']}")
        return {"status": "skipped", "reason": "no_email"}

    # Build business context for capabilities that need it
    try:
        business_context = await build_business_context(heartbeat["businessSlug"])
    except Exception:
        business_context = None

    new_snapshot = {}
    deltas = []

    for cap_name in heartbeat.get("capabilities", []):
        registry_name = _CAP_NAME_MAP.get(cap_name, cap_name)
        cap = get_capability(registry_name)
        if not cap:
            logger.warning(f"[Heartbeat] Unknown capability: {cap_name}")
            continue

        try:
            # Run the capability using the existing runner
            result = await cap.runner(identity, business_context)
            adapted = cap.response_adapter(result)

            new_snapshot[cap_name] = {
                "score": adapted.get("score"),
                "summary": adapted.get("summary"),
                "reportUrl": adapted.get("reportUrl"),
                "runAt": datetime.utcnow(),
            }

            # Compute delta vs last snapshot
            prev = heartbeat.get("lastSnapshot", {}).get(cap_name)
            delta = compute_delta(cap_name, prev, new_snapshot[cap_name])
            deltas.append(delta)

        except Exception as e:
            logger.error(f"[Heartbeat] Failed to run {cap_name} for {heartbeat['businessSlug']}: {e}")
            # Keep previous snapshot for this capability
            prev = heartbeat.get("lastSnapshot", {}).get(cap_name)
            if prev:
                new_snapshot[cap_name] = prev

    # Determine if any significant changes
    significant_deltas = [d for d in deltas if d.get("significant")]
    has_changes = len(significant_deltas) > 0
    consecutive_oks = heartbeat.get("consecutiveOks", 0)

    # Send email
    try:
        if has_changes:
            await _send_digest_email(user_email, heartbeat, deltas, new_snapshot)
        elif consecutive_oks < 3:
            # Send brief "all clear" — suppress after 3 consecutive OKs
            await _send_ok_email(user_email, heartbeat, new_snapshot)
        else:
            logger.info(f"[Heartbeat] Suppressing OK email for {heartbeat_id} (consecutive OKs: {consecutive_oks})")
    except Exception as e:
        logger.error(f"[Heartbeat] Email failed for {heartbeat_id}: {e}")

    # Compute next run
    next_run = datetime.utcnow() + timedelta(days=7)

    # Build snapshot with deltas key for record_heartbeat_run
    # (record_heartbeat_run checks snapshot.get("deltas") to manage consecutiveOks)
    snapshot_with_deltas = {**new_snapshot}
    if has_changes:
        snapshot_with_deltas["deltas"] = significant_deltas

    # Record the run
    await record_heartbeat_run(
        heartbeat_id,
        snapshot=snapshot_with_deltas,
        next_run=next_run,
    )

    return {
        "status": "completed",
        "capabilities_run": len(new_snapshot),
        "significant_changes": len(significant_deltas),
        "email_sent": True,
    }


# -- Email helpers ----------------------------------------------------------

CAPABILITY_DISPLAY = {
    "seo": {"label": "SEO Deep Audit", "accent": "#a78bfa", "icon": "\U0001f50d"},
    "margin": {"label": "Margin Surgery", "accent": "#f87171", "icon": "\U0001f489"},
    "traffic": {"label": "Foot Traffic", "accent": "#4ade80", "icon": "\U0001f6b6"},
    "competitive": {"label": "Competitive Intel", "accent": "#fb923c", "icon": "\u2694\ufe0f"},
    "social": {"label": "Social Media", "accent": "#38bdf8", "icon": "\U0001f4f1"},
}

DIRECTION_SYMBOLS = {"improved": "\u25b2", "declined": "\u25bc", "stable": "\u2014", "new": "\u2605"}


async def _send_digest_email(to: str, heartbeat: dict, deltas: list[dict], snapshot: dict) -> None:
    """Send the full weekly digest email with change details."""
    from hephae_common.email import send_email

    biz_name = heartbeat.get("businessName", "Your Business")
    subject = f"\U0001f493 Heartbeat: {biz_name} \u2014 Changes Detected"

    html = _build_digest_html(biz_name, deltas, snapshot)
    text = f"Heartbeat update for {biz_name}: {len([d for d in deltas if d['significant']])} capabilities changed this week."

    await send_email(to, subject, text, html_content=html, from_addr="Chris from Hephae <chris@hephae.co>")


async def _send_ok_email(to: str, heartbeat: dict, snapshot: dict) -> None:
    """Send a brief all-clear email."""
    from hephae_common.email import send_email

    biz_name = heartbeat.get("businessName", "Your Business")
    subject = f"\U0001f493 Heartbeat: {biz_name} \u2014 All Clear \u2713"

    html = _build_ok_html(biz_name, snapshot)
    text = f"Weekly heartbeat for {biz_name}: no significant changes detected. Everything is running smoothly."

    await send_email(to, subject, text, html_content=html, from_addr="Chris from Hephae <chris@hephae.co>")


def _build_digest_html(biz_name: str, deltas: list[dict], snapshot: dict) -> str:
    """Build the HTML for the weekly digest email."""
    import html as html_module
    esc = html_module.escape

    # Build capability cards
    cards_html = ""
    for delta in deltas:
        cap = delta["capability"]
        display = CAPABILITY_DISPLAY.get(cap, {"label": cap, "accent": "#818cf8", "icon": "\U0001f4ca"})
        direction = delta.get("direction", "stable")
        symbol = DIRECTION_SYMBOLS.get(direction, "\u2014")

        score_text = ""
        if delta.get("prevScore") is not None and delta.get("newScore") is not None:
            score_text = f"{delta['prevScore']} \u2192 {delta['newScore']} {symbol}"
        elif delta.get("newScore") is not None:
            score_text = f"{delta['newScore']} {symbol}"
        else:
            score_text = f"{direction.title()} {symbol}"

        # Color based on direction
        direction_color = "#4ade80" if direction == "improved" else "#f87171" if direction == "declined" else "#94a3b8"

        report_link = ""
        if delta.get("reportUrl"):
            report_link = f'<a href="{esc(delta["reportUrl"])}" style="color:{display["accent"]};text-decoration:none;font-size:13px;font-weight:600;">View Report \u2192</a>'

        summary = esc(delta.get("newSummary", "")[:200]) if delta.get("newSummary") else ""

        cards_html += f"""
        <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-left:3px solid {display['accent']};border-radius:8px;padding:16px 20px;margin-bottom:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:13px;font-weight:700;color:#e2e8f0;">{display['icon']} {esc(display['label'])}</span>
            <span style="font-size:13px;font-weight:700;color:{direction_color};">{score_text}</span>
          </div>
          {"<div style='font-size:13px;color:#94a3b8;line-height:1.5;margin-bottom:8px;'>" + summary + "</div>" if summary else ""}
          {report_link}
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;">
    <tr><td align="center" style="padding:40px 20px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
        <tr><td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:24px 40px;text-align:center;">
          <div style="font-size:22px;font-weight:800;color:#ffffff;">\U0001f493 Hephae Heartbeat</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-top:4px;">Weekly Intelligence Digest</div>
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.03);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:32px 32px 24px;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:18px;font-weight:700;color:#e2e8f0;">\U0001f4cd {esc(biz_name)}</span>
          </div>
          {cards_html}
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 16px 16px;padding:20px 32px;text-align:center;">
          <div style="font-size:11px;color:rgba(226,232,240,0.3);line-height:1.6;">
            Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a> \u00b7 <a href="https://hephae.co/forge" style="color:#818cf8;text-decoration:none;">Manage Heartbeats</a>
          </div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _build_ok_html(biz_name: str, snapshot: dict) -> str:
    """Build the HTML for the all-clear email."""
    import html as html_module
    esc = html_module.escape

    # Build quick stats
    stats_html = ""
    for cap_name, snap in snapshot.items():
        if cap_name == "deltas":
            continue
        display = CAPABILITY_DISPLAY.get(cap_name, {"label": cap_name, "icon": "\U0001f4ca"})
        score = snap.get("score")
        score_text = f"{score}" if score is not None else "N/A"
        stats_html += f'<div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">\u2022 {display["label"]}: {score_text} (stable)</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/></head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;">
    <tr><td align="center" style="padding:40px 20px;">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
        <tr><td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:24px 40px;text-align:center;">
          <div style="font-size:22px;font-weight:800;color:#ffffff;">\U0001f493 Hephae Heartbeat</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-top:4px;">Weekly Check-in</div>
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.03);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:32px;">
          <div style="text-align:center;margin-bottom:20px;">
            <span style="font-size:18px;font-weight:700;color:#e2e8f0;">\U0001f4cd {esc(biz_name)} \u2014 All Clear \u2713</span>
          </div>
          <div style="text-align:center;font-size:14px;color:#94a3b8;margin-bottom:20px;line-height:1.6;">
            Your monitored capabilities show no significant changes this week. Everything is running smoothly.
          </div>
          <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:16px 20px;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:rgba(226,232,240,0.5);margin-bottom:8px;">Quick Stats</div>
            {stats_html}
          </div>
        </td></tr>
        <tr><td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 16px 16px;padding:20px 32px;text-align:center;">
          <div style="font-size:11px;color:rgba(226,232,240,0.3);line-height:1.6;">
            Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a> \u00b7 <a href="https://hephae.co/forge" style="color:#818cf8;text-decoration:none;">Manage Heartbeats</a>
          </div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
