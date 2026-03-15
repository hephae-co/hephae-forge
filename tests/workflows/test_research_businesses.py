"""Unit tests for the research businesses router endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from hephae_api.types import DiscoveredBusiness

_PAGINATED_RESPONSE = {
    "businesses": [{"name": "Test Biz", "zipCode": "07110", "id": "test-biz"}],
    "total": 1,
    "page": 1,
    "pages": 1,
    "pageSize": 25,
}


@pytest.fixture
def client():
    """Create a test client with mocked Firebase and optional deps."""
    import sys
    # Mock optional deps that may not be installed in local dev venv
    _mocks: dict = {}
    for mod_name in ("resend", "crawl4ai", "playwright", "playwright.async_api"):
        if mod_name not in sys.modules:
            _mocks[mod_name] = MagicMock()
            sys.modules[mod_name] = _mocks[mod_name]

    with patch("hephae_common.firebase.get_db"):
        from hephae_api.main import app
        from hephae_api.lib.auth import verify_admin_request
        app.dependency_overrides[verify_admin_request] = lambda: {"uid": "test-admin", "email": "admin@test.com"}
        yield TestClient(app)
        app.dependency_overrides.pop(verify_admin_request, None)


class TestDiscoverBusinesses:
    """POST /api/research/businesses"""

    def test_discover_with_json_body(self, client):
        """Verify endpoint accepts zipCode in JSON body (not query param)."""
        mock_businesses = [
            DiscoveredBusiness(name="Pizza Palace", address="123 Main St", docId="pizza-palace"),
            DiscoveredBusiness(name="Burger Barn", address="456 Oak Ave", docId="burger-barn"),
        ]
        with patch(
            "hephae_api.routers.admin.research_businesses.scan_zipcode",
            new_callable=AsyncMock,
            return_value=mock_businesses,
        ):
            response = client.post("/api/research/businesses", json={"zipCode": "07110"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["businesses"]) == 2
        assert data["businesses"][0]["name"] == "Pizza Palace"

    def test_discover_returns_count_field(self, client):
        with patch(
            "hephae_api.routers.admin.research_businesses.scan_zipcode",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = client.post("/api/research/businesses", json={"zipCode": "99999"})

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0

    def test_discover_missing_zipcode_returns_422(self, client):
        assert client.post("/api/research/businesses", json={}).status_code == 422

    def test_discover_no_body_returns_422(self, client):
        assert client.post("/api/research/businesses").status_code == 422


class TestGetBusinesses:
    """GET /api/research/businesses — now returns paginated response."""

    def test_get_businesses_with_zipcode(self, client):
        with patch(
            "hephae_api.routers.admin.research_businesses.get_businesses_paginated",
            new_callable=AsyncMock,
            return_value=_PAGINATED_RESPONSE,
        ):
            response = client.get("/api/research/businesses?zipCode=07110")

        assert response.status_code == 200
        data = response.json()
        assert "businesses" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert data["total"] == 1
        assert data["businesses"][0]["name"] == "Test Biz"

    def test_get_businesses_pagination_params_forwarded(self, client):
        """page and pageSize are forwarded to the DB function."""
        mock_fn = AsyncMock(return_value={**_PAGINATED_RESPONSE, "page": 2, "total": 50})
        with patch("hephae_api.routers.admin.research_businesses.get_businesses_paginated", mock_fn):
            response = client.get("/api/research/businesses?zipCode=07110&page=2&pageSize=10")

        assert response.status_code == 200
        mock_fn.assert_called_once_with(
            zip_code="07110", page=2, page_size=10,
            category=None, status=None, has_email=None, name=None,
        )

    def test_get_businesses_filter_params_forwarded(self, client):
        """category, status, hasEmail filters are forwarded."""
        mock_fn = AsyncMock(return_value=_PAGINATED_RESPONSE)
        with patch("hephae_api.routers.admin.research_businesses.get_businesses_paginated", mock_fn):
            response = client.get(
                "/api/research/businesses?zipCode=07110&category=restaurant&status=analyzed&hasEmail=true"
            )

        assert response.status_code == 200
        mock_fn.assert_called_once_with(
            zip_code="07110", page=1, page_size=25,
            category="restaurant", status="analyzed", has_email=True, name=None,
        )

    def test_get_businesses_no_zipcode_returns_200(self, client):
        """zipCode is now optional — returns 200 with empty results."""
        mock_fn = AsyncMock(return_value=_PAGINATED_RESPONSE)
        with patch("hephae_api.routers.admin.research_businesses.get_businesses_paginated", mock_fn):
            assert client.get("/api/research/businesses").status_code == 200

    def test_page_must_be_positive(self, client):
        with patch(
            "hephae_api.routers.admin.research_businesses.get_businesses_paginated",
            new_callable=AsyncMock, return_value=_PAGINATED_RESPONSE,
        ):
            assert client.get("/api/research/businesses?zipCode=07110&page=0").status_code == 422

    def test_page_size_max_100(self, client):
        with patch(
            "hephae_api.routers.admin.research_businesses.get_businesses_paginated",
            new_callable=AsyncMock, return_value=_PAGINATED_RESPONSE,
        ):
            assert client.get("/api/research/businesses?zipCode=07110&pageSize=200").status_code == 422


class TestDeleteBusiness:
    """DELETE /api/research/businesses"""

    def test_delete_business(self, client):
        with patch(
            "hephae_api.routers.admin.research_businesses.delete_business",
            new_callable=AsyncMock,
        ):
            response = client.delete("/api/research/businesses?id=test-biz")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_missing_id_returns_422(self, client):
        assert client.delete("/api/research/businesses").status_code == 422


class TestRunReviewerAction:
    """POST /api/research/actions action=run-reviewer"""

    def test_run_reviewer_success(self, client):
        """run-reviewer action fetches biz, runs reviewer, saves result."""
        mock_biz = {
            "id": "test-biz",
            "name": "Test Biz",
            "identity": {"name": "Test Biz", "email": "test@example.com"},
            "latestOutputs": {"seo_auditor": {"score": 30, "summary": "Poor SEO"}},
        }
        mock_result = {
            "outreach_score": 8,
            "best_channel": "email",
            "primary_reason": "Poor SEO = clear value we can deliver",
            "strengths": ["Email available", "Low SEO score"],
            "concerns": [],
        }
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.update = MagicMock()

        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=mock_biz), \
             patch("hephae_agents.reviewer.runner.run_reviewer",
                   new_callable=AsyncMock, return_value=mock_result), \
             patch("hephae_common.firebase.get_db", return_value=mock_db), \
             patch("asyncio.to_thread", new_callable=AsyncMock):
            response = client.post(
                "/api/research/actions",
                json={"action": "run-reviewer", "businessId": "test-biz"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["outreach_score"] == 8

    def test_run_reviewer_business_not_found(self, client):
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=None):
            response = client.post(
                "/api/research/actions",
                json={"action": "run-reviewer", "businessId": "nonexistent"},
            )
        assert response.status_code == 404

    def test_run_reviewer_agent_returns_none(self, client):
        """When reviewer returns None, endpoint returns success=False."""
        mock_biz = {"id": "biz", "name": "Biz", "identity": {}, "latestOutputs": {}}
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=mock_biz), \
             patch("hephae_agents.reviewer.runner.run_reviewer",
                   new_callable=AsyncMock, return_value=None):
            response = client.post(
                "/api/research/actions",
                json={"action": "run-reviewer", "businessId": "biz"},
            )
        assert response.status_code == 200
        assert response.json()["success"] is False


class TestGenerateOutreachContent:
    """POST /api/research/actions with action='generate-outreach-content'"""

    def test_generate_outreach_content_success(self, client):
        """Generate outreach content for all 5 channels."""
        mock_biz = {
            "id": "biz1",
            "name": "Test Cafe",
            "identity": {"name": "Test Cafe", "docId": "biz1"},
            "latestOutputs": {"margin_surgeon": {"score": 60, "summary": "Test"}},
            "socialLinks": {"instagram": "@testcafe", "twitter": "@testcafe_x"},
        }
        mock_content = {
            "instagram": {"caption": "Instagram caption"},
            "facebook": {"post": "Facebook post"},
            "twitter": {"tweet": "Tweet text"},
            "email": {"subject": "Email subject", "body": "Email body"},
            "contactForm": {"message": "Contact form message"},
        }
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=mock_biz), \
             patch("hephae_agents.social.post_generator.runner.run_social_post_generation",
                   new_callable=AsyncMock, return_value=mock_content), \
             patch("hephae_api.routers.admin.research_businesses.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.collection.return_value.document.return_value.update = MagicMock()

            response = client.post(
                "/api/research/actions",
                json={"action": "generate-outreach-content", "businessId": "biz1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "content" in data
        assert data["content"]["instagram"]["caption"] == "Instagram caption"
        assert data["content"]["email"]["subject"] == "Email subject"
        assert data["content"]["contactForm"]["message"] == "Contact form message"

    def test_generate_outreach_content_business_not_found(self, client):
        """Should return 404 if business doesn't exist."""
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=None):
            response = client.post(
                "/api/research/actions",
                json={"action": "generate-outreach-content", "businessId": "nonexistent"},
            )
        assert response.status_code == 404

    def test_generate_outreach_uses_social_links(self, client):
        """Social links from business should be passed to runner."""
        mock_biz = {
            "id": "biz1",
            "name": "Cafe",
            "identity": {"name": "Cafe"},
            "latestOutputs": {},
            "socialLinks": {"instagram": "@cafebiz", "facebook": "CafeBizPage", "twitter": "@cafe_x"},
        }
        mock_content = {
            "instagram": {"caption": "ig"},
            "facebook": {"post": "fb"},
            "twitter": {"tweet": "tw"},
            "email": {"subject": "subj", "body": "body"},
            "contactForm": {"message": "msg"},
        }
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=mock_biz), \
             patch("hephae_agents.social.post_generator.runner.run_social_post_generation",
                   new_callable=AsyncMock, return_value=mock_content) as mock_runner, \
             patch("hephae_api.routers.admin.research_businesses.get_db"):
            response = client.post(
                "/api/research/actions",
                json={"action": "generate-outreach-content", "businessId": "biz1"},
            )

        assert response.status_code == 200
        # Verify runner was called with correct social_handles
        call_kwargs = mock_runner.call_args.kwargs
        assert call_kwargs["social_handles"]["instagram"] == "@cafebiz"
        assert call_kwargs["social_handles"]["facebook"] == "CafeBizPage"
        assert call_kwargs["social_handles"]["twitter"] == "@cafe_x"

    def test_generate_outreach_uses_latest_outputs(self, client):
        """latest_outputs from business should be passed to runner."""
        latest_outputs = {
            "margin_surgeon": {"score": 65, "summary": "Margin data"},
            "seo_auditor": {"score": 45, "summary": "SEO data"},
        }
        mock_biz = {
            "id": "biz1",
            "name": "Biz",
            "identity": {"name": "Biz"},
            "latestOutputs": latest_outputs,
            "socialLinks": {},
        }
        mock_content = {
            "instagram": {"caption": "ig"},
            "facebook": {"post": "fb"},
            "twitter": {"tweet": "tw"},
            "email": {"subject": "subj", "body": "body"},
            "contactForm": {"message": "msg"},
        }
        with patch("hephae_api.routers.admin.research_businesses.get_business",
                   new_callable=AsyncMock, return_value=mock_biz), \
             patch("hephae_agents.social.post_generator.runner.run_social_post_generation",
                   new_callable=AsyncMock, return_value=mock_content) as mock_runner, \
             patch("hephae_api.routers.admin.research_businesses.get_db"):
            response = client.post(
                "/api/research/actions",
                json={"action": "generate-outreach-content", "businessId": "biz1"},
            )

        assert response.status_code == 200
        # Verify runner was called with latest_outputs
        call_kwargs = mock_runner.call_args.kwargs
        assert call_kwargs["latest_outputs"] == latest_outputs


