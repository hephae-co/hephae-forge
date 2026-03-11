"""Unit tests for USDA NASS QuickStats client."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from hephae_integrations.usda_client import (
    _get_commodities_for_industry,
    _parse_records,
    _generate_highlights,
    query_usda_prices,
    INDUSTRY_COMMODITIES,
    DEFAULT_FOOD_COMMODITIES,
)


# ---------------------------------------------------------------------------
# _get_commodities_for_industry
# ---------------------------------------------------------------------------

class TestGetCommoditiesForIndustry:
    def test_direct_match(self):
        result = _get_commodities_for_industry("pizza")
        assert result == INDUSTRY_COMMODITIES["pizza"]

    def test_singular_fallback(self):
        result = _get_commodities_for_industry("bakeries")
        assert result == INDUSTRY_COMMODITIES["bakeries"]

    def test_unknown_returns_defaults(self):
        result = _get_commodities_for_industry("car_wash")
        assert result == DEFAULT_FOOD_COMMODITIES

    def test_case_insensitive(self):
        result = _get_commodities_for_industry("  Pizza  ")
        assert result == INDUSTRY_COMMODITIES["pizza"]

    def test_partial_match(self):
        result = _get_commodities_for_industry("juice bar smoothie")
        # "juice bar" is in the key, should match
        assert result == INDUSTRY_COMMODITIES["juice bar"]


# ---------------------------------------------------------------------------
# _parse_records
# ---------------------------------------------------------------------------

class TestParseRecords:
    def test_basic_parsing(self):
        records = [
            {
                "commodity_desc": "WHEAT",
                "year": "2024",
                "reference_period_desc": "YEAR",
                "Value": "7.50",
                "unit_desc": "$ / BU",
                "state_name": "US TOTAL",
            },
        ]
        result = _parse_records(records)
        assert len(result) == 1
        assert result[0]["commodity"] == "WHEAT"
        assert result[0]["year"] == 2024
        assert result[0]["value"] == 7.5
        assert result[0]["unit"] == "$ / BU"

    def test_withheld_values_skipped(self):
        records = [
            {"commodity_desc": "X", "year": "2024", "Value": "(D)", "unit_desc": "X"},
            {"commodity_desc": "X", "year": "2024", "Value": "(NA)", "unit_desc": "X"},
            {"commodity_desc": "X", "year": "2024", "Value": "(Z)", "unit_desc": "X"},
            {"commodity_desc": "X", "year": "2024", "Value": "(S)", "unit_desc": "X"},
        ]
        result = _parse_records(records)
        assert len(result) == 0

    def test_comma_formatted_numbers(self):
        records = [
            {
                "commodity_desc": "CATTLE",
                "year": "2024",
                "Value": "1,234.56",
                "unit_desc": "HEAD",
                "state_name": "US",
            },
        ]
        result = _parse_records(records)
        assert result[0]["value"] == pytest.approx(1234.56)

    def test_sorted_by_commodity_then_year(self):
        records = [
            {"commodity_desc": "MILK", "year": "2025", "Value": "20.0", "unit_desc": "CWT"},
            {"commodity_desc": "EGGS", "year": "2024", "Value": "2.0", "unit_desc": "DOZ"},
            {"commodity_desc": "MILK", "year": "2024", "Value": "19.0", "unit_desc": "CWT"},
        ]
        result = _parse_records(records)
        commodities_years = [(p["commodity"], p["year"]) for p in result]
        assert commodities_years == [("EGGS", 2024), ("MILK", 2024), ("MILK", 2025)]

    def test_empty_value_skipped(self):
        records = [
            {"commodity_desc": "X", "year": "2024", "Value": "", "unit_desc": "X"},
            {"commodity_desc": "X", "year": "2024", "Value": "   ", "unit_desc": "X"},
        ]
        result = _parse_records(records)
        assert len(result) == 0

    def test_invalid_float_skipped(self):
        records = [
            {"commodity_desc": "X", "year": "2024", "Value": "N/A", "unit_desc": "X"},
        ]
        result = _parse_records(records)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# _generate_highlights
# ---------------------------------------------------------------------------

class TestGenerateHighlights:
    def test_yoy_change(self):
        prices = [
            {"commodity": "WHEAT", "year": 2023, "value": 7.00, "unit": "$ / BU", "state": "US"},
            {"commodity": "WHEAT", "year": 2024, "value": 7.70, "unit": "$ / BU", "state": "US"},
        ]
        highlights = _generate_highlights(prices)
        assert len(highlights) == 1
        assert "WHEAT" in highlights[0]
        assert "10.0%" in highlights[0]
        assert "up" in highlights[0]

    def test_single_year_fallback(self):
        prices = [
            {"commodity": "MILK", "year": 2024, "value": 20.5, "unit": "CWT", "state": "US"},
        ]
        highlights = _generate_highlights(prices)
        assert len(highlights) == 1
        assert "$20.50" in highlights[0]
        assert "(2024)" in highlights[0]

    def test_decline(self):
        prices = [
            {"commodity": "EGGS", "year": 2023, "value": 3.00, "unit": "DOZ", "state": "US"},
            {"commodity": "EGGS", "year": 2024, "value": 2.40, "unit": "DOZ", "state": "US"},
        ]
        highlights = _generate_highlights(prices)
        assert "down" in highlights[0]
        assert "20.0%" in highlights[0]

    def test_zero_prev_value(self):
        prices = [
            {"commodity": "X", "year": 2023, "value": 0.0, "unit": "U", "state": "US"},
            {"commodity": "X", "year": 2024, "value": 5.0, "unit": "U", "state": "US"},
        ]
        highlights = _generate_highlights(prices)
        # Cannot compute pct change — should just show latest value
        assert "$5.00" in highlights[0]

    def test_multiple_commodities(self):
        prices = [
            {"commodity": "A", "year": 2023, "value": 10.0, "unit": "U", "state": "US"},
            {"commodity": "A", "year": 2024, "value": 12.0, "unit": "U", "state": "US"},
            {"commodity": "B", "year": 2024, "value": 5.0, "unit": "U", "state": "US"},
        ]
        highlights = _generate_highlights(prices)
        assert len(highlights) == 2


# ---------------------------------------------------------------------------
# query_usda_prices (async, mocked)
# ---------------------------------------------------------------------------

class TestQueryUsdaPrices:
    @pytest.mark.asyncio
    async def test_success_with_state(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "commodity_desc": "WHEAT",
                    "year": "2024",
                    "reference_period_desc": "YEAR",
                    "Value": "7.50",
                    "unit_desc": "$ / BU",
                    "state_name": "NEW JERSEY",
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_integrations.usda_client.httpx.AsyncClient", return_value=mock_client):
            result = await query_usda_prices("bakeries", state="NJ", api_key="test-key")

        assert isinstance(result, dict)
        assert len(result["commodities"]) > 0
        assert result["commodities"][0]["commodity"] == "WHEAT"

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_empty(self):
        with patch.dict("os.environ", {"USDA_NASS_API_KEY": ""}, clear=False):
            result = await query_usda_prices("pizza", api_key="")

        assert isinstance(result, dict)
        assert result["commodities"] == []

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """Some commodities return data, some fail — should still return partial data."""
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "data": [
                {
                    "commodity_desc": "WHEAT",
                    "year": "2024",
                    "Value": "7.50",
                    "unit_desc": "$ / BU",
                    "state_name": "US",
                },
            ],
        }

        fail_response = MagicMock()
        fail_response.status_code = 400
        fail_response.text = "bad request"

        mock_client = AsyncMock()
        # First call succeeds, second fails
        mock_client.get.side_effect = [success_response, fail_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_integrations.usda_client.httpx.AsyncClient", return_value=mock_client), \
             patch("hephae_integrations.usda_client._get_commodities_for_industry") as mock_get_comms:
            mock_get_comms.return_value = [
                {"commodity_desc": "WHEAT", "statisticcat_desc": "PRICE RECEIVED"},
                {"commodity_desc": "CATFISH", "statisticcat_desc": "PRICE RECEIVED"},
            ]
            result = await query_usda_prices("bakeries", api_key="test-key")

        # Should have the wheat record but not catfish
        assert len(result["commodities"]) == 1
        assert result["commodities"][0]["commodity"] == "WHEAT"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self):
        cached_data = {
            "commodities": [
                {"commodity": "WHEAT", "year": 2024, "period": "YEAR", "value": 7.5, "unit": "$ / BU", "state": "US"},
            ],
            "highlights": ["WHEAT: $7.50/$ / BU (2024)"],
        }

        cache_reader = AsyncMock(return_value=cached_data)

        with patch("hephae_integrations.usda_client.httpx.AsyncClient") as mock_http:
            result = await query_usda_prices("bakeries", state="NJ", api_key="test-key", cache_reader=cache_reader)

        assert isinstance(result, dict)
        assert len(result["commodities"]) == 1
        mock_http.assert_not_called()
