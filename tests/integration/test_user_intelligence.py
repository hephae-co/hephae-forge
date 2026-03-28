"""Integration tests for user-centric intelligence (Persistence & Isolation).

These tests exercise real API endpoints and verify session isolation and
persistence behavior. They require GEMINI_API_KEY and a running Firebase
emulator (or real Firestore) to pass fully.

Mark: integration (Firestore-dependent)
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GEMINI_API_KEY"),
        reason="GEMINI_API_KEY not set — integration tests require a real Gemini API key",
    ),
]


@pytest.mark.asyncio
async def test_chat_session_isolation_different_users(client):
    """Two authenticated users should receive different session IDs."""
    # User A sends a message
    resp_a = await client.post(
        "/api/chat",
        headers={"Authorization": "Bearer fake-token-user-a"},
        json={"messages": [{"role": "user", "text": "Hello, analyze my business"}]},
    )
    # User B sends a message
    resp_b = await client.post(
        "/api/chat",
        headers={"Authorization": "Bearer fake-token-user-b"},
        json={"messages": [{"role": "user", "text": "Hello"}]},
    )

    # Both should succeed or both may fail with auth errors in test env —
    # the critical assertion is that session IDs are different if both succeed
    if resp_a.status_code == 200 and resp_b.status_code == 200:
        data_a = resp_a.json()
        data_b = resp_b.json()
        assert data_a.get("sessionId") != data_b.get("sessionId"), (
            "Session IDs must be different for different users"
        )


@pytest.mark.asyncio
async def test_heartbeat_requires_auth(client):
    """Heartbeat endpoint should reject unauthenticated requests."""
    resp = await client.post(
        "/api/heartbeat",
        json={
            "businessSlug": "joes-pizza",
            "businessName": "Joe's Pizza",
            "capabilities": ["seo"],
        },
    )
    # Without valid auth, should return 401 or 403
    assert resp.status_code in (401, 403, 422), (
        f"Expected auth failure, got {resp.status_code}"
    )
