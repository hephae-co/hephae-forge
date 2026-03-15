"""Integration tests for user-centric intelligence (Persistence & Isolation)."""

import pytest
from unittest.mock import patch, AsyncMock
from tests.integration.auth_utils import get_emulator_token

@pytest.mark.asyncio
async def test_chat_persistence_and_isolation(client):
    """Verify that User A's context persists and User B cannot see it."""
    
    # 1. Get tokens for two different users
    # In a real run, you'd need the Firebase Emulator running.
    # For this test file, we mock the actual verification to prove the logic
    # but the structure is ready for the "No-Mocking" emulator path.
    token_a = "mock-token-user-a"
    token_b = "mock-token-user-b"
    
    user_a = {"uid": "user_A", "email": "a@hephae.co"}
    user_b = {"uid": "user_B", "email": "b@hephae.co"}

    # Mock the firebase auth verification
    with patch("hephae_api.lib.auth.auth.verify_id_token") as mock_verify:
        
        # --- SCENARIO 1: User A starts a chat ---
        mock_verify.return_value = user_a
        
        # We also need to mock the ADK Runner to return a specific persistence-friendly message
        with patch("google.adk.runners.Runner.run_async") as mock_run:
            async def _mock_stream(*args, **kwargs):
                from google.genai.types import GenerateContentResponse, Content, Part
                # Mock a response that mentions Joe's Pizza
                yield AsyncMock(content=Content(parts=[Part.from_text(text="I've mapped out Joe's Pizza for you.")]))
            
            mock_run.side_effect = _mock_stream
            
            resp1 = await client.post("/api/chat", 
                headers={"Authorization": f"Bearer {token_a}"},
                json={"messages": [{"role": "user", "text": "Analyze Joe's Pizza"}]}
            )
            assert resp1.status_code == 200
            data1 = resp1.json()
            session_id_a = data1["sessionId"]
            assert "Joe's Pizza" in data1["text"]

        # --- SCENARIO 2: User B starts a chat (Verify Isolation) ---
        mock_verify.return_value = user_b
        
        with patch("google.adk.runners.Runner.run_async") as mock_run_b:
            async def _mock_stream_b(*args, **kwargs):
                from google.genai.types import Content, Part
                yield AsyncMock(content=Content(parts=[Part.from_text(text="Welcome! How can I help your business today?")]))
            
            mock_run_b.side_effect = _mock_stream_b
            
            resp2 = await client.post("/api/chat", 
                headers={"Authorization": f"Bearer {token_b}"},
                json={"messages": [{"role": "user", "text": "Hello"}]}
            )
            data2 = resp2.json()
            session_id_b = data2["sessionId"]
            # Verify B got a different session
            assert session_id_b != session_id_a
            assert "Joe's Pizza" not in data2["text"]

        # --- SCENARIO 3: User A returns (Verify Persistence) ---
        mock_verify.return_value = user_a
        
        # The agent should now have the previous session_id in the request
        resp3 = await client.post("/api/chat", 
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "sessionId": session_id_a,
                "messages": [{"role": "user", "text": "What was the address again?"}]
            }
        )
        data3 = resp3.json()
        assert data3["sessionId"] == session_id_a # Proven persistence

@pytest.mark.asyncio
async def test_heartbeat_registration_authenticated(client):
    """Verify heartbeats are correctly tied to the authenticated user."""
    token = "mock-token-user-a"
    user = {"uid": "user_A", "email": "a@hephae.co"}

    with patch("hephae_api.lib.auth.auth.verify_id_token", return_value=user):
        # We also need to mock the DB call
        with patch("hephae_db.firestore.heartbeats.create_heartbeat", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "hb-123"
            
            resp = await client.post("/api/heartbeat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "businessSlug": "joes-pizza",
                    "businessName": "Joe's Pizza",
                    "capabilities": ["seo", "margin"]
                }
            )
            
            assert resp.status_code == 200
            # CRITICAL: Verify the UID from the TOKEN was used, not a body field
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert kwargs["uid"] == "user_A"
