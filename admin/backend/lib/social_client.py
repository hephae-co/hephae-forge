"""Platform posting clients for social media."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SocialPostResult:
    success: bool
    post_id: str | None = None
    error: str | None = None


class XClient:
    """Post to X (Twitter) via v2 API using OAuth 1.0a."""

    def __init__(self) -> None:
        if not all([settings.X_API_KEY, settings.X_API_SECRET, settings.X_ACCESS_TOKEN, settings.X_ACCESS_SECRET]):
            raise ValueError("X API credentials not configured")

    async def post(self, text: str) -> SocialPostResult:
        try:
            from authlib.integrations.httpx_client import AsyncOAuth1Client

            client = AsyncOAuth1Client(
                client_id=settings.X_API_KEY,
                client_secret=settings.X_API_SECRET,
                token=settings.X_ACCESS_TOKEN,
                token_secret=settings.X_ACCESS_SECRET,
            )
            resp = await client.post(
                "https://api.x.com/2/tweets",
                json={"text": text},
            )
            await client.aclose()

            if resp.status_code in (200, 201):
                data = resp.json()
                return SocialPostResult(success=True, post_id=data.get("data", {}).get("id"))
            return SocialPostResult(success=False, error=f"X API {resp.status_code}: {resp.text}")
        except ImportError:
            return SocialPostResult(success=False, error="authlib not installed — run: pip install authlib")
        except Exception as e:
            logger.exception("X post failed")
            return SocialPostResult(success=False, error=str(e))


class FacebookClient:
    """Post to Facebook Page via Graph API v19.0."""

    def __init__(self) -> None:
        if not all([settings.FACEBOOK_PAGE_TOKEN, settings.FACEBOOK_PAGE_ID]):
            raise ValueError("Facebook credentials not configured")

    async def post(self, text: str) -> SocialPostResult:
        try:
            url = f"https://graph.facebook.com/v19.0/{settings.FACEBOOK_PAGE_ID}/feed"
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data={
                    "message": text,
                    "access_token": settings.FACEBOOK_PAGE_TOKEN,
                })
            if resp.status_code == 200:
                data = resp.json()
                return SocialPostResult(success=True, post_id=data.get("id"))
            return SocialPostResult(success=False, error=f"Facebook API {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.exception("Facebook post failed")
            return SocialPostResult(success=False, error=str(e))


class InstagramClient:
    """Stub — Instagram requires image URL, not yet implemented."""

    def __init__(self) -> None:
        if not all([settings.INSTAGRAM_ACCESS_TOKEN, settings.INSTAGRAM_BUSINESS_ACCOUNT_ID]):
            raise ValueError("Instagram credentials not configured")

    async def post(self, text: str) -> SocialPostResult:
        return SocialPostResult(
            success=False,
            error="Instagram posting requires an image URL — not yet implemented",
        )


def get_client(platform: str) -> XClient | FacebookClient | InstagramClient:
    """Factory to get the correct platform client."""
    clients = {
        "x": XClient,
        "facebook": FacebookClient,
        "instagram": InstagramClient,
    }
    cls = clients.get(platform)
    if not cls:
        raise ValueError(f"Unsupported platform: {platform}")
    return cls()
