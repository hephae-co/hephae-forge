"""Platform posting clients for social media."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SocialPostResult:
    success: bool
    post_id: str | None = None
    error: str | None = None


class XClient:
    """Post to X (Twitter) via v2 API using OAuth 1.0a."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        access_token: str = "",
        access_secret: str = "",
    ) -> None:
        self.api_key = api_key or os.getenv("X_API_KEY", "")
        self.api_secret = api_secret or os.getenv("X_API_SECRET", "")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN", "")
        self.access_secret = access_secret or os.getenv("X_ACCESS_SECRET", "")

        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            raise ValueError("X API credentials not configured")

    async def post(self, text: str) -> SocialPostResult:
        try:
            from authlib.integrations.httpx_client import AsyncOAuth1Client

            client = AsyncOAuth1Client(
                client_id=self.api_key,
                client_secret=self.api_secret,
                token=self.access_token,
                token_secret=self.access_secret,
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

    def __init__(
        self,
        page_token: str = "",
        page_id: str = "",
    ) -> None:
        self.page_token = page_token or os.getenv("FACEBOOK_PAGE_TOKEN", "")
        self.page_id = page_id or os.getenv("FACEBOOK_PAGE_ID", "")

        if not all([self.page_token, self.page_id]):
            raise ValueError("Facebook credentials not configured")

    async def post(self, text: str) -> SocialPostResult:
        try:
            url = f"https://graph.facebook.com/v19.0/{self.page_id}/feed"
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data={
                    "message": text,
                    "access_token": self.page_token,
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

    def __init__(
        self,
        access_token: str = "",
        business_account_id: str = "",
    ) -> None:
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self.business_account_id = business_account_id or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

        if not all([self.access_token, self.business_account_id]):
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
