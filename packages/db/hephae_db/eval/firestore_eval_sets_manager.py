"""FirestoreEvalSetsManager — ADK EvalSetsManager backed by Firestore test_fixtures.

Converts human-curated fixtures (saved via the admin UI "Save as Test Case" /
"Save as Grounding" buttons) into ADK EvalSet / EvalCase objects for use with
AgentEvaluator.evaluate_eval_set().

Architecture notes:
  - This class is SYNCHRONOUS (the EvalSetsManager ABC does not use async).
    All Firestore reads are blocking calls wrapped in asyncio.get_event_loop()
    or called directly (since eval runners don't run inside an async context).
  - eval_set_id corresponds to agentKey (e.g. "seo_auditor").
  - Each fixture with fixtureType == "test_case" and agentKey == eval_set_id
    becomes one EvalCase.
  - The fixture's identity + agentOutput form the user_content + expected
    final_response of the Invocation.
  - Rubrics from rubrics.py are attached to each EvalCase.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from google.adk.evaluation.eval_case import EvalCase, Invocation
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_sets_manager import EvalSetsManager

from hephae_common.firebase import get_db
from hephae_db.eval.prompt_builders import build_eval_prompt, AGENT_EVAL_MODULE
from hephae_db.eval.rubrics import AGENT_RUBRICS

logger = logging.getLogger(__name__)

_APP_NAME = "hephae-hub"
_COLLECTION = "test_fixtures"


def _fixture_to_eval_case(fixture: dict[str, Any], agent_key: str) -> EvalCase | None:
    """Convert a Firestore fixture document into an ADK EvalCase.

    Returns None if the fixture lacks enough data to form a valid case.
    """
    identity = fixture.get("identity") or {}
    agent_output = fixture.get("agentOutput")

    if not identity.get("name"):
        logger.warning(
            f"[FirestoreEvalSetsManager] Skipping fixture {fixture.get('id')} — missing identity.name"
        )
        return None

    # Reconstruct the agent input prompt from identity
    prompt = build_eval_prompt(agent_key, identity, fixture)

    # Build expected final response from saved agent output
    import json
    expected_text: str
    if isinstance(agent_output, dict):
        expected_text = json.dumps(agent_output, ensure_ascii=False)
    elif isinstance(agent_output, str):
        expected_text = agent_output
    else:
        # No stored output — create a case without expected response
        # (rubric-only evaluation)
        expected_text = ""

    from google.genai.types import Content, Part

    user_content = Content(role="user", parts=[Part(text=prompt)])
    model_content = Content(role="model", parts=[Part(text=expected_text)]) if expected_text else None

    invocation = Invocation(
        invocation_id=fixture.get("id", f"fixture-{int(time.time() * 1000)}"),
        user_content=user_content,
        final_response=model_content,
    )

    rubrics = AGENT_RUBRICS.get(agent_key, [])

    eval_case = EvalCase(
        eval_id=fixture.get("id", f"case-{int(time.time() * 1000)}"),
        conversation=[invocation],
        rubrics=rubrics,
    )

    notes = fixture.get("notes", "")
    if notes:
        logger.debug(
            f"[FirestoreEvalSetsManager] EvalCase {eval_case.eval_id} notes: {notes}"
        )

    return eval_case


class FirestoreEvalSetsManager(EvalSetsManager):
    """Reads test_fixtures from Firestore and exposes them as ADK EvalSets.

    Usage:
        manager = FirestoreEvalSetsManager()
        eval_set = manager.get_eval_set("hephae-hub", "seo_auditor")
        await AgentEvaluator.evaluate_eval_set(
            agent_module="tests.evals.seo_auditor.agent",
            eval_set=eval_set,
            criteria={"rubric_based_final_response_quality_v1": 0.6},
            num_runs=1,
        )

    Limitations:
        - create_eval_set / add_eval_case / update_eval_case / delete_eval_case
          are not backed by Firestore writes — this manager is READ-ONLY.
          Use the admin UI or save_fixture_from_business() to add/remove cases.
        - list_eval_sets returns the known agentKeys, not Firestore collections.
    """

    def get_eval_set(self, app_name: str, eval_set_id: str) -> Optional[EvalSet]:
        """Load all test_case fixtures for the given agentKey as an EvalSet."""
        agent_key = eval_set_id
        db = get_db()

        try:
            query = (
                db.collection(_COLLECTION)
                .where("fixtureType", "==", "test_case")
                .where("agentKey", "==", agent_key)
                .order_by("savedAt", direction="DESCENDING")
                .limit(100)
            )
            docs = query.get()
        except Exception as e:
            logger.error(
                f"[FirestoreEvalSetsManager] Firestore query failed for agent_key={agent_key}: {e}"
            )
            return None

        eval_cases: list[EvalCase] = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            case = _fixture_to_eval_case(data, agent_key)
            if case:
                eval_cases.append(case)

        if not eval_cases:
            logger.info(
                f"[FirestoreEvalSetsManager] No test_case fixtures found for agent_key={agent_key}"
            )
            return None

        logger.info(
            f"[FirestoreEvalSetsManager] Loaded {len(eval_cases)} eval cases for {agent_key}"
        )

        return EvalSet(
            eval_set_id=eval_set_id,
            name=f"{agent_key} human-curated eval set",
            description=(
                f"Human-curated eval cases for {agent_key}. "
                "Saved from the admin BusinessBrowser via 'Save as Test Case'."
            ),
            eval_cases=eval_cases,
        )

    def create_eval_set(self, app_name: str, eval_set_id: str) -> EvalSet:
        """Not implemented — fixtures are created via the admin UI."""
        raise NotImplementedError(
            "FirestoreEvalSetsManager is read-only. "
            "Add fixtures via the admin UI BusinessBrowser."
        )

    def list_eval_sets(self, app_name: str) -> list[str]:
        """Return known agentKeys that have test_case fixtures."""
        return list(AGENT_EVAL_MODULE.keys())

    def get_eval_case(
        self, app_name: str, eval_set_id: str, eval_case_id: str
    ) -> Optional[EvalCase]:
        """Fetch a single eval case by fixture ID."""
        db = get_db()
        try:
            doc = db.collection(_COLLECTION).document(eval_case_id).get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            data["id"] = doc.id
            return _fixture_to_eval_case(data, eval_set_id)
        except Exception as e:
            logger.error(
                f"[FirestoreEvalSetsManager] Failed to fetch eval case {eval_case_id}: {e}"
            )
            return None

    def add_eval_case(self, app_name: str, eval_set_id: str, eval_case: EvalCase):
        raise NotImplementedError(
            "FirestoreEvalSetsManager is read-only. "
            "Add fixtures via the admin UI BusinessBrowser."
        )

    def update_eval_case(
        self, app_name: str, eval_set_id: str, updated_eval_case: EvalCase
    ):
        raise NotImplementedError(
            "FirestoreEvalSetsManager is read-only. "
            "Update fixtures via the admin UI or Firestore console."
        )

    def delete_eval_case(self, app_name: str, eval_set_id: str, eval_case_id: str):
        """Delete a fixture from Firestore by document ID."""
        db = get_db()
        try:
            db.collection(_COLLECTION).document(eval_case_id).delete()
            logger.info(
                f"[FirestoreEvalSetsManager] Deleted eval case {eval_case_id} "
                f"from {eval_set_id}"
            )
        except Exception as e:
            logger.error(
                f"[FirestoreEvalSetsManager] Failed to delete eval case {eval_case_id}: {e}"
            )
            raise
