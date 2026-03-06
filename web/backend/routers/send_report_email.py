"""POST /api/send-report-email — Send report email via Resend."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.lib.email import send_report_email

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_REPORT_TYPES = {"profile", "margin", "traffic", "seo", "competitive"}


@router.post("/send-report-email")
async def send_email_route(request: Request):
    try:
        body = await request.json()
        email = body.get("email", "")
        report_url = body.get("reportUrl", "")
        report_type = body.get("reportType", "")
        business_name = body.get("businessName", "")
        summary = body.get("summary", "Your report is ready. Click below to view the full analysis.")

        if not email or "@" not in email:
            return JSONResponse({"error": "Valid email is required."}, status_code=400)
        if not report_url:
            return JSONResponse({"error": "reportUrl is required."}, status_code=400)
        if report_type not in VALID_REPORT_TYPES:
            return JSONResponse(
                {"error": f"reportType must be one of: {', '.join(VALID_REPORT_TYPES)}"},
                status_code=400,
            )
        if not business_name:
            return JSONResponse({"error": "businessName is required."}, status_code=400)

        result = await send_report_email(
            to=email,
            business_name=business_name,
            report_type=report_type,
            report_url=report_url,
            summary=summary,
        )

        if not result.get("success"):
            return JSONResponse(
                {"error": result.get("error", "Failed to send email.")},
                status_code=502,
            )

        return JSONResponse({"success": True, "emailId": result.get("id")})

    except Exception as e:
        logger.error(f"[API/SendReportEmail] Failed: {e}")
        return JSONResponse({"error": "Internal Server Error"}, status_code=500)
