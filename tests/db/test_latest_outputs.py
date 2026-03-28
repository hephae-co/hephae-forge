"""
Unit tests for hephae_db.context.latest_outputs — shared Firestore latestOutputs fetcher.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.integration


SAMPLE_BUSINESS_DOC = {
    "name": "Bosphorus Kitchen",
    "socialLinks": {
        "instagram": "https://instagram.com/bosphorus_nj",
        "facebook": "https://facebook.com/BosphorusKitchen",
        "twitter": "https://twitter.com/bosphorus_nj",
    },
    "latestOutputs": {
        "margin_surgeon": {
            "score": 62,
            "summary": "$847/mo profit leakage",
            "reportUrl": "https://storage.googleapis.com/everything-hephae/bosphorus-kitchen/margin-1234.html",
            "totalLeakage": 847,
            "menu_item_count": 12,
        },
        "seo_auditor": {
            "score": 75,
            "summary": "Good technical SEO, weak content",
            "reportUrl": "https://storage.googleapis.com/everything-hephae/bosphorus-kitchen/seo-5678.html",
            "seo_technical_score": 85,
            "seo_content_score": 55,
        },
    },
}


class TestFetchLatestOutputs:
    """Test fetch_latest_outputs() function."""

    def test_returns_outputs_for_valid_business(self):
        with patch("hephae_db.context.latest_outputs.read_business", return_value=SAMPLE_BUSINESS_DOC):
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            result = fetch_latest_outputs("Bosphorus Kitchen")

        assert "outputs" in result
        assert "socialLinks" in result
        assert "margin_surgeon" in result["outputs"]
        assert "seo_auditor" in result["outputs"]
        assert result["outputs"]["margin_surgeon"]["score"] == 62

    def test_returns_social_links(self):
        with patch("hephae_db.context.latest_outputs.read_business", return_value=SAMPLE_BUSINESS_DOC):
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            result = fetch_latest_outputs("Bosphorus Kitchen")

        assert "instagram" in result["socialLinks"]
        assert "twitter" in result["socialLinks"]

    def test_returns_empty_for_missing_business(self):
        with patch("hephae_db.context.latest_outputs.read_business", return_value=None):
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            result = fetch_latest_outputs("Nonexistent Cafe")

        assert result["outputs"] == {}
        assert result["socialLinks"] == {}

    def test_returns_empty_for_empty_name(self):
        from hephae_db.context.latest_outputs import fetch_latest_outputs

        result = fetch_latest_outputs("")
        assert result["outputs"] == {}

    def test_returns_empty_for_business_without_outputs(self):
        doc_no_outputs = {"name": "New Biz"}
        with patch("hephae_db.context.latest_outputs.read_business", return_value=doc_no_outputs):
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            result = fetch_latest_outputs("New Biz")

        assert result["outputs"] == {}

    def test_handles_exception_gracefully(self):
        with patch(
            "hephae_db.context.latest_outputs.read_business",
            side_effect=Exception("Firestore down"),
        ):
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            result = fetch_latest_outputs("Some Biz")

        assert result["outputs"] == {}

    def test_uses_slug_for_lookup(self):
        with patch("hephae_db.context.latest_outputs.read_business", return_value=None) as mock_read:
            from hephae_db.context.latest_outputs import fetch_latest_outputs

            fetch_latest_outputs("Café L'Artiste")

        # generate_slug("Café L'Artiste") -> "caf-lartiste"
        mock_read.assert_called_once()
        slug_arg = mock_read.call_args[0][0]
        assert " " not in slug_arg
        assert slug_arg == slug_arg.lower()
