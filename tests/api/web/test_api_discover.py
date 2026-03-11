"""
Unit tests for POST /api/discover

Now that discover.py delegates to run_discovery(), tests mock the runner
and verify: input validation, post-processing (menu capture, GCS, Firestore),
and response shape.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BASE_IDENTITY = {
    "name": "Bosphorus Restaurant",
    "address": "10 Main St, Nutley, NJ 07110",
    "officialUrl": "https://bosphorusnutley.com",
    "coordinates": {"lat": 40.8218, "lng": -74.1573},
}

SAMPLE_METRICS = {
    "instagram": {
        "url": "https://instagram.com/bosphorus_nj",
        "username": "bosphorus_nj",
        "followerCount": 2450,
        "postCount": 187,
        "bio": "Authentic Turkish cuisine",
        "isVerified": False,
        "lastPostRecency": "3 days ago",
        "engagementIndicator": "moderate",
        "error": None,
    },
    "facebook": {
        "url": "https://facebook.com/BosphorusNutley",
        "pageName": "Bosphorus Restaurant",
        "followerCount": 1200,
        "likeCount": 1150,
        "rating": 4.6,
        "reviewCount": 89,
        "lastPostRecency": "1 week ago",
        "engagementIndicator": "low",
        "error": None,
    },
    "twitter": None,
    "tiktok": None,
    "yelp": {
        "url": "https://yelp.com/biz/bosphorus-nutley",
        "rating": 4.5,
        "reviewCount": 234,
        "priceRange": "$$",
        "categories": ["Turkish", "Mediterranean"],
        "claimedByOwner": True,
        "error": None,
    },
    "summary": {
        "totalFollowers": 3650,
        "strongestPlatform": "instagram",
        "weakestPlatform": "facebook",
        "overallPresenceScore": 62,
        "postingFrequency": "weekly",
        "recommendation": "Instagram is strongest. Consider increasing posting frequency.",
    },
}

SAMPLE_NEWS = [
    {"title": "Local Gem Review", "url": "https://nj.com/bosphorus", "source": "NJ.com", "date": "2025-12-01", "snippet": "Great food"},
    {"title": "Best Turkish Food", "url": "https://eater.com/bosphorus", "source": "Eater", "date": "2025-11-15", "snippet": "Top pick"},
]


def _base_enriched(**overrides):
    """Build a minimal enriched profile dict, as returned by run_discovery()."""
    base = {
        **BASE_IDENTITY,
        "menuUrl": None,
        "socialLinks": {
            "instagram": None, "facebook": None, "twitter": None,
            "yelp": None, "tiktok": None,
            "grubhub": None, "doordash": None, "ubereats": None,
            "seamless": None, "toasttab": None,
        },
        "phone": None,
        "email": None,
        "emailStatus": None,
        "contactFormUrl": None,
        "contactFormStatus": None,
        "hours": None,
        "googleMapsUrl": None,
        "competitors": None,
        "news": None,
        "favicon": None,
        "logoUrl": None,
        "primaryColor": None,
        "secondaryColor": None,
        "persona": None,
        "socialProfileMetrics": None,
        "aiOverview": None,
        "challenges": None,
        "entityMatch": None,
        "validationReport": None,
        "localContext": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Client with run_discovery and all post-processing deps mocked."""
    mock_run_discovery = AsyncMock(return_value=_base_enriched())
    mock_write_agent_result = AsyncMock(return_value=None)
    mock_write_discovery = AsyncMock(return_value=None)

    with (
        patch("backend.routers.web.discover.run_discovery", mock_run_discovery),
        patch("backend.routers.web.discover.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/profile.html"),
        patch("backend.routers.web.discover.build_profile_report", return_value="<html>profile</html>"),
        patch("backend.routers.web.discover.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.web.discover.write_discovery", mock_write_discovery),
        patch("backend.routers.web.discover.write_agent_result", mock_write_agent_result),
        patch("backend.routers.web.discover._capture_menu", new_callable=AsyncMock, return_value=("", "")),
    ):
        client_ctx = {
            "run_discovery": mock_run_discovery,
            "write_agent_result": mock_write_agent_result,
            "write_discovery": mock_write_discovery,
        }

        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._test_ctx = client_ctx  # type: ignore[attr-defined]
            yield ac


