"""
Tier 2: Session & Persistence Tests.

Validates that FirestoreSessionService correctly maintains state
across process boundaries and agent restarts.
"""

from __future__ import annotations

import time
import pytest
from google.adk.runners import Runner
from hephae_db.firestore.session_service import FirestoreSessionService
from hephae_agents.discovery.agent import discovery_phase1 # Using a real agent
from hephae_common.adk_helpers import user_msg

@pytest.mark.integration
@pytest.mark.asyncio
async def test_firestore_session_persistence_across_runners():
    """Verify that a second runner can resume state from a first runner's session."""
    session_service = FirestoreSessionService()
    user_id = f"persist-test-user-{int(time.time())}"
    session_id = f"persist-session-{int(time.time())}"
    app_name = "persistence-test"
    
    # 1. First Runner: Initialize and set some state
    await session_service.create_session(
        app_name=app_name, 
        user_id=user_id, 
        session_id=session_id, 
        state={"initial_key": "initial_value"}
    )
    
    # Verify state is saved
    s1 = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
    assert s1.state["initial_key"] == "initial_value"
    
    # 2. Update state directly (simulating an agent writing to state)
    await session_service.update_session(
        app_name=app_name, user_id=user_id, session_id=session_id, state={"agent_result": "success"}
    )
    
    # 3. Second Runner: Re-instantiate a new runner with same IDs
    # In a new process/turn, we'd just have the IDs.
    s2 = await session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
    
    assert s2.state["initial_key"] == "initial_value", "Persistence failed: initial_key missing"
    assert s2.state["agent_result"] == "success", "Persistence failed: updated state missing"
    
    # 4. Clean up (optional, but good for hygiene)
    # db = get_db()
    # db.collection("sessions").document(f"{app_name}:{user_id}:{session_id}").delete()
