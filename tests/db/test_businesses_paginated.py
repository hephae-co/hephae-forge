"""Unit tests for get_businesses_paginated — pagination and filtering logic."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration


def _make_doc(name: str, zip_code: str = "07110", email: str = "", category: str = "",
              status: str = "scanned") -> MagicMock:
    doc = MagicMock()
    doc.id = name.lower().replace(" ", "-")
    data = {
        "name": name,
        "zipCode": zip_code,
        "discoveryStatus": status,
    }
    if email:
        data["email"] = email
    if category:
        data["category"] = category
    doc.to_dict.return_value = data
    return doc


def _make_db(docs: list) -> MagicMock:
    """Build a mock Firestore db that returns the given docs from a collection query."""
    mock_db = MagicMock()
    query = MagicMock()
    query.where.return_value = query
    query.get.return_value = docs
    mock_db.collection.return_value.where.return_value = query
    return mock_db


class TestGetBusinessesPaginated:
    """Tests for _get_businesses_paginated_sync (tested via asyncio.to_thread mock)."""

    def _run(self, zip_code="07110", page=1, page_size=25,
             category=None, status=None, has_email=None, docs=None):
        from hephae_db.firestore.businesses import _get_businesses_paginated_sync
        docs = docs or []
        with patch("hephae_db.firestore.businesses.get_db", return_value=_make_db(docs)):
            return _get_businesses_paginated_sync(zip_code, page, page_size, category, status, has_email)

    def test_returns_paginated_shape(self):
        docs = [_make_doc("Alpha"), _make_doc("Beta")]
        result = self._run(docs=docs)
        assert "businesses" in result
        assert "total" in result
        assert "page" in result
        assert "pages" in result
        assert "pageSize" in result

    def test_total_reflects_all_matches(self):
        docs = [_make_doc(f"Biz {i}") for i in range(10)]
        result = self._run(page_size=3, docs=docs)
        assert result["total"] == 10

    def test_page_1_returns_first_slice(self):
        docs = [_make_doc(f"Alpha {i:02}") for i in range(10)]
        result = self._run(page=1, page_size=3, docs=docs)
        assert len(result["businesses"]) == 3
        assert result["page"] == 1

    def test_page_2_returns_second_slice(self):
        docs = [_make_doc(f"Biz {i:02}") for i in range(10)]
        result = self._run(page=2, page_size=3, docs=docs)
        assert len(result["businesses"]) == 3
        assert result["page"] == 2
        # businesses are sorted by name, so page 2 is items [3,4,5]
        assert result["businesses"][0]["name"] != result["businesses"][1]["name"]

    def test_last_page_returns_remainder(self):
        docs = [_make_doc(f"Biz {i:02}") for i in range(10)]
        result = self._run(page=4, page_size=3, docs=docs)
        assert len(result["businesses"]) == 1  # 10 % 3 = 1

    def test_pages_count_correct(self):
        docs = [_make_doc(f"Biz {i}") for i in range(7)]
        result = self._run(page_size=3, docs=docs)
        assert result["pages"] == 3  # ceil(7/3)

    def test_empty_returns_valid_shape(self):
        result = self._run(docs=[])
        assert result["businesses"] == []
        assert result["total"] == 0
        assert result["pages"] == 1

    def test_sorted_by_name_ascending(self):
        docs = [_make_doc("Zaza"), _make_doc("Alpha"), _make_doc("Mango")]
        result = self._run(docs=docs)
        names = [b["name"] for b in result["businesses"]]
        assert names == sorted(names, key=str.lower)

    def test_has_email_true_filters_businesses(self):
        docs = [
            _make_doc("With Email", email="a@b.com"),
            _make_doc("No Email"),
        ]
        result = self._run(has_email=True, docs=docs)
        assert result["total"] == 1
        assert result["businesses"][0]["email"] == "a@b.com"

    def test_has_email_false_filters_businesses(self):
        docs = [
            _make_doc("With Email", email="a@b.com"),
            _make_doc("No Email"),
        ]
        result = self._run(has_email=False, docs=docs)
        assert result["total"] == 1
        assert "email" not in result["businesses"][0]

    def test_has_email_none_returns_all(self):
        docs = [_make_doc("A", email="x@y.com"), _make_doc("B")]
        result = self._run(has_email=None, docs=docs)
        assert result["total"] == 2

    def test_identity_email_counts_for_has_email(self):
        """Email in identity field (not top-level) should count."""
        doc = MagicMock()
        doc.id = "biz-with-identity-email"
        doc.to_dict.return_value = {
            "name": "Identity Email Biz",
            "zipCode": "07110",
            "identity": {"email": "owner@biz.com"},
        }
        result = self._run(has_email=True, docs=[doc])
        assert result["total"] == 1

    def test_firestore_error_returns_empty_shape(self):
        mock_db = MagicMock()
        mock_db.collection.side_effect = Exception("Firestore down")
        from hephae_db.firestore.businesses import _get_businesses_paginated_sync
        with patch("hephae_db.firestore.businesses.get_db", return_value=mock_db):
            result = _get_businesses_paginated_sync("07110")
        assert result["businesses"] == []
        assert result["total"] == 0


class TestGetBusinessesPaginatedAsync:
    """Test the async wrapper."""

    @pytest.mark.asyncio
    async def test_async_wrapper_returns_same_as_sync(self):
        docs = [_make_doc("Pizza Palace", email="info@pizza.com")]
        mock_db = _make_db(docs)
        with patch("hephae_db.firestore.businesses.get_db", return_value=mock_db):
            from hephae_db.firestore.businesses import get_businesses_paginated
            result = await get_businesses_paginated("07110", page=1, page_size=25)
        assert result["total"] == 1
        assert result["businesses"][0]["name"] == "Pizza Palace"
