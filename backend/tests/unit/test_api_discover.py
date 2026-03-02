"""
Unit tests for POST /api/discover

All I/O (ADK Runner, GCS, Firestore, BigQuery) is mocked.
Tests cover: input validation, state parsing, field normalization, and the
pipeline-based discovery architecture.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Fresh client with all external deps mocked at the router module level."""
    # We patch at the router-level imports so the route handler sees mocks
    mock_session_svc = MagicMock()
    mock_session_svc.create_session = AsyncMock(return_value=None)
    mock_session_svc.get_session = AsyncMock(return_value=MagicMock(state={}))

    async def _empty_stream(*a, **kw):
        return
        yield

    mock_runner = MagicMock()
    mock_runner.run_async = MagicMock(side_effect=_empty_stream)

    mock_write_agent_result = AsyncMock(return_value=None)

    with (
        patch("backend.routers.discover.InMemorySessionService", return_value=mock_session_svc),
        patch("backend.routers.discover.Runner", return_value=mock_runner),
        patch("backend.routers.discover.upload_report", new_callable=AsyncMock, return_value="https://storage.googleapis.com/test/profile.html"),
        patch("backend.routers.discover.build_profile_report", return_value="<html>profile</html>"),
        patch("backend.routers.discover.generate_slug", side_effect=lambda n: n.lower().replace(" ", "-")),
        patch("backend.routers.discover.write_discovery", new_callable=AsyncMock, return_value=None) as mock_write_discovery,
        patch("backend.routers.discover.write_agent_result", mock_write_agent_result),
    ):
        # Store mocks for state manipulation
        client_ctx = {
            "session_svc": mock_session_svc,
            "write_agent_result": mock_write_agent_result,
            "write_discovery": mock_write_discovery,
        }

        from backend.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._test_ctx = client_ctx  # type: ignore[attr-defined]
            yield ac


def _set_state(client, state: dict):
    """Helper to set the mock session state for the next request."""
    client._test_ctx["session_svc"].get_session.return_value = MagicMock(state=state)


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
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Social links parsing
# ---------------------------------------------------------------------------

