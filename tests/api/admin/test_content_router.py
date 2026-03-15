"""Unit tests for the content router endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from hephae_api.types import ContentPost, ContentStatus, ContentPlatform, ContentType, ContentSourceType


@pytest.fixture
def client():
    """Create a test client with mocked Firebase and bypassed admin auth."""
    with patch("hephae_common.firebase.get_db"):
        from hephae_api.main import app
        from hephae_api.lib.auth import verify_admin_request

        app.dependency_overrides[verify_admin_request] = lambda: {"uid": "test-admin", "email": "admin@test.com"}
        yield TestClient(app)
        app.dependency_overrides.pop(verify_admin_request, None)


def _make_draft(**overrides) -> dict:
    """Return a draft post as a plain dict (matching Firestore return shape)."""
    defaults = dict(
        id="post-123",
        type=ContentType.SOCIAL.value,
        platform=ContentPlatform.X.value,
        status=ContentStatus.DRAFT.value,
        sourceType=ContentSourceType.ZIPCODE_RESEARCH.value,
        sourceId="run-1",
        sourceLabel="Zip 07110",
        content="Test post content",
        hashtags=["local", "marketing"],
    )
    defaults.update(overrides)
    return defaults


class TestGenerateContent:
    """POST /api/content/generate"""

    def test_generate_success(self, client):
        # get_run returns a dict with "report" and "zipCode"
        mock_run_data = {
            "report": {"summary": "test"},
            "zipCode": "07110",
        }

        forge_response = {
            "success": True,
            "data": {"content": "Great post!", "title": None, "hashtags": ["local"]},
        }

        # Mock the httpx.AsyncClient context manager properly
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = forge_response

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_resp
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_api.routers.admin.content.get_run", new_callable=AsyncMock, return_value=mock_run_data), \
             patch("hephae_api.routers.admin.content.save_content_post", new_callable=AsyncMock, return_value="new-id"), \
             patch("hephae_api.routers.admin.content.httpx.AsyncClient", return_value=mock_client_instance):

            response = client.post("/api/content/generate", json={
                "platform": "x",
                "sourceType": "zipcode_research",
                "sourceId": "run-1",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["post"]["content"] == "Great post!"

    def test_generate_missing_source_returns_404(self, client):
        with patch("hephae_api.routers.admin.content.get_run", new_callable=AsyncMock, return_value=None):
            response = client.post("/api/content/generate", json={
                "platform": "x",
                "sourceType": "zipcode_research",
                "sourceId": "nonexistent",
            })
        assert response.status_code == 404

    def test_generate_invalid_platform_returns_422(self, client):
        response = client.post("/api/content/generate", json={
            "platform": "tiktok",
            "sourceType": "zipcode_research",
            "sourceId": "run-1",
        })
        assert response.status_code == 422


class TestListPosts:
    """GET /api/content"""

    def test_list_posts(self, client):
        drafts = [_make_draft(), _make_draft(id="post-456")]
        with patch("hephae_api.routers.admin.content.list_content_posts", new_callable=AsyncMock, return_value=drafts):
            response = client.get("/api/content?limit=10")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_posts_with_platform_filter(self, client):
        with patch("hephae_api.routers.admin.content.list_content_posts", new_callable=AsyncMock, return_value=[]) as mock_list:
            response = client.get("/api/content?platform=x")

        assert response.status_code == 200
        mock_list.assert_called_once_with(limit=20, platform="x")


class TestGetPost:
    """GET /api/content/{id}"""

    def test_get_post(self, client):
        draft = _make_draft()
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=draft):
            response = client.get("/api/content/post-123")
        assert response.status_code == 200
        assert response.json()["id"] == "post-123"

    def test_get_post_not_found(self, client):
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=None):
            response = client.get("/api/content/nonexistent")
        assert response.status_code == 404


class TestEditPost:
    """PATCH /api/content/{id}"""

    def test_edit_draft(self, client):
        draft = _make_draft()
        updated = _make_draft(content="Updated content")
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, side_effect=[draft, updated]), \
             patch("hephae_api.routers.admin.content.update_content_post", new_callable=AsyncMock):
            response = client.patch("/api/content/post-123", json={"content": "Updated content"})

        assert response.status_code == 200
        assert response.json()["content"] == "Updated content"

    def test_edit_published_post_rejected(self, client):
        published = _make_draft(status=ContentStatus.PUBLISHED.value)
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=published):
            response = client.patch("/api/content/post-123", json={"content": "New"})
        assert response.status_code == 400
        assert "drafts" in response.json()["detail"].lower()


class TestPublishPost:
    """POST /api/content/{id}/publish"""

    def test_publish_blog(self, client):
        blog_draft = _make_draft(platform=ContentPlatform.BLOG.value, type=ContentType.BLOG.value)
        published = _make_draft(platform=ContentPlatform.BLOG.value, status=ContentStatus.PUBLISHED.value)
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, side_effect=[blog_draft, published]), \
             patch("hephae_api.routers.admin.content.update_content_post", new_callable=AsyncMock):
            response = client.post("/api/content/post-123/publish")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_publish_already_published_rejected(self, client):
        published = _make_draft(status=ContentStatus.PUBLISHED.value)
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=published):
            response = client.post("/api/content/post-123/publish")
        assert response.status_code == 400

    def test_publish_not_found(self, client):
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=None):
            response = client.post("/api/content/nonexistent/publish")
        assert response.status_code == 404


class TestDeletePost:
    """DELETE /api/content/{id}"""

    def test_delete_draft(self, client):
        draft = _make_draft()
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=draft), \
             patch("hephae_api.routers.admin.content.delete_content_post", new_callable=AsyncMock):
            response = client.delete("/api/content/post-123")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_published_rejected(self, client):
        published = _make_draft(status=ContentStatus.PUBLISHED.value)
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=published):
            response = client.delete("/api/content/post-123")
        assert response.status_code == 400

    def test_delete_not_found(self, client):
        with patch("hephae_api.routers.admin.content.get_content_post", new_callable=AsyncMock, return_value=None):
            response = client.delete("/api/content/nonexistent")
        assert response.status_code == 404
