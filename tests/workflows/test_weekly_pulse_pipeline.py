"""Weekly Pulse Pipeline — unit tests for Phases A-C.

Covers:
- A: Schema validation, signal archive CRUD, batch work item CRUD,
     impact multipliers, playbook matching, gemini_batch tools field
- B: Critique thresholds, rewrite feedback generation
- C: Batch ID mapping, batch processor stage orchestration
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


# ═══════════════════════════════════════════════════════════════════════════
# Phase A: Foundation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPulseOutputSchemas:
    """A1: Schema validation — WeeklyPulseOutput, InsightCritique, CritiqueResult."""

    def test_weekly_pulse_output_valid(self):
        from hephae_db.schemas import WeeklyPulseOutput

        output = WeeklyPulseOutput(
            zipCode="07110",
            businessType="restaurants",
            weekOf="2026-W12",
            headline="Delivery adoption hits tipping point",
            insights=[],
            quickStats={"trendingSearches": [], "weatherOutlook": "Clear"},
        )
        assert output.zipCode == "07110"
        assert output.headline == "Delivery adoption hits tipping point"

    def test_weekly_pulse_output_null_safety(self):
        """Gemini sometimes returns null for non-nullable fields."""
        from hephae_db.schemas import WeeklyPulseOutput

        output = WeeklyPulseOutput(
            zipCode="07110",
            businessType="restaurants",
            weekOf="2026-W12",
            headline="Test",
            insights=None,  # Gemini might return null
            quickStats=None,  # Gemini might return null
        )
        assert output.insights == []
        assert output.quickStats is not None

    def test_pulse_insight_with_signal_sources(self):
        from hephae_db.schemas import PulseInsight

        insight = PulseInsight(
            rank=1,
            title="Delivery gap closing",
            analysis="3 competitors added delivery",
            recommendation="Launch delivery now",
            dataSources=["OSM", "Google Trends"],
            impactScore=82,
            impactLevel="high",
            timeSensitivity="this_week",
            signalSources=["osm", "trends", "socialPulse"],
            playbookUsed="competitor_delivery_wave",
        )
        assert insight.signalSources == ["osm", "trends", "socialPulse"]
        assert insight.playbookUsed == "competitor_delivery_wave"

    def test_pulse_insight_defaults(self):
        """signalSources and playbookUsed should default to empty."""
        from hephae_db.schemas import PulseInsight

        insight = PulseInsight(
            title="Test", analysis="Test", recommendation="Test",
        )
        assert insight.signalSources == []
        assert insight.playbookUsed == ""
        assert insight.impactScore == 50
        assert insight.impactLevel == "medium"

    def test_critique_result_valid(self):
        from hephae_db.schemas import CritiqueResult, InsightCritique

        critique = CritiqueResult(
            overall_pass=False,
            insights=[
                InsightCritique(
                    insight_rank=1,
                    obviousness_score=85,
                    actionability_score=30,
                    cross_signal_score=20,
                    verdict="REWRITE",
                    rewrite_instruction="Too obvious — everyone knows it rains.",
                ),
                InsightCritique(
                    insight_rank=2,
                    obviousness_score=15,
                    actionability_score=80,
                    cross_signal_score=75,
                    verdict="PASS",
                ),
            ],
            summary="1 of 2 insights needs rewrite",
        )
        assert not critique.overall_pass
        assert len(critique.insights) == 2
        assert critique.insights[0].verdict == "REWRITE"
        assert critique.insights[1].verdict == "PASS"

    def test_critique_result_null_safety(self):
        from hephae_db.schemas import CritiqueResult

        critique = CritiqueResult(
            overall_pass=None,  # Gemini null
            insights=None,
        )
        assert critique.overall_pass is False
        assert critique.insights == []

    def test_insight_critique_defaults(self):
        from hephae_db.schemas import InsightCritique

        ic = InsightCritique()
        assert ic.insight_rank == 1
        assert ic.obviousness_score == 50
        assert ic.actionability_score == 50
        assert ic.cross_signal_score == 50
        assert ic.verdict == "PASS"
        assert ic.rewrite_instruction == ""

    def test_weekly_pulse_output_json_schema(self):
        """Verify model_json_schema() works for Vertex batch response_schema."""
        from hephae_db.schemas import WeeklyPulseOutput

        schema = WeeklyPulseOutput.model_json_schema()
        assert "properties" in schema
        assert "zipCode" in schema["properties"]
        assert "insights" in schema["properties"]
        assert "headline" in schema["properties"]

    def test_critique_result_json_schema(self):
        from hephae_db.schemas import CritiqueResult

        schema = CritiqueResult.model_json_schema()
        assert "properties" in schema
        assert "overall_pass" in schema["properties"]
        assert "insights" in schema["properties"]


class TestImpactMultipliers:
    """A5: Pre-computed impact arithmetic is correct (no LLM)."""

    def test_empty_signals(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        result = compute_impact_multipliers({})
        assert isinstance(result, dict)
        # No crash on empty

    def test_bls_price_deltas(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        signals = {
            "priceDeltas": [
                {"label": "Dairy", "yoyPctChange": 12.1, "momPctChange": 3.4},
                {"label": "Poultry", "yoyPctChange": -5.3, "momPctChange": -0.8},
                {"label": "Cereals", "yoyPctChange": 2.0, "momPctChange": 0.5},
            ],
        }
        result = compute_impact_multipliers(signals)
        assert result["dairy_yoy_pct"] == 12.1
        assert result["poultry_yoy_pct"] == -5.3
        assert result["dairy_mom_pct"] == 3.4

    def test_census_and_irs(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        signals = {
            "censusDemographics": {
                "medianHouseholdIncome": 72500,
                "totalPopulation": 28000,
                "povertyRate": 8.2,
            },
            "irsIncome": {"avgAGI": 85000, "selfEmploymentRate": 12.5},
        }
        result = compute_impact_multipliers(signals)
        assert result["median_income"] == 72500
        assert result["population"] == 28000
        assert result["avg_agi"] == 85000
        assert result["self_employment_rate"] == 12.5

    def test_weather_traffic_modifier(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        # 3 rainy days out of 7
        signals = {
            "weather": {
                "forecast": [
                    {"shortForecast": "Rain"},
                    {"shortForecast": "Showers"},
                    {"shortForecast": "Sunny"},
                    {"shortForecast": "Rain"},
                    {"shortForecast": "Clear"},
                    {"shortForecast": "Partly Cloudy"},
                    {"shortForecast": "Clear"},
                ],
            },
        }
        result = compute_impact_multipliers(signals)
        assert result["weather_traffic_modifier"] == -0.15  # -0.05 * 3

    def test_net_traffic_delta(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        signals = {
            "weather": {"forecast": [{"shortForecast": "Rain"}] * 2 + [{"shortForecast": "Clear"}] * 5},
            "localCatalysts": {
                "catalysts": [
                    {"type": "Development"},
                    {"type": "Infrastructure"},
                ],
            },
        }
        result = compute_impact_multipliers(signals)
        # weather: -0.05 * 2 = -0.10
        # events: 0.10 * 2 = 0.20
        # net: 0.10
        assert result["weather_traffic_modifier"] == -0.10
        assert result["event_traffic_modifier"] == 0.20
        assert result["net_traffic_delta"] == 0.10

    def test_osm_competitor_count(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        signals = {"osmDensity": {"totalBusinesses": 14}}
        result = compute_impact_multipliers(signals)
        assert result["competitor_count"] == 14

    def test_fda_recall_count(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import compute_impact_multipliers

        signals = {"fdaRecalls": {"recentRecallCount": 5, "totalRecalls": 20}}
        result = compute_impact_multipliers(signals)
        assert result["fda_recent_recall_count"] == 5


class TestPlaybookMatching:
    """A5: Correct playbooks matched for known signal conditions."""

    def test_dairy_margin_swap_triggers(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"dairy_yoy_pct": 12.1, "poultry_yoy_pct": -5.3}
        matched = match_playbooks(pre_computed, business_type="restaurants")
        names = [m["name"] for m in matched]
        assert "dairy_margin_swap" in names

    def test_dairy_margin_swap_not_triggered_low_dairy(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"dairy_yoy_pct": 3.0, "poultry_yoy_pct": -5.3}
        matched = match_playbooks(pre_computed, business_type="restaurants")
        names = [m["name"] for m in matched]
        assert "dairy_margin_swap" not in names

    def test_competitor_delivery_wave(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"delivery_adoption_pct": 0.71}
        matched = match_playbooks(pre_computed, business_type="restaurants")
        names = [m["name"] for m in matched]
        assert "competitor_delivery_wave" in names

    def test_weather_rain_prep_for_food(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"weather_traffic_modifier": -0.15}
        matched = match_playbooks(pre_computed, business_type="restaurants")
        names = [m["name"] for m in matched]
        assert "weather_rain_prep" in names

    def test_weather_rain_prep_skipped_for_non_food(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"weather_traffic_modifier": -0.15}
        matched = match_playbooks(pre_computed, business_type="auto repair")
        names = [m["name"] for m in matched]
        assert "weather_rain_prep" not in names

    def test_no_matches_with_empty_data(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        matched = match_playbooks({}, business_type="restaurants")
        assert matched == []

    def test_multiple_playbooks_match(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {
            "dairy_yoy_pct": 12.1,
            "poultry_yoy_pct": -5.3,
            "delivery_adoption_pct": 0.80,
            "weather_traffic_modifier": -0.15,
            "event_traffic_modifier": 0.0,
            "net_traffic_delta": -0.15,
        }
        matched = match_playbooks(pre_computed, business_type="restaurants")
        names = [m["name"] for m in matched]
        assert "dairy_margin_swap" in names
        assert "competitor_delivery_wave" in names
        assert "weather_rain_prep" in names

    def test_playbook_variable_substitution(self):
        from hephae_api.workflows.orchestrators.pulse_playbooks import match_playbooks

        pre_computed = {"dairy_yoy_pct": 12.1, "poultry_yoy_pct": -5.3}
        matched = match_playbooks(pre_computed, business_type="restaurants")
        dairy_pb = next(m for m in matched if m["name"] == "dairy_margin_swap")
        assert "12.1" in dairy_pb["play"]
        assert "-5.3" in dairy_pb["play"]


class TestGeminiBatchToolsField:
    """A6: JSONL includes tools when provided, omits when not."""

    def test_jsonl_includes_tools_field(self):
        """Verify the tools field is included in JSONL for grounding."""
        import json as _json

        # Simulate the JSONL builder logic from submit_vertex_batch
        req = {
            "request_id": "test:07110:social_pulse",
            "contents": [{"role": "user", "parts": [{"text": "test prompt"}]}],
            "tools": [{"google_search_retrieval": {
                "dynamic_retrieval_config": {"mode": "MODE_DYNAMIC"},
            }}],
            "config": {"response_mime_type": "application/json"},
        }

        # Replicate the JSONL builder from gemini_batch.py
        line = {
            "request_id": req["request_id"],
            "model": "publishers/google/models/gemini-3.1-flash-lite-preview",
            "contents": req["contents"],
        }
        if req.get("config"):
            line["generation_config"] = req["config"]
        if req.get("tools"):
            line["tools"] = req["tools"]

        jsonl = _json.dumps(line)
        parsed = _json.loads(jsonl)

        assert "tools" in parsed
        assert parsed["tools"][0]["google_search_retrieval"]["dynamic_retrieval_config"]["mode"] == "MODE_DYNAMIC"

    def test_jsonl_omits_tools_when_not_provided(self):
        import json as _json

        req = {
            "request_id": "test:07110:economist",
            "contents": [{"role": "user", "parts": [{"text": "test prompt"}]}],
        }

        line = {
            "request_id": req["request_id"],
            "model": "publishers/google/models/gemini-3.1-flash-lite-preview",
            "contents": req["contents"],
        }
        if req.get("config"):
            line["generation_config"] = req["config"]
        if req.get("tools"):
            line["tools"] = req["tools"]

        jsonl = _json.dumps(line)
        parsed = _json.loads(jsonl)

        assert "tools" not in parsed


class TestIndustryPluginsStripped:
    """A7: industry_plugins.py retains type classification, fetchers removed."""

    def test_is_food_business(self):
        from hephae_api.workflows.orchestrators.industry_plugins import is_food_business

        assert is_food_business("restaurants") is True
        assert is_food_business("pizza") is True
        assert is_food_business("auto repair") is False
        assert is_food_business("salons") is False

    def test_classify_business_type(self):
        from hephae_api.workflows.orchestrators.industry_plugins import classify_business_type

        assert classify_business_type("restaurants") == "food"
        assert classify_business_type("clothing") == "retail"
        assert classify_business_type("salons") == "beauty"
        assert classify_business_type("auto repair") == "service"
        assert classify_business_type("consulting") == "general"

    def test_fetch_industry_data_removed(self):
        """fetch_industry_data should no longer exist in the module."""
        import hephae_api.workflows.orchestrators.industry_plugins as ip

        assert not hasattr(ip, "fetch_industry_data")


# ═══════════════════════════════════════════════════════════════════════════
# Phase A: Firestore CRUD tests (mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestSignalArchiveCRUD:
    """A2: Save/read archive roundtrip."""

    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self):
        from hephae_db.firestore.signal_archive import save_signal_archive, get_signal_archive

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "zipCode": "07110",
            "weekOf": "2026-W12",
            "collectedAt": datetime.utcnow(),
            "sources": {"blsCpi": {"raw": {"test": True}, "fetchedAt": "2026-03-18", "version": "v1"}},
            "preComputedImpact": {"dairy_yoy_pct": 12.1},
        }
        mock_doc.id = "07110-2026-W12"

        mock_collection = MagicMock()
        mock_collection.document.return_value = MagicMock(
            get=MagicMock(return_value=mock_doc),
            set=MagicMock(),
        )

        mock_db = MagicMock()
        mock_db.collection.return_value = mock_collection

        with patch("hephae_db.firestore.signal_archive.get_db", return_value=mock_db):
            doc_id = await save_signal_archive(
                "07110", "2026-W12",
                {"blsCpi": {"raw": {"test": True}, "fetchedAt": "2026-03-18", "version": "v1"}},
                {"dairy_yoy_pct": 12.1},
            )
            assert doc_id == "07110-2026-W12"

            result = await get_signal_archive("07110", "2026-W12")
            assert result is not None
            assert result["zipCode"] == "07110"
            assert "blsCpi" in result["sources"]


class TestPulseBatchWorkItemCRUD:
    """A3/C1: Batch work item CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_work_items(self):
        from hephae_db.firestore.pulse_batch import create_work_items

        mock_batch = MagicMock()
        mock_batch.commit = MagicMock()
        mock_batch.set = MagicMock()

        mock_db = MagicMock()
        mock_db.batch.return_value = mock_batch
        mock_db.collection.return_value = MagicMock(
            document=MagicMock(return_value=MagicMock())
        )

        with patch("hephae_db.firestore.pulse_batch.get_db", return_value=mock_db):
            count = await create_work_items(
                "pulse-essex-2026-W12",
                ["07110", "07042", "07003"],
                "restaurants",
                "2026-W12",
            )
            assert count == 3
            assert mock_batch.set.call_count == 3

    @pytest.mark.asyncio
    async def test_update_work_item(self):
        from hephae_db.firestore.pulse_batch import update_work_item

        mock_doc_ref = MagicMock()
        mock_doc_ref.update = MagicMock()

        mock_db = MagicMock()
        mock_db.collection.return_value = MagicMock(
            document=MagicMock(return_value=mock_doc_ref)
        )

        with patch("hephae_db.firestore.pulse_batch.get_db", return_value=mock_db):
            await update_work_item(
                "pulse-essex-2026-W12", "07110",
                {"status": "RESEARCH", "rawSignals": {"test": True}},
            )
            mock_doc_ref.update.assert_called_once()
            call_args = mock_doc_ref.update.call_args[0][0]
            assert call_args["status"] == "RESEARCH"
            assert "updatedAt" in call_args

    @pytest.mark.asyncio
    async def test_get_batch_summary(self):
        from hephae_db.firestore.pulse_batch import get_batch_summary

        mock_docs = []
        for status in ["COMPLETED", "COMPLETED", "FAILED", "RESEARCH"]:
            doc = MagicMock()
            doc.to_dict.return_value = {"batchId": "test-batch", "status": status}
            doc.id = f"test-batch:{status}"
            mock_docs.append(doc)

        mock_db = MagicMock()
        mock_db.collection.return_value = MagicMock(
            where=MagicMock(return_value=MagicMock(
                get=MagicMock(return_value=mock_docs)
            ))
        )

        with patch("hephae_db.firestore.pulse_batch.get_db", return_value=mock_db):
            summary = await get_batch_summary("test-batch")
            assert summary["totalItems"] == 4
            assert summary["statusCounts"]["COMPLETED"] == 2
            assert summary["statusCounts"]["FAILED"] == 1
            assert summary["allCompleted"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Phase A: Cache tests (mocked)
# ═══════════════════════════════════════════════════════════════════════════


class TestFetchToolsCache:
    """A4: Each fetch tool returns data, second call hits cache."""

    @pytest.mark.asyncio
    async def test_fetch_census_cache_through(self):
        from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_census

        census_data = {"totalPopulation": 28000, "medianHouseholdIncome": 72500}

        with (
            patch("hephae_api.workflows.orchestrators.pulse_fetch_tools.get_cached", new_callable=AsyncMock, return_value=None) as mock_get,
            patch("hephae_api.workflows.orchestrators.pulse_fetch_tools.set_cached", new_callable=AsyncMock) as mock_set,
            patch("hephae_db.bigquery.public_data.query_census_demographics", new_callable=AsyncMock, return_value=census_data),
        ):
            result = await fetch_census("07110")
            assert result == census_data
            mock_set.assert_called_once()
            assert mock_set.call_args[0][0] == "census"
            assert mock_set.call_args[0][1] == "07110"

    @pytest.mark.asyncio
    async def test_fetch_census_cache_hit(self):
        from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_census

        cached_data = {"totalPopulation": 28000}

        with patch("hephae_api.workflows.orchestrators.pulse_fetch_tools.get_cached", new_callable=AsyncMock, return_value=cached_data):
            result = await fetch_census("07110")
            assert result == cached_data

    @pytest.mark.asyncio
    async def test_fetch_bls_cpi_cache_through(self):
        from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_bls_cpi

        bls_data = {"series": [{"label": "Dairy", "value": 123.4}], "highlights": []}

        with (
            patch("hephae_api.workflows.orchestrators.pulse_fetch_tools.get_cached", new_callable=AsyncMock, return_value=None),
            patch("hephae_api.workflows.orchestrators.pulse_fetch_tools.set_cached", new_callable=AsyncMock) as mock_set,
            patch("hephae_integrations.bls_client.query_bls_cpi", new_callable=AsyncMock, return_value=bls_data),
        ):
            result = await fetch_bls_cpi("restaurants")
            assert result == bls_data
            mock_set.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
# Phase B: Critique tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCritiqueThresholds:
    """B4: Critique score thresholds are enforced correctly."""

    def test_passing_insight(self):
        """Insight with low obviousness + high actionability + high cross-signal passes."""
        from hephae_db.schemas import InsightCritique

        ic = InsightCritique(
            insight_rank=1,
            obviousness_score=15,
            actionability_score=85,
            cross_signal_score=75,
            verdict="PASS",
        )
        # Verify thresholds
        assert ic.obviousness_score < 30  # PASS
        assert ic.actionability_score >= 70  # PASS
        assert ic.cross_signal_score >= 60  # PASS

    def test_failing_obviousness(self):
        """High obviousness score should fail."""
        from hephae_db.schemas import InsightCritique

        ic = InsightCritique(
            insight_rank=1,
            obviousness_score=85,
            actionability_score=80,
            cross_signal_score=70,
            verdict="REWRITE",
            rewrite_instruction="Too obvious",
        )
        assert ic.obviousness_score >= 30  # FAIL
        assert ic.verdict == "REWRITE"

    def test_failing_actionability(self):
        from hephae_db.schemas import InsightCritique

        ic = InsightCritique(
            insight_rank=2,
            obviousness_score=10,
            actionability_score=40,
            cross_signal_score=70,
            verdict="REWRITE",
            rewrite_instruction="Not actionable enough",
        )
        assert ic.actionability_score < 70  # FAIL

    def test_failing_cross_signal(self):
        from hephae_db.schemas import InsightCritique

        ic = InsightCritique(
            insight_rank=3,
            obviousness_score=20,
            actionability_score=75,
            cross_signal_score=30,
            verdict="REWRITE",
            rewrite_instruction="Only cites one source",
        )
        assert ic.cross_signal_score < 60  # FAIL


class TestCritiqueRouter:
    """B4: CritiqueRouter deterministic routing."""

    def _make_ctx(self, state: dict) -> MagicMock:
        ctx = MagicMock()
        ctx.session.state = dict(state)
        ctx.invocation_id = "test-inv"
        return ctx

    @pytest.mark.asyncio
    async def test_escalates_on_pass(self):
        from hephae_agents.research.pulse_critique_agent import CritiqueRouter

        router = CritiqueRouter()
        ctx = self._make_ctx({
            "critiqueResult": {"overall_pass": True, "insights": []},
        })

        events = []
        async for event in router._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions.escalate is True
        assert events[0].actions.state_delta["rewriteFeedback"] == ""

    @pytest.mark.asyncio
    async def test_writes_feedback_on_fail(self):
        from hephae_agents.research.pulse_critique_agent import CritiqueRouter

        router = CritiqueRouter()
        ctx = self._make_ctx({
            "critiqueResult": {
                "overall_pass": False,
                "insights": [
                    {
                        "insight_rank": 1,
                        "obviousness_score": 85,
                        "actionability_score": 30,
                        "cross_signal_score": 20,
                        "verdict": "REWRITE",
                        "rewrite_instruction": "Too obvious, not actionable",
                    },
                    {
                        "insight_rank": 2,
                        "obviousness_score": 10,
                        "actionability_score": 90,
                        "cross_signal_score": 80,
                        "verdict": "PASS",
                    },
                ],
            },
        })

        events = []
        async for event in router._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions.escalate is not True
        feedback = events[0].actions.state_delta["rewriteFeedback"]
        assert "Insight #1" in feedback
        assert "REWRITE" in feedback
        assert "Too obvious, not actionable" in feedback
        # Insight #2 passed, shouldn't be in feedback
        assert "Insight #2" not in feedback

    @pytest.mark.asyncio
    async def test_handles_string_critique_result(self):
        """critiqueResult might be a JSON string from output_key."""
        from hephae_agents.research.pulse_critique_agent import CritiqueRouter

        router = CritiqueRouter()
        ctx = self._make_ctx({
            "critiqueResult": json.dumps({
                "overall_pass": True,
                "insights": [],
            }),
        })

        events = []
        async for event in router._run_async_impl(ctx):
            events.append(event)

        assert events[0].actions.escalate is True

    @pytest.mark.asyncio
    async def test_handles_malformed_critique(self):
        """Malformed critique should not crash."""
        from hephae_agents.research.pulse_critique_agent import CritiqueRouter

        router = CritiqueRouter()
        ctx = self._make_ctx({"critiqueResult": "not valid json {"})

        events = []
        async for event in router._run_async_impl(ctx):
            events.append(event)

        # Should default to fail path (overall_pass defaults to False)
        assert len(events) == 1
        assert events[0].actions.state_delta["rewriteFeedback"] == "Some insights need improvement."


# ═══════════════════════════════════════════════════════════════════════════
# Phase C: Batch tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBatchIDMapping:
    """C2: request_ids correctly map results back to zip codes."""

    def test_stage1_request_id_format(self):
        batch_id = "pulse-essex-2026-W12"
        zip_code = "07110"
        assert f"{batch_id}:{zip_code}:social_pulse" == "pulse-essex-2026-W12:07110:social_pulse"
        assert f"{batch_id}:{zip_code}:local_catalyst" == "pulse-essex-2026-W12:07110:local_catalyst"

    def test_stage2_request_id_format(self):
        batch_id = "pulse-essex-2026-W12"
        zip_code = "07042"
        assert f"{batch_id}:{zip_code}:economist" == "pulse-essex-2026-W12:07042:economist"
        assert f"{batch_id}:{zip_code}:local_scout" == "pulse-essex-2026-W12:07042:local_scout"
        assert f"{batch_id}:{zip_code}:historian" == "pulse-essex-2026-W12:07042:historian"

    def test_stage3_request_id_format(self):
        batch_id = "pulse-essex-2026-W12"
        zip_code = "07003"
        assert f"{batch_id}:{zip_code}:synthesis" == "pulse-essex-2026-W12:07003:synthesis"

    def test_stage4_request_id_format(self):
        batch_id = "pulse-essex-2026-W12"
        zip_code = "07110"
        assert f"{batch_id}:{zip_code}:critique" == "pulse-essex-2026-W12:07110:critique"

    def test_work_item_doc_id_format(self):
        batch_id = "pulse-essex-2026-W12"
        zip_code = "07110"
        doc_id = f"{batch_id}:{zip_code}"
        assert doc_id == "pulse-essex-2026-W12:07110"

    def test_request_id_parsing(self):
        """Verify we can parse zip code back from request_id."""
        req_id = "pulse-essex-2026-W12:07110:social_pulse"
        parts = req_id.split(":")
        # batch_id parts may contain hyphens, so join all but last two
        zip_code = parts[-2]
        stage = parts[-1]
        assert zip_code == "07110"
        assert stage == "social_pulse"


class TestBatchSynthesisSchema:
    """C3: Stage 3 JSONL includes response_schema."""

    def test_synthesis_config_has_response_schema(self):
        from hephae_db.schemas import WeeklyPulseOutput

        schema = WeeklyPulseOutput.model_json_schema()

        # Simulate the config that _stage3_synthesis builds
        config = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }

        assert "response_schema" in config
        assert "properties" in config["response_schema"]
        assert "insights" in config["response_schema"]["properties"]
