"""Unit tests for the research businesses router endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.types import DiscoveredBusiness


@pytest.fixture
def client():
    """Create a test client with mocked Firebase."""
    with patch("backend.lib.firebase.get_db"):
        from backend.main import app
        return TestClient(app)


class TestDiscoverBusinesses:
    """POST /api/research/businesses"""

    def test_discover_with_json_body(self, client):
        """Verify endpoint accepts zipCode in JSON body (not query param)."""
        mock_businesses = [
            DiscoveredBusiness(name="Pizza Palace", address="123 Main St", docId="pizza-palace"),
            DiscoveredBusiness(name="Burger Barn", address="456 Oak Ave", docId="burger-barn"),
        ]
        with patch(
            "backend.routers.research_businesses.scan_zipcode",
            new_callable=AsyncMock,
            return_value=mock_businesses,
        ):
            response = client.post(
                "/api/research/businesses",
                json={"zipCode": "07110"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["businesses"]) == 2
        assert data["businesses"][0]["name"] == "Pizza Palace"

    def test_discover_returns_count_field(self, client):
        """Frontend depends on data.count — ensure it's in the response."""
        with patch(
            "backend.routers.research_businesses.scan_zipcode",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = client.post(
                "/api/research/businesses",
                json={"zipCode": "99999"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] == 0
        assert data["businesses"] == []

    def test_discover_missing_zipcode_returns_422(self, client):
        """Missing zipCode in body should return 422."""
        response = client.post(
            "/api/research/businesses",
            json={},
        )
        assert response.status_code == 422

    def test_discover_no_body_returns_422(self, client):
        """No request body at all should return 422."""
        response = client.post("/api/research/businesses")
        assert response.status_code == 422


class TestGetBusinesses:
    """GET /api/research/businesses"""

    def test_get_businesses_with_zipcode(self, client):
        mock_businesses = [
            {"name": "Test Biz", "zipCode": "07110", "docId": "test-biz"},
        ]
        with patch(
            "backend.routers.research_businesses.get_businesses_in_zipcode",
            new_callable=AsyncMock,
            return_value=mock_businesses,
        ):
            response = client.get("/api/research/businesses?zipCode=07110")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_businesses_missing_zipcode_returns_422(self, client):
        """GET requires zipCode as query param."""
        response = client.get("/api/research/businesses")
        assert response.status_code == 422


class TestDeleteBusiness:
    """DELETE /api/research/businesses"""

    def test_delete_business(self, client):
        with patch(
            "backend.routers.research_businesses.delete_business",
            new_callable=AsyncMock,
        ):
            response = client.delete("/api/research/businesses?id=test-biz")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_missing_id_returns_422(self, client):
        response = client.delete("/api/research/businesses")
        assert response.status_code == 422
