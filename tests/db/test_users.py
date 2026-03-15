"""Unit tests for hephae_db.firestore.users — user CRUD and business linking."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helper: build a mock Firestore doc
# ---------------------------------------------------------------------------

def _mock_doc(exists: bool, data: dict | None = None):
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def _mock_db():
    """Return a mock Firestore client with chainable collection/document/get."""
    db = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Tests: get_or_create_user
# ---------------------------------------------------------------------------

class TestGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_creates_new_user_on_first_login(self):
        db = _mock_db()
        doc_ref = MagicMock()
        db.collection.return_value.document.return_value = doc_ref
        doc_ref.get.return_value = _mock_doc(exists=False)

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_or_create_user

            result = await get_or_create_user(
                uid="new-user-1",
                email="new@example.com",
                display_name="New User",
                photo_url="https://photo.url/pic.jpg",
            )

        # Should have called set() to create the doc
        doc_ref.set.assert_called_once()
        created_data = doc_ref.set.call_args[0][0]
        assert created_data["email"] == "new@example.com"
        assert created_data["displayName"] == "New User"
        assert created_data["photoURL"] == "https://photo.url/pic.jpg"
        assert created_data["businesses"] == []
        assert "createdAt" in created_data
        assert "lastLoginAt" in created_data

        # Return value should include uid
        assert result["uid"] == "new-user-1"
        assert result["email"] == "new@example.com"

    @pytest.mark.asyncio
    async def test_updates_last_login_for_existing_user(self):
        db = _mock_db()
        doc_ref = MagicMock()
        db.collection.return_value.document.return_value = doc_ref
        existing_data = {
            "email": "existing@example.com",
            "displayName": "Existing User",
            "businesses": ["joes-pizza"],
            "createdAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "lastLoginAt": datetime(2026, 3, 1, tzinfo=timezone.utc),
        }
        doc_ref.get.return_value = _mock_doc(exists=True, data=existing_data)

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_or_create_user

            result = await get_or_create_user(uid="existing-user")

        # Should update lastLoginAt, NOT call set()
        doc_ref.update.assert_called_once()
        update_args = doc_ref.update.call_args[0][0]
        assert "lastLoginAt" in update_args
        doc_ref.set.assert_not_called()

        # Return value should include uid and existing businesses
        assert result["uid"] == "existing-user"
        assert result["businesses"] == ["joes-pizza"]

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self):
        db = _mock_db()
        doc_ref = MagicMock()
        db.collection.return_value.document.return_value = doc_ref
        doc_ref.get.return_value = _mock_doc(exists=False)

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_or_create_user

            result = await get_or_create_user(uid="minimal-user")

        created_data = doc_ref.set.call_args[0][0]
        assert created_data["email"] is None
        assert created_data["displayName"] is None
        assert created_data["photoURL"] is None


# ---------------------------------------------------------------------------
# Tests: get_user
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_returns_user_with_uid(self):
        db = _mock_db()
        db.collection.return_value.document.return_value.get.return_value = _mock_doc(
            exists=True, data={"email": "test@test.com", "businesses": ["slug-1"]}
        )

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_user

            result = get_user("uid-123")

        assert result["uid"] == "uid-123"
        assert result["email"] == "test@test.com"

    def test_returns_none_when_not_found(self):
        db = _mock_db()
        db.collection.return_value.document.return_value.get.return_value = _mock_doc(exists=False)

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_user

            result = get_user("nonexistent")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: add_business_to_user
# ---------------------------------------------------------------------------

class TestAddBusinessToUser:
    def test_adds_business_slug_with_array_union(self):
        db = _mock_db()
        doc_ref = MagicMock()
        db.collection.return_value.document.return_value = doc_ref

        with (
            patch("hephae_db.firestore.users.get_db", return_value=db),
            patch("google.cloud.firestore_v1.ArrayUnion") as mock_union,
        ):
            from hephae_db.firestore.users import add_business_to_user

            add_business_to_user("uid-123", "new-biz-slug")

        doc_ref.update.assert_called_once()
        mock_union.assert_called_once_with(["new-biz-slug"])


# ---------------------------------------------------------------------------
# Tests: get_user_businesses
# ---------------------------------------------------------------------------

class TestGetUserBusinesses:
    def test_returns_business_list(self):
        db = _mock_db()
        db.collection.return_value.document.return_value.get.return_value = _mock_doc(
            exists=True, data={"businesses": ["biz-1", "biz-2"]}
        )

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_user_businesses

            result = get_user_businesses("uid-123")

        assert result == ["biz-1", "biz-2"]

    def test_returns_empty_list_for_nonexistent_user(self):
        db = _mock_db()
        db.collection.return_value.document.return_value.get.return_value = _mock_doc(exists=False)

        with patch("hephae_db.firestore.users.get_db", return_value=db):
            from hephae_db.firestore.users import get_user_businesses

            result = get_user_businesses("ghost")

        assert result == []
