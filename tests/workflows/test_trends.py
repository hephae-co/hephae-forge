import pytest
import json
from unittest.mock import patch, MagicMock

from hephae_api.config import AgentModels

try:
    from hephae_api.agents.trends_researcher import (
        execute_trends_bigquery,
        trends_query_generator,
        trends_query_executor,
        trends_research_pipeline,
        _clean_sql,
    )
except ImportError:
    pytest.skip("Module removed during refactor", allow_module_level=True)


# ---------------------------------------------------------------------------
# SQL cleaning utility tests
# ---------------------------------------------------------------------------

class TestCleanSql:
    def test_removes_markdown_fences(self):
        raw = "```sql\nSELECT * FROM t\n```"
        assert "```" not in _clean_sql(raw)
        assert "SELECT * FROM t" in _clean_sql(raw)

    def test_removes_escaped_newlines(self):
        raw = "SELECT *\\nFROM t"
        cleaned = _clean_sql(raw)
        assert "\\n" not in cleaned
        assert "SELECT" in cleaned

    def test_removes_backslashes(self):
        raw = "SELECT \\'term\\' FROM t"
        cleaned = _clean_sql(raw)
        assert "\\" not in cleaned

    def test_strips_whitespace(self):
        raw = "   SELECT 1   "
        assert _clean_sql(raw) == "SELECT 1"


# ---------------------------------------------------------------------------
# Agent initialization tests
# ---------------------------------------------------------------------------

class TestAgentInitialization:
    def test_trends_query_generator_config(self):
        assert trends_query_generator.name == "trends_query_generator"
        assert trends_query_generator.model == AgentModels.ENHANCED_MODEL
        assert trends_query_generator.output_key == "generated_trends_sql"
        assert "top_rising_terms" in trends_query_generator.instruction
        assert "top_terms" in trends_query_generator.instruction
        assert "{research_findings}" in trends_query_generator.instruction

    def test_trends_query_executor_config(self):
        assert trends_query_executor.name == "trends_query_executor"
        assert trends_query_executor.model == AgentModels.PRIMARY_MODEL
        assert trends_query_executor.output_key == "trends_analysis"
        assert execute_trends_bigquery in trends_query_executor.tools

    def test_pipeline_structure(self):
        agents = trends_research_pipeline.sub_agents
        assert len(agents) == 2
        assert agents[0].name == "trends_query_generator"
        assert agents[1].name == "trends_query_executor"

    def test_generator_instruction_has_table_schema(self):
        instruction = trends_query_generator.instruction
        assert "bigquery-public-data.google_trends.top_terms" in instruction
        assert "bigquery-public-data.google_trends.top_rising_terms" in instruction
        assert "dma_name" in instruction
        assert "refresh_date" in instruction

    def test_generator_instruction_requests_two_queries(self):
        instruction = trends_query_generator.instruction
        assert "---SEPARATOR---" in instruction
        assert "Query 1" in instruction
        assert "Query 2" in instruction


# ---------------------------------------------------------------------------
# BigQuery tool tests
# ---------------------------------------------------------------------------

class TestExecuteTrendsBigquery:
    @patch("hephae_api.agents.trends_researcher.bigquery.Client")
    def test_successful_query(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_row1 = {"term": "pizza delivery", "percent_gain": 500, "rank": 1}
        mock_row2 = {"term": "taco tuesday", "percent_gain": 300, "rank": 2}

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([mock_row1, mock_row2])
        mock_client.query.return_value.result.return_value = mock_result

        result = execute_trends_bigquery("SELECT term FROM trends")

        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["term"] == "pizza delivery"
        assert parsed[1]["percent_gain"] == 300
        mock_client.query.assert_called_once()

    @patch("hephae_api.agents.trends_researcher.bigquery.Client")
    def test_empty_results(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_client.query.return_value.result.return_value = mock_result

        result = execute_trends_bigquery("SELECT term FROM trends WHERE 1=0")
        assert result == "Query returned no results."

    @patch("hephae_api.agents.trends_researcher.bigquery.Client")
    def test_bigquery_error_returns_error_string(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.query.side_effect = Exception("Access denied: bigquery-public-data")

        result = execute_trends_bigquery("SELECT * FROM nonexistent")
        assert "Error executing BigQuery query" in result
        assert "Access denied" in result

    @patch("hephae_api.agents.trends_researcher.bigquery.Client")
    def test_cleans_sql_before_execution(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_client.query.return_value.result.return_value = mock_result

        execute_trends_bigquery("```sql\nSELECT 1\n```")

        called_sql = mock_client.query.call_args[0][0]
        assert "```" not in called_sql
        assert "SELECT 1" in called_sql

    @patch("hephae_api.agents.trends_researcher.bigquery.Client")
    def test_handles_datetime_serialization(self, mock_client_cls):
        from datetime import date

        mock_client = mock_client_cls.return_value
        mock_row = {"term": "trending", "week": date(2026, 2, 23)}
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([mock_row])
        mock_client.query.return_value.result.return_value = mock_result

        result = execute_trends_bigquery("SELECT * FROM trends")
        parsed = json.loads(result)
        assert parsed[0]["term"] == "trending"
        assert "2026" in parsed[0]["week"]