class TestSaveOutreachDraft:
    """POST /api/research/actions with action='save-outreach-draft'"""

    def test_save_draft_twitter(self, client):
        """Save draft for twitter channel."""
        with patch("hephae_api.routers.admin.research_businesses.get_db") as mock_get_db, \
             patch("hephae_db.firestore.fixtures.save_fixture_from_business",
                   new_callable=AsyncMock) as mock_save_fixture:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.collection.return_value.document.return_value.update = MagicMock()

            response = client.post(
                "/api/research/actions",
                json={
                    "action": "save-outreach-draft",
                    "businessId": "biz1",
                    "channel": "twitter",
                    "editedContent": "Updated tweet text",
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        # Verify Firestore update was called with correct fields
        update_call = mock_db.collection.return_value.document.return_value.update
        assert update_call.called
        update_data = update_call.call_args[0][0]
        assert "outreachContent.twitter.edited" in update_data
        assert update_data["outreachContent.twitter.edited"] == "Updated tweet text"
        # Verify fixture was saved
        mock_save_fixture.assert_called_once()
        fixture_call_kwargs = mock_save_fixture.call_args.kwargs
        assert fixture_call_kwargs["agent_key"] == "outreach_twitter"
        assert fixture_call_kwargs["fixture_type"] == "outreach_draft"

    def test_save_draft_email_with_subject(self, client):
        """Save draft for email with subject line."""
        with patch("hephae_api.routers.admin.research_businesses.get_db") as mock_get_db, \
             patch("hephae_db.firestore.fixtures.save_fixture_from_business",
                   new_callable=AsyncMock):
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.collection.return_value.document.return_value.update = MagicMock()

            response = client.post(
                "/api/research/actions",
                json={
                    "action": "save-outreach-draft",
                    "businessId": "biz1",
                    "channel": "email",
                    "editedContent": "Updated email body",
                    "emailSubject": "Updated subject line",
                },
            )

        assert response.status_code == 200
        assert response.json()["success"] is True
        # Verify both body and subject were saved
        update_call = mock_db.collection.return_value.document.return_value.update
        update_data = update_call.call_args[0][0]
        assert update_data["outreachContent.email.edited"] == "Updated email body"
        assert update_data["outreachContent.email.editedSubject"] == "Updated subject line"

    def test_save_draft_instagram(self, client):
        """Save draft for instagram channel."""
        with patch("hephae_api.routers.admin.research_businesses.get_db") as mock_get_db, \
             patch("hephae_db.firestore.fixtures.save_fixture_from_business",
                   new_callable=AsyncMock) as mock_save_fixture:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.collection.return_value.document.return_value.update = MagicMock()

            response = client.post(
                "/api/research/actions",
                json={
                    "action": "save-outreach-draft",
                    "businessId": "biz1",
                    "channel": "instagram",
                    "editedContent": "Updated caption with #hashtags",
                },
            )

        assert response.status_code == 200
        update_call = mock_db.collection.return_value.document.return_value.update
        update_data = update_call.call_args[0][0]
        assert update_data["outreachContent.instagram.edited"] == "Updated caption with #hashtags"
        # Verify correct agent key
        fixture_call_kwargs = mock_save_fixture.call_args.kwargs
        assert fixture_call_kwargs["agent_key"] == "outreach_instagram"

    def test_save_draft_contact_form(self, client):
        """Save draft for contact form channel."""
        with patch("hephae_api.routers.admin.research_businesses.get_db") as mock_get_db, \
             patch("hephae_db.firestore.fixtures.save_fixture_from_business",
                   new_callable=AsyncMock) as mock_save_fixture:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_db.collection.return_value.document.return_value.update = MagicMock()

            response = client.post(
                "/api/research/actions",
                json={
                    "action": "save-outreach-draft",
                    "businessId": "biz1",
                    "channel": "contactForm",
                    "editedContent": "Hi, we help businesses optimize. Visit us at hephae.co",
                },
            )

        assert response.status_code == 200
        update_call = mock_db.collection.return_value.document.return_value.update
        update_data = update_call.call_args[0][0]
        assert update_data["outreachContent.contactForm.edited"] == "Hi, we help businesses optimize. Visit us at hephae.co"
        fixture_call_kwargs = mock_save_fixture.call_args.kwargs
        assert fixture_call_kwargs["agent_key"] == "outreach_contactForm"
