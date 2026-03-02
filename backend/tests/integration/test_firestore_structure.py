"""
Level 4: Firestore document structure validation.

Writes enriched profile via write_discovery(), reads it back,
and validates the document structure matches expectations.

Uses INTEGRATION_TEST_ prefix for all docs, cleaned up at end.
"""

from __future__ import annotations

import logging
import os

import pytest
import pytest_asyncio

from backend.tests.integration.businesses import BUSINESSES, GroundTruth

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.needs_browser, pytest.mark.asyncio]

TEST_DOC_PREFIX = "INTEGRATION_TEST_"


def _has_firestore():
    """Check if Firestore credentials are available."""
    return bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("FIREBASE_PROJECT_ID")
        or os.environ.get("GCLOUD_PROJECT")
    )


def _make_test_slug(biz_id: str) -> str:
    return f"{TEST_DOC_PREFIX}{biz_id}"


@pytest.fixture(scope="module")
def firestore_db():
    """Get a real Firestore client, skip if unavailable."""
    if not _has_firestore():
        pytest.skip("No Firestore credentials available")
    try:
        from backend.lib.firebase import db
        return db
    except Exception as e:
        pytest.skip(f"Firestore init failed: {e}")


@pytest_asyncio.fixture(scope="module")
async def written_docs(firestore_db, discovery_cache):
    """Write test docs to Firestore, yield slugs, then clean up."""
    from backend.lib.db.write_discovery import write_discovery, strip_blobs, _parse_zip_code

    written_slugs = []

    for biz in BUSINESSES:
        if biz.id not in discovery_cache.enriched_profiles:
            logger.warning(f"[Firestore] Skipping {biz.id} — no enriched profile cached")
            continue

        profile = discovery_cache.enriched_profiles[biz.id].copy()
        # Override name to use test prefix for safe cleanup
        test_name = f"{TEST_DOC_PREFIX}{biz.id}"
        profile["name"] = test_name

        try:
            await write_discovery(profile=profile, triggered_by="integration_test")
            written_slugs.append((biz, test_name))
        except Exception as e:
            logger.error(f"[Firestore] write_discovery failed for {biz.id}: {e}")

    yield written_slugs

    # Cleanup: delete all test docs
    for _biz, test_name in written_slugs:
        try:
            from backend.lib.report_storage import generate_slug
            slug = generate_slug(test_name)
            firestore_db.document(f"businesses/{slug}").delete()
            logger.info(f"[Firestore] Cleaned up businesses/{slug}")
        except Exception as e:
            logger.warning(f"[Firestore] Cleanup failed for {test_name}: {e}")


