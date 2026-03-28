"""Functional tests for tech_intelligence Firestore module.

Tests call the real Firestore functions. They require ADC or
FIRESTORE_EMULATOR_HOST to be configured.

These are integration tests — they read real Firestore.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="No Firestore credentials — set GOOGLE_APPLICATION_CREDENTIALS or FIRESTORE_EMULATOR_HOST",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_tech_intelligence_returns_list():
    """list_tech_intelligence always returns a list."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence

    results = await list_tech_intelligence()
    assert isinstance(results, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tech_intelligence_nonexistent_returns_none():
    """Querying a non-existent vertical+week returns None."""
    from hephae_db.firestore.tech_intelligence import get_tech_intelligence

    result = await get_tech_intelligence("__nonexistent__", "9999-W99")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tech_intelligence_document_shape():
    """Each tech intelligence doc has vertical and weekOf fields."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence

    results = await list_tech_intelligence()
    for doc in results:
        assert "vertical" in doc, "Must have vertical"
        assert "weekOf" in doc, "Must have weekOf"
        assert isinstance(doc["vertical"], str)
        assert isinstance(doc["weekOf"], str)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_tech_intelligence_filter_by_vertical():
    """list_tech_intelligence filters by vertical correctly."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence

    results = await list_tech_intelligence(vertical="restaurant")
    assert isinstance(results, list)
    for doc in results:
        assert doc.get("vertical") == "restaurant"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_tech_intelligence_limit_respected():
    """list_tech_intelligence respects limit parameter."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence

    results = await list_tech_intelligence(limit=3)
    assert isinstance(results, list)
    assert len(results) <= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_doc_id_format_is_vertical_dash_week():
    """Tech intelligence doc id follows 'vertical-YYYY-Www' format."""
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence
    import re

    results = await list_tech_intelligence()
    for doc in results:
        doc_id = doc.get("id")
        if doc_id:
            # Should follow pattern: {vertical}-{YYYY}-W{ww}
            assert re.match(r"^.+-\d{4}-W\d{2}$", doc_id), (
                f"Doc id '{doc_id}' doesn't match expected format"
            )
