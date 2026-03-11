"""Unit tests for the food prices router endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from backend.types import BlsCpiData, BlsCpiSeries, BlsCpiDataPoint, UsdaPriceData, UsdaCommodityPrice


@pytest.fixture
def client():
    """Create a test client with mocked Firebase and bypassed admin auth."""
    with patch("hephae_common.firebase.get_db"):
        from backend.main import app
        from backend.lib.auth import verify_admin_request

        app.dependency_overrides[verify_admin_request] = lambda: {"uid": "test-admin", "email": "admin@test.com"}
        yield TestClient(app)
        app.dependency_overrides.pop(verify_admin_request, None)


class TestCpiEndpoint:
    def test_get_cpi(self, client):
        mock_data = BlsCpiData(
            series=[
                BlsCpiSeries(
                    seriesId="CUUR0000SAF1",
                    label="Food (all items)",
                    data=[BlsCpiDataPoint(year=2025, month=3, period="2025-03", indexValue=310.5, yoyPctChange=2.5)],
                ),
            ],
            latestMonth="2025-03",
            highlights=["Food (all items): 2.5% up year-over-year (index 310.5, 2025-03)"],
        )

        with patch("backend.routers.admin.food_prices.query_bls_cpi", new_callable=AsyncMock, return_value=mock_data):
            response = client.get("/api/food-prices/cpi?industry=pizza")

        assert response.status_code == 200
        data = response.json()
        assert data["latestMonth"] == "2025-03"
        assert len(data["series"]) == 1
        assert len(data["highlights"]) == 1

    def test_get_cpi_default_industry(self, client):
        mock_data = BlsCpiData()
        with patch("backend.routers.admin.food_prices.query_bls_cpi", new_callable=AsyncMock, return_value=mock_data):
            response = client.get("/api/food-prices/cpi")
        assert response.status_code == 200


class TestCommoditiesEndpoint:
    def test_get_commodities(self, client):
        mock_data = UsdaPriceData(
            commodities=[
                UsdaCommodityPrice(commodity="WHEAT", year=2024, period="YEAR", value=7.5, unit="$ / BU", state="US"),
            ],
            highlights=["WHEAT: $7.50/$ / BU (2024)"],
        )

        with patch("backend.routers.admin.food_prices.query_usda_prices", new_callable=AsyncMock, return_value=mock_data):
            response = client.get("/api/food-prices/commodities?industry=bakeries&state=NJ")

        assert response.status_code == 200
        data = response.json()
        assert len(data["commodities"]) == 1
        assert data["commodities"][0]["commodity"] == "WHEAT"

    def test_get_commodities_defaults(self, client):
        mock_data = UsdaPriceData()
        with patch("backend.routers.admin.food_prices.query_usda_prices", new_callable=AsyncMock, return_value=mock_data):
            response = client.get("/api/food-prices/commodities")
        assert response.status_code == 200


class TestSummaryEndpoint:
    def test_get_summary(self, client):
        # Router uses .get() — pass dicts, not Pydantic models
        bls_data = {
            "series": [{"seriesId": "CUUR0000SAF1", "label": "Food (all items)", "data": []}],
            "latestMonth": "2025-03",
            "highlights": ["Food (all items): 2.5% up"],
        }
        usda_data = {
            "commodities": [{"commodity": "WHEAT", "year": 2024, "value": 7.5, "unit": "$ / BU", "state": "US"}],
            "highlights": ["WHEAT: $7.50"],
        }

        with patch("backend.routers.admin.food_prices.query_bls_cpi", new_callable=AsyncMock, return_value=bls_data), \
             patch("backend.routers.admin.food_prices.query_usda_prices", new_callable=AsyncMock, return_value=usda_data):
            response = client.get("/api/food-prices/summary?industry=pizza&state=NJ")

        assert response.status_code == 200
        data = response.json()
        assert "BLS Consumer Price Index" in data["sources"]
        assert "USDA NASS QuickStats" in data["sources"]
        assert len(data["highlights"]) == 2
        assert data["blsCpi"] is not None
        assert data["usdaNass"] is not None

    def test_summary_with_empty_data(self, client):
        with patch("backend.routers.admin.food_prices.query_bls_cpi", new_callable=AsyncMock, return_value={"series": [], "highlights": []}), \
             patch("backend.routers.admin.food_prices.query_usda_prices", new_callable=AsyncMock, return_value={"commodities": [], "highlights": []}):
            response = client.get("/api/food-prices/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["sources"] == []
        assert data["highlights"] == []