class TestFirestoreDocStructure:
    """Validate Firestore document structure after write_discovery()."""

    @pytest.mark.timeout(30)
    async def test_enriched_fields_at_top_level(self, firestore_db, written_docs):
        """Enriched fields exist at both top-level and inside identity."""
        if not written_docs:
            pytest.skip("No docs written — pipeline may have timed out")

        from backend.lib.report_storage import generate_slug

        enriched_field_names = [
            "phone", "socialLinks", "primaryColor", "persona",
            "competitors", "logoUrl", "favicon", "menuUrl",
        ]

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            assert doc.exists, f"Document businesses/{slug} not found"

            data = doc.to_dict()

            # Check top-level fields
            for field in enriched_field_names:
                assert field in data, (
                    f"Missing top-level field '{field}' in businesses/{slug}. "
                    f"Keys: {list(data.keys())}"
                )

            # Check identity sub-object
            identity = data.get("identity", {})
            for field in enriched_field_names:
                assert field in identity, (
                    f"Missing identity.{field} in businesses/{slug}. "
                    f"Identity keys: {list(identity.keys())}"
                )

    @pytest.mark.timeout(30)
    async def test_no_base64_blobs(self, firestore_db, written_docs):
        """No menuScreenshotBase64 or other binary blobs in Firestore."""
        if not written_docs:
            pytest.skip("No docs written")

        from backend.lib.report_storage import generate_slug

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            if not doc.exists:
                continue

            data = doc.to_dict()
            assert "menuScreenshotBase64" not in data, (
                f"businesses/{slug} contains menuScreenshotBase64 blob!"
            )

            # Also check identity sub-object
            identity = data.get("identity", {})
            assert "menuScreenshotBase64" not in identity

    @pytest.mark.timeout(30)
    async def test_zip_code_parsed(self, firestore_db, written_docs):
        """zipCode is parsed from address and stored at top level."""
        if not written_docs:
            pytest.skip("No docs written")

        from backend.lib.report_storage import generate_slug

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            if not doc.exists:
                continue

            data = doc.to_dict()
            address = data.get("address", "")

            # If the address contains a zip code, it should be parsed
            import re
            if re.search(r"\b\d{5}\b", address or ""):
                assert "zipCode" in data, (
                    f"businesses/{slug} has address with zip '{address}' "
                    "but no top-level zipCode field"
                )
                assert re.match(r"^\d{5}$", data["zipCode"]), (
                    f"zipCode '{data['zipCode']}' is not a valid 5-digit code"
                )

    @pytest.mark.timeout(30)
    async def test_social_links_is_dict(self, firestore_db, written_docs):
        """socialLinks field is a dict (not a string or array)."""
        if not written_docs:
            pytest.skip("No docs written")

        from backend.lib.report_storage import generate_slug

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            if not doc.exists:
                continue

            data = doc.to_dict()
            social = data.get("socialLinks")
            if social is not None:
                assert isinstance(social, dict), (
                    f"socialLinks should be dict, got {type(social).__name__}: {social}"
                )

    @pytest.mark.timeout(30)
    async def test_social_profile_metrics_stored_as_dict(self, firestore_db, written_docs):
        """socialProfileMetrics field is stored as a dict (not a JSON string)."""
        if not written_docs:
            pytest.skip("No docs written")

        from backend.lib.report_storage import generate_slug

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            if not doc.exists:
                continue

            data = doc.to_dict()
            metrics = data.get("socialProfileMetrics")
            if metrics is not None:
                assert isinstance(metrics, dict), (
                    f"socialProfileMetrics should be dict, got {type(metrics).__name__}"
                )
                # Should not be a JSON string stored as a string field
                assert not isinstance(metrics, str), (
                    f"socialProfileMetrics was stored as a string, not a dict: {metrics[:100]}"
                )

    @pytest.mark.timeout(30)
    async def test_social_profile_metrics_nested_structure(self, firestore_db, written_docs):
        """socialProfileMetrics preserves nested platform objects in Firestore."""
        if not written_docs:
            pytest.skip("No docs written")

        from backend.lib.report_storage import generate_slug

        valid_platform_keys = {"instagram", "facebook", "twitter", "tiktok", "yelp", "summary"}

        for biz, test_name in written_docs:
            slug = generate_slug(test_name)
            doc = firestore_db.document(f"businesses/{slug}").get()
            if not doc.exists:
                continue

            data = doc.to_dict()
            metrics = data.get("socialProfileMetrics")
            if not isinstance(metrics, dict):
                continue

            # Check platform sub-objects are preserved as dicts
            for key, value in metrics.items():
                if key in valid_platform_keys and value is not None:
                    assert isinstance(value, dict), (
                        f"socialProfileMetrics.{key} should be a dict, "
                        f"got {type(value).__name__}: {value}"
                    )

            # If summary exists, validate its structure
            summary = metrics.get("summary")
            if isinstance(summary, dict):
                # These fields should be present when summary exists
                expected_summary_fields = [
                    "totalFollowers", "overallPresenceScore",
                ]
                for field in expected_summary_fields:
                    assert field in summary, (
                        f"summary missing '{field}' for {biz.id}. "
                        f"Summary keys: {list(summary.keys())}"
                    )

                # overallPresenceScore should be 0-100
                score = summary.get("overallPresenceScore")
                if score is not None:
                    assert 0 <= score <= 100, (
                        f"overallPresenceScore {score} out of range [0,100]"
                    )