def _set_enriched(client, **overrides):
    """Configure run_discovery to return an enriched profile with overrides."""
    client._test_ctx["run_discovery"].return_value = _base_enriched(**overrides)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    @pytest.mark.asyncio
    async def test_400_when_body_missing_identity(self, client):
        res = await client.post("/api/discover", json={})
        assert res.status_code == 400
        assert "missing" in res.json()["error"].lower() or "identity" in res.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_400_when_identity_has_no_url(self, client):
        res = await client.post("/api/discover", json={"identity": {"name": "Test", "address": "123 Main"}})
        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_200_when_all_required_fields(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Social links
# ---------------------------------------------------------------------------

class TestSocialLinksParsing:
    @pytest.mark.asyncio
    async def test_parses_social_links(self, client):
        _set_enriched(client,
            socialLinks={
                **_base_enriched()["socialLinks"],
                "instagram": "https://instagram.com/bosphorus",
            },
            phone="+1 (201) 555-0100",
            hours="Mon-Sun 11am-10pm",
        )
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["instagram"] == "https://instagram.com/bosphorus"
        assert data["phone"] == "+1 (201) 555-0100"
        assert data["hours"] == "Mon-Sun 11am-10pm"

    @pytest.mark.asyncio
    async def test_null_social_links(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["instagram"] is None


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

class TestCompetitorsParsing:
    @pytest.mark.asyncio
    async def test_returns_competitors(self, client):
        rivals = [
            {"name": "Turkish Kitchen", "url": "https://turkishkitchen.com", "reason": "Same cuisine"},
            {"name": "Istanbul Grill", "url": "https://istanbulgrill.com", "reason": "Same neighborhood"},
            {"name": "Olive Tree", "url": "https://olivetree.com", "reason": "Mediterranean overlap"},
        ]
        _set_enriched(client, competitors=rivals)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert len(data["competitors"]) == 3
        assert data["competitors"][0]["name"] == "Turkish Kitchen"

    @pytest.mark.asyncio
    async def test_competitors_none_when_missing(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("competitors") is None


# ---------------------------------------------------------------------------
# Theme data
# ---------------------------------------------------------------------------

class TestThemeData:
    @pytest.mark.asyncio
    async def test_uses_theme_fields(self, client):
        _set_enriched(client,
            logoUrl="https://bosphorus.com/logo.png",
            favicon="https://bosphorus.com/favicon.ico",
            primaryColor="#c0392b",
            secondaryColor="#ffffff",
            persona="Classic Establishment",
        )
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["logoUrl"] == "https://bosphorus.com/logo.png"
        assert data["favicon"] == "https://bosphorus.com/favicon.ico"
        assert data["primaryColor"] == "#c0392b"
        assert data["persona"] == "Classic Establishment"

    @pytest.mark.asyncio
    async def test_defaults_when_theme_missing(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("primaryColor") is None
        assert data.get("persona") is None


# ---------------------------------------------------------------------------
# Delivery platforms
# ---------------------------------------------------------------------------

class TestDeliveryPlatforms:
    @pytest.mark.asyncio
    async def test_delivery_links(self, client):
        _set_enriched(client, socialLinks={
            **_base_enriched()["socialLinks"],
            "grubhub": "https://www.grubhub.com/restaurant/bosphorus-123",
            "doordash": "https://www.doordash.com/store/bosphorus-456",
            "ubereats": "https://www.ubereats.com/store/bosphorus-789",
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["grubhub"] == "https://www.grubhub.com/restaurant/bosphorus-123"
        assert data["socialLinks"]["doordash"] == "https://www.doordash.com/store/bosphorus-456"
        assert data["socialLinks"]["ubereats"] == "https://www.ubereats.com/store/bosphorus-789"


# ---------------------------------------------------------------------------
# Menu URL
# ---------------------------------------------------------------------------

class TestMenuUrl:
    @pytest.mark.asyncio
    async def test_includes_menu_url(self, client):
        _set_enriched(client, menuUrl="https://bosphorusnutley.com/menu")
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["menuUrl"] == "https://bosphorusnutley.com/menu"

    @pytest.mark.asyncio
    async def test_excludes_null_menu_url(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("menuUrl") is None


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

class TestResponseShape:
    @pytest.mark.asyncio
    async def test_returns_identity_fields(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["name"] == "Bosphorus Restaurant"
        assert data["officialUrl"] == "https://bosphorusnutley.com"
        assert data["address"] == "10 Main St, Nutley, NJ 07110"

    @pytest.mark.asyncio
    async def test_includes_report_url(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["reportUrl"] == "https://storage.googleapis.com/test/profile.html"


# ---------------------------------------------------------------------------
# Social Profile Metrics
# ---------------------------------------------------------------------------

class TestSocialProfileMetricsParsing:
    @pytest.mark.asyncio
    async def test_metrics_present(self, client):
        _set_enriched(client, socialProfileMetrics=SAMPLE_METRICS)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialProfileMetrics"]["instagram"]["followerCount"] == 2450
        assert data["socialProfileMetrics"]["summary"]["totalFollowers"] == 3650

    @pytest.mark.asyncio
    async def test_null_when_metrics_missing(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("socialProfileMetrics") is None

    @pytest.mark.asyncio
    async def test_metrics_nested_structure_preserved(self, client):
        _set_enriched(client, socialProfileMetrics=SAMPLE_METRICS)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        metrics = data["socialProfileMetrics"]
        assert metrics["facebook"]["rating"] == 4.6
        assert metrics["facebook"]["reviewCount"] == 89
        assert metrics["yelp"]["categories"] == ["Turkish", "Mediterranean"]
        assert metrics["twitter"] is None
        assert metrics["tiktok"] is None


class TestSocialProfilerWriteAgentResult:
    @pytest.mark.asyncio
    async def test_write_called_when_metrics_present(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        _set_enriched(client, socialProfileMetrics=SAMPLE_METRICS)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        mock_war.assert_called_once()
        call_kwargs = mock_war.call_args.kwargs
        assert call_kwargs["agent_name"] == "social_profiler"
        assert call_kwargs["raw_data"] == SAMPLE_METRICS
        assert call_kwargs["score"] == 62

    @pytest.mark.asyncio
    async def test_write_not_called_when_metrics_empty(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        mock_war.assert_not_called()

    @pytest.mark.asyncio
    async def test_score_from_summary(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        metrics = {**SAMPLE_METRICS, "summary": {**SAMPLE_METRICS["summary"], "overallPresenceScore": 85}}
        _set_enriched(client, socialProfileMetrics=metrics)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        import asyncio
        await asyncio.sleep(0.05)
        assert mock_war.call_args.kwargs["score"] == 85


# ---------------------------------------------------------------------------
# News data
# ---------------------------------------------------------------------------

class TestNewsDataParsing:
    @pytest.mark.asyncio
    async def test_returns_news(self, client):
        _set_enriched(client, news=SAMPLE_NEWS)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["news"] is not None
        assert len(data["news"]) == 2
        assert data["news"][0]["title"] == "Local Gem Review"

    @pytest.mark.asyncio
    async def test_news_none_when_missing(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("news") is None


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

SAMPLE_VALIDATION_REPORT = {
    "totalUrlsChecked": 12,
    "valid": 8,
    "invalid": 2,
    "unverifiable": 1,
    "corrected": 1,
    "flags": ["socialData.tiktok: invalid, no replacement found"],
}


class TestValidationReport:
    @pytest.mark.asyncio
    async def test_validation_report_present(self, client):
        _set_enriched(client, validationReport=SAMPLE_VALIDATION_REPORT)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["validationReport"] is not None
        assert data["validationReport"]["totalUrlsChecked"] == 12
        assert data["validationReport"]["valid"] == 8

    @pytest.mark.asyncio
    async def test_no_validation_report_when_missing(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("validationReport") is None


# ---------------------------------------------------------------------------
# Entity match / discovery abort
# ---------------------------------------------------------------------------

class TestDiscoveryAbort:
    @pytest.mark.asyncio
    async def test_aborted_discovery_returns_immediately(self, client):
        _set_enriched(client,
            discoveryAborted=True,
            discoveryAbortReason="Site does not match target business: MISMATCH",
            entityMatch={"status": "MISMATCH", "reason": "Site is for a different business"},
        )
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["discoveryAborted"] is True
        assert "MISMATCH" in data["discoveryAbortReason"]

    @pytest.mark.asyncio
    async def test_normal_discovery_not_aborted(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("discoveryAborted") is None


# ---------------------------------------------------------------------------
# Agent result writes
# ---------------------------------------------------------------------------

class TestAgentResultWrites:
    @pytest.mark.asyncio
    async def test_reviewer_write_called(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        _set_enriched(client, validationReport=SAMPLE_VALIDATION_REPORT)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        calls = mock_war.call_args_list
        reviewer_calls = [c for c in calls if c.kwargs.get("agent_name") == "discovery_reviewer"]
        assert len(reviewer_calls) == 1
        assert "12" in reviewer_calls[0].kwargs["summary"]

    @pytest.mark.asyncio
    async def test_news_write_called(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        _set_enriched(client, news=SAMPLE_NEWS)
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        calls = mock_war.call_args_list
        news_calls = [c for c in calls if c.kwargs.get("agent_name") == "news_discovery"]
        assert len(news_calls) == 1
        assert "2 news" in news_calls[0].kwargs["summary"]

    @pytest.mark.asyncio
    async def test_no_reviewer_write_when_no_validation_report(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        calls = mock_war.call_args_list
        reviewer_calls = [c for c in calls if c.kwargs.get("agent_name") == "discovery_reviewer"]
        assert len(reviewer_calls) == 0

    @pytest.mark.asyncio
    async def test_overview_write_called(self, client):
        mock_war = client._test_ctx["write_agent_result"]
        mock_war.reset_mock()
        _set_enriched(client, aiOverview={"summary": "Great Turkish restaurant"})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        import asyncio
        await asyncio.sleep(0.05)
        calls = mock_war.call_args_list
        overview_calls = [c for c in calls if c.kwargs.get("agent_name") == "business_overview"]
        assert len(overview_calls) == 1


# ---------------------------------------------------------------------------
# Local context (P0a)
# ---------------------------------------------------------------------------

class TestLocalContext:
    @pytest.mark.asyncio
    async def test_local_context_present(self, client):
        _set_enriched(client, localContext={
            "areaResearch": {"summary": "Growing market"},
            "zipcodeResearch": {"report": "Active dining area"},
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["localContext"] is not None
        assert data["localContext"]["areaResearch"]["summary"] == "Growing market"

    @pytest.mark.asyncio
    async def test_local_context_null_when_unavailable(self, client):
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("localContext") is None


# ---------------------------------------------------------------------------
# Challenges (P0.2)
# ---------------------------------------------------------------------------

class TestChallenges:
    @pytest.mark.asyncio
    async def test_challenges_present(self, client):
        _set_enriched(client, challenges={
            "reputationRisks": ["Low Yelp rating"],
            "healthInspections": [],
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["challenges"] is not None
        assert "Low Yelp rating" in data["challenges"]["reputationRisks"]