class TestSocialLinksParsing:
    @pytest.mark.asyncio
    async def test_parses_social_from_json_string(self, client):
        _set_state(client, {
            "socialData": json.dumps({"instagram": "https://instagram.com/bosphorus"}),
            "contactData": json.dumps({"phone": "+1 (201) 555-0100", "hours": "Mon-Sun 11am-10pm"}),
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["instagram"] == "https://instagram.com/bosphorus"
        assert data["phone"] == "+1 (201) 555-0100"
        assert data["hours"] == "Mon-Sun 11am-10pm"

    @pytest.mark.asyncio
    async def test_accepts_social_as_dict(self, client):
        _set_state(client, {
            "socialData": {"facebook": "https://facebook.com/bosphorus"},
            "contactData": {"email": "info@bosphorus.com"},
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["facebook"] == "https://facebook.com/bosphorus"
        assert data["email"] == "info@bosphorus.com"

    @pytest.mark.asyncio
    async def test_no_crash_on_malformed_social_json(self, client):
        _set_state(client, {"socialData": "not-valid-json"})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, client):
        raw = {"phone": "+1 (201) 555-0199"}
        _set_state(client, {"contactData": f"```json\n{json.dumps(raw)}\n```"})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["phone"] == "+1 (201) 555-0199"


# ---------------------------------------------------------------------------
# Competitors parsing
# ---------------------------------------------------------------------------

class TestCompetitorsParsing:
    @pytest.mark.asyncio
    async def test_parses_competitors_from_json_string(self, client):
        rivals = [
            {"name": "Turkish Kitchen", "url": "https://turkishkitchen.com", "reason": "Same cuisine"},
            {"name": "Istanbul Grill", "url": "https://istanbulgrill.com", "reason": "Same neighborhood"},
            {"name": "Olive Tree", "url": "https://olivetree.com", "reason": "Mediterranean overlap"},
        ]
        _set_state(client, {"competitorData": json.dumps(rivals)})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert len(data["competitors"]) == 3
        assert data["competitors"][0]["name"] == "Turkish Kitchen"

    @pytest.mark.asyncio
    async def test_accepts_competitors_as_array(self, client):
        rivals = [{"name": "Rival A", "url": "https://a.com", "reason": "Close by"}]
        _set_state(client, {"competitorData": rivals})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert isinstance(data["competitors"], list)
        assert data["competitors"][0]["url"] == "https://a.com"

    @pytest.mark.asyncio
    async def test_no_crash_on_malformed_competitors(self, client):
        _set_state(client, {"competitorData": "broken json ["})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_competitors_none_when_missing(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("competitors") is None


# ---------------------------------------------------------------------------
# Theme data
# ---------------------------------------------------------------------------

class TestThemeData:
    @pytest.mark.asyncio
    async def test_uses_theme_fields(self, client):
        _set_state(client, {
            "themeData": json.dumps({
                "logoUrl": "https://bosphorus.com/logo.png",
                "favicon": "https://bosphorus.com/favicon.ico",
                "primaryColor": "#c0392b",
                "secondaryColor": "#ffffff",
                "persona": "Classic Establishment",
            }),
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["logoUrl"] == "https://bosphorus.com/logo.png"
        assert data["favicon"] == "https://bosphorus.com/favicon.ico"
        assert data["primaryColor"] == "#c0392b"
        assert data["persona"] == "Classic Establishment"

    @pytest.mark.asyncio
    async def test_defaults_when_theme_missing(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data.get("primaryColor") is None
        assert data.get("persona") is None


# ---------------------------------------------------------------------------
# Delivery platforms
# ---------------------------------------------------------------------------

class TestDeliveryPlatforms:
    @pytest.mark.asyncio
    async def test_delivery_from_menu_data(self, client):
        _set_state(client, {
            "menuData": json.dumps({
                "menuUrl": None,
                "grubhub": "https://www.grubhub.com/restaurant/bosphorus-123",
                "doordash": "https://www.doordash.com/store/bosphorus-456",
                "ubereats": "https://www.ubereats.com/store/bosphorus-789",
            }),
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["grubhub"] == "https://www.grubhub.com/restaurant/bosphorus-123"
        assert data["socialLinks"]["doordash"] == "https://www.doordash.com/store/bosphorus-456"
        assert data["socialLinks"]["ubereats"] == "https://www.ubereats.com/store/bosphorus-789"

    @pytest.mark.asyncio
    async def test_delivery_fallback_to_social(self, client):
        _set_state(client, {
            "menuData": {"menuUrl": None},
            "socialData": json.dumps({
                "grubhub": "https://www.grubhub.com/restaurant/llm-found",
                "doordash": "https://www.doordash.com/store/llm-found",
            }),
        })
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialLinks"]["grubhub"] == "https://www.grubhub.com/restaurant/llm-found"
        assert data["socialLinks"]["doordash"] == "https://www.doordash.com/store/llm-found"


# ---------------------------------------------------------------------------
# Menu URL
# ---------------------------------------------------------------------------

class TestMenuUrl:
    @pytest.mark.asyncio
    async def test_includes_menu_url(self, client):
        _set_state(client, {"menuData": {"menuUrl": "https://bosphorusnutley.com/menu"}})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["menuUrl"] == "https://bosphorusnutley.com/menu"

    @pytest.mark.asyncio
    async def test_excludes_null_menu_url(self, client):
        _set_state(client, {"menuData": {"menuUrl": None}})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("menuUrl") is None

    @pytest.mark.asyncio
    async def test_200_when_menu_data_missing(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

class TestResponseShape:
    @pytest.mark.asyncio
    async def test_returns_identity_fields(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["name"] == "Bosphorus Restaurant"
        assert data["officialUrl"] == "https://bosphorusnutley.com"
        assert data["address"] == "10 Main St, Nutley, NJ 07110"

    @pytest.mark.asyncio
    async def test_includes_report_url(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["reportUrl"] == "https://storage.googleapis.com/test/profile.html"


# ---------------------------------------------------------------------------
# Social Profile Metrics parsing
# ---------------------------------------------------------------------------

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


class TestSocialProfileMetricsParsing:
    @pytest.mark.asyncio
    async def test_parses_metrics_from_json_string(self, client):
        _set_state(client, {"socialProfileMetrics": json.dumps(SAMPLE_METRICS)})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialProfileMetrics"]["instagram"]["followerCount"] == 2450
        assert data["socialProfileMetrics"]["summary"]["totalFollowers"] == 3650

    @pytest.mark.asyncio
    async def test_parses_metrics_from_dict(self, client):
        _set_state(client, {"socialProfileMetrics": SAMPLE_METRICS})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialProfileMetrics"]["yelp"]["rating"] == 4.5

    @pytest.mark.asyncio
    async def test_strips_markdown_fences_from_metrics(self, client):
        raw = f"```json\n{json.dumps(SAMPLE_METRICS)}\n```"
        _set_state(client, {"socialProfileMetrics": raw})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data["socialProfileMetrics"]["summary"]["overallPresenceScore"] == 62

    @pytest.mark.asyncio
    async def test_null_when_metrics_missing(self, client):
        _set_state(client, {})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        data = res.json()
        assert data.get("socialProfileMetrics") is None

    @pytest.mark.asyncio
    async def test_null_when_metrics_malformed(self, client):
        _set_state(client, {"socialProfileMetrics": "not valid json {"})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        data = res.json()
        assert data.get("socialProfileMetrics") is None

    @pytest.mark.asyncio
    async def test_metrics_nested_structure_preserved(self, client):
        _set_state(client, {"socialProfileMetrics": SAMPLE_METRICS})
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
        _set_state(client, {"socialProfileMetrics": SAMPLE_METRICS})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        assert res.status_code == 200
        # Give fire-and-forget task a chance to be created
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
        _set_state(client, {})
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
        _set_state(client, {"socialProfileMetrics": metrics})
        res = await client.post("/api/discover", json={"identity": BASE_IDENTITY})
        import asyncio
        await asyncio.sleep(0.05)
        assert mock_war.call_args.kwargs["score"] == 85
