"""Unit tests for BLS Consumer Price Index client."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from hephae_integrations.bls_client import (
    _get_relevant_series,
    _parse_series_data,
    _generate_highlights,
    query_bls_cpi,
    FOOD_CPI_SERIES,
    DETAILED_SERIES,
)


# ---------------------------------------------------------------------------
# _get_relevant_series
# ---------------------------------------------------------------------------

class TestGetRelevantSeries:
    def test_pizza_gets_bakery_dairy_meats(self):
        series = _get_relevant_series("pizza")
        # Should include primary food series
        assert "CUUR0000SAF1" in series.values()
        # Should include bakery, dairy, meats detailed series
        for cat in ("bakery", "dairy", "meats"):
            for sid in DETAILED_SERIES[cat].values():
                assert sid in series.values(), f"Missing {cat} series {sid}"

    def test_unknown_industry_gets_only_primary(self):
        series = _get_relevant_series("car_wash")
        assert series == FOOD_CPI_SERIES

    def test_trailing_s_fallback(self):
        series = _get_relevant_series("bakeries")
        # "bakeries" is a direct match in INDUSTRY_TO_DETAILED
        for sid in DETAILED_SERIES["bakery"].values():
            assert sid in series.values()

    def test_case_insensitive(self):
        series = _get_relevant_series("  Pizza  ")
        for sid in DETAILED_SERIES["bakery"].values():
            assert sid in series.values()

    def test_coffee_gets_beverages(self):
        series = _get_relevant_series("coffee")
        for sid in DETAILED_SERIES["beverages"].values():
            assert sid in series.values()


# ---------------------------------------------------------------------------
# _parse_series_data
# ---------------------------------------------------------------------------

class TestParseSeriesData:
    def test_basic_parsing(self):
        raw = {
            "seriesID": "CUUR0000SAF1",
            "data": [
                {
                    "year": "2025",
                    "period": "M03",
                    "value": "310.5",
                    "calculations": {"pct_changes": {"12": "2.5"}},
                },
                {
                    "year": "2025",
                    "period": "M02",
                    "value": "309.1",
                    "calculations": {"pct_changes": {"12": "2.3"}},
                },
            ],
        }
        result = _parse_series_data(raw)
        assert result["seriesId"] == "CUUR0000SAF1"
        assert result["label"] == "Food (all items)"
        assert len(result["data"]) == 2
        # Should be sorted chronologically (Feb before Mar)
        assert result["data"][0]["month"] == 2
        assert result["data"][1]["month"] == 3

    def test_m13_annual_avg_skipped(self):
        raw = {
            "seriesID": "CUUR0000SAF1",
            "data": [
                {"year": "2025", "period": "M13", "value": "300.0", "calculations": {}},
                {"year": "2025", "period": "M01", "value": "305.0", "calculations": {}},
            ],
        }
        result = _parse_series_data(raw)
        assert len(result["data"]) == 1
        assert result["data"][0]["month"] == 1

    def test_yoy_extraction(self):
        raw = {
            "seriesID": "CUUR0000SAF1",
            "data": [
                {
                    "year": "2025",
                    "period": "M06",
                    "value": "315.0",
                    "calculations": {"pct_changes": {"12": "-1.2"}},
                },
            ],
        }
        result = _parse_series_data(raw)
        assert result["data"][0]["yoyPctChange"] == pytest.approx(-1.2)

    def test_missing_yoy_is_none(self):
        raw = {
            "seriesID": "CUUR0000SAF1",
            "data": [
                {"year": "2025", "period": "M01", "value": "300.0", "calculations": {}},
            ],
        }
        result = _parse_series_data(raw)
        assert result["data"][0]["yoyPctChange"] is None

    def test_chronological_sort(self):
        raw = {
            "seriesID": "CUUR0000SAF1",
            "data": [
                {"year": "2025", "period": "M12", "value": "320.0", "calculations": {}},
                {"year": "2024", "period": "M06", "value": "310.0", "calculations": {}},
                {"year": "2025", "period": "M01", "value": "315.0", "calculations": {}},
            ],
        }
        result = _parse_series_data(raw)
        periods = [(d["year"], d["month"]) for d in result["data"]]
        assert periods == [(2024, 6), (2025, 1), (2025, 12)]

    def test_unknown_series_id_uses_id_as_label(self):
        raw = {
            "seriesID": "UNKNOWN123",
            "data": [{"year": "2025", "period": "M01", "value": "100.0", "calculations": {}}],
        }
        result = _parse_series_data(raw)
        assert result["label"] == "UNKNOWN123"


# ---------------------------------------------------------------------------
# _generate_highlights
# ---------------------------------------------------------------------------

class TestGenerateHighlights:
    def test_basic_highlight(self):
        series_list = [
            {
                "seriesId": "CUUR0000SAF1",
                "label": "Food (all items)",
                "data": [{"year": 2025, "month": 3, "period": "2025-03", "indexValue": 310.5, "yoyPctChange": 2.5}],
            },
        ]
        highlights = _generate_highlights(series_list)
        assert len(highlights) == 1
        assert "Food (all items)" in highlights[0]
        assert "2.5%" in highlights[0]
        assert "up" in highlights[0]

    def test_negative_change_says_down(self):
        series_list = [
            {
                "seriesId": "X",
                "label": "Eggs",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 200.0, "yoyPctChange": -3.1}],
            },
        ]
        highlights = _generate_highlights(series_list)
        assert "down" in highlights[0]
        assert "3.1%" in highlights[0]

    def test_sorted_by_biggest_movers(self):
        series_list = [
            {
                "seriesId": "A", "label": "Small",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 100.0, "yoyPctChange": 0.5}],
            },
            {
                "seriesId": "B", "label": "Big",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 100.0, "yoyPctChange": -8.0}],
            },
            {
                "seriesId": "C", "label": "Medium",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 100.0, "yoyPctChange": 3.0}],
            },
        ]
        highlights = _generate_highlights(series_list)
        assert "Big" in highlights[0]
        assert "Medium" in highlights[1]
        assert "Small" in highlights[2]

    def test_max_10_highlights(self):
        series_list = [
            {
                "seriesId": f"S{i}", "label": f"Item{i}",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 100.0, "yoyPctChange": float(i)}],
            }
            for i in range(15)
        ]
        highlights = _generate_highlights(series_list)
        assert len(highlights) == 10

    def test_no_yoy_skipped(self):
        series_list = [
            {
                "seriesId": "X", "label": "NoYoY",
                "data": [{"year": 2025, "month": 1, "period": "2025-01", "indexValue": 100.0, "yoyPctChange": None}],
            },
        ]
        highlights = _generate_highlights(series_list)
        assert len(highlights) == 0

    def test_empty_series_skipped(self):
        series_list = [
            {"seriesId": "X", "label": "Empty", "data": []},
        ]
        highlights = _generate_highlights(series_list)
        assert len(highlights) == 0


# ---------------------------------------------------------------------------
# query_bls_cpi (async, mocked)
# ---------------------------------------------------------------------------

class TestQueryBlsCpi:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "REQUEST_SUCCEEDED",
            "Results": {
                "series": [
                    {
                        "seriesID": "CUUR0000SAF1",
                        "data": [
                            {
                                "year": "2025",
                                "period": "M03",
                                "value": "310.5",
                                "calculations": {"pct_changes": {"12": "2.5"}},
                            },
                        ],
                    },
                ],
            },
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_integrations.bls_client.httpx.AsyncClient", return_value=mock_client):
            result = await query_bls_cpi("pizza", api_key="test-key")

        assert isinstance(result, dict)
        assert len(result["series"]) == 1
        assert result["latestMonth"] == "2025-03"
        assert len(result["highlights"]) > 0

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_empty(self):
        with patch.dict("os.environ", {"BLS_API_KEY": ""}, clear=False):
            result = await query_bls_cpi("pizza", api_key="")

        assert isinstance(result, dict)
        assert result["series"] == []
        assert result["highlights"] == []

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_integrations.bls_client.httpx.AsyncClient", return_value=mock_client):
            result = await query_bls_cpi("pizza", api_key="test-key")

        assert result["series"] == []

    @pytest.mark.asyncio
    async def test_api_status_not_succeeded_returns_empty(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "REQUEST_NOT_PROCESSED",
            "message": ["Daily limit reached"],
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hephae_integrations.bls_client.httpx.AsyncClient", return_value=mock_client):
            result = await query_bls_cpi("pizza", api_key="test-key")

        assert result["series"] == []

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self):
        cached_data = {
            "series": [
                {
                    "seriesId": "CUUR0000SAF1",
                    "label": "Food (all items)",
                    "data": [{"year": 2025, "month": 3, "period": "2025-03", "indexValue": 310.5, "yoyPctChange": 2.5}],
                }
            ],
            "latestMonth": "2025-03",
            "highlights": ["Food (all items): 2.5% up year-over-year (index 310.5, 2025-03)"],
        }

        cache_reader = AsyncMock(return_value=cached_data)

        with patch("hephae_integrations.bls_client.httpx.AsyncClient") as mock_http:
            result = await query_bls_cpi("pizza", api_key="test-key", cache_reader=cache_reader)

        assert isinstance(result, dict)
        assert result["latestMonth"] == "2025-03"
        # httpx should NOT have been called
        mock_http.assert_not_called()
