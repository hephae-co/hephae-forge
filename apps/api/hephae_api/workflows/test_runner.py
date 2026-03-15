"""Test runner — runs all 4 capability runners + evaluators directly (no HTTP).

Covers: SEO, Traffic, Competitive Analysis, Margin Surgery.
Persists results to Firestore (test_runs collection, 7-day TTL).
Uses a dedicated test business identity to avoid polluting real data.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from google.adk import Runner
from google.adk.sessions import InMemorySessionService

from hephae_agents.evaluators.seo_evaluator import SeoEvaluatorAgent
from hephae_agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent
from hephae_agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent
from hephae_agents.evaluators.margin_surgeon_evaluator import MarginSurgeonEvaluatorAgent

logger = logging.getLogger(__name__)

# Dedicated test business — uses a real URL so SEO/discovery agents have something to crawl,
# but the identity is clearly marked as a test so it can be cleaned up.
TEST_BUSINESSES = [
    {
        "id": "qa-test-001",
        "name": "Test Biz",
        "officialUrl": "https://example.com",
        "address": "123 Test St, Anytown, NJ 07001",
        "zipCode": "07001",
        "competitors": [{"name": "Comp A", "url": "https://example.org"}],
        "menuUrl": None,
        "socialLinks": {},
    }
]


class HephaeTestRunner:
    def __init__(self):
        self.businesses = TEST_BUSINESSES

    async def evaluate_with_agent(self, agent, prompt: str) -> dict[str, Any]:
        """Run an evaluator agent and parse the JSON score output."""
        session_service = InMemorySessionService()
        runner = Runner(agent=agent, session_service=session_service, app_name="HephaeAdmin")

        session_id = f"eval-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        user_id = "qa-runner"
        await session_service.create_session(app_name="HephaeAdmin", session_id=session_id, user_id=user_id)

        text_out = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=prompt,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        text_out += part.text

        try:
            return json.loads(text_out.replace("```json", "").replace("```", "").strip())
        except Exception:
            return {"score": 0, "isHallucinated": True, "issues": ["Failed to parse evaluator output"]}

    def _make_result(self, capability: str, biz: dict, eval_data: dict, duration_ms: float) -> dict:
        return {
            "capability": capability,
            "businessId": biz["id"],
            "businessName": biz["name"],
            "score": eval_data.get("score", 0),
            "isHallucinated": eval_data.get("isHallucinated", False),
            "issues": eval_data.get("issues", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "responseTimeMs": round(duration_ms, 1),
        }

    async def _test_seo(self, biz: dict) -> dict | None:
        from hephae_agents.seo_auditor.runner import run_seo_audit

        if not biz.get("officialUrl"):
            return None
        start = datetime.now(timezone.utc)
        try:
            output = await run_seo_audit(biz)
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            prompt = f"TARGET_URL: {biz['officialUrl']}\nACTUAL_OUTPUT: {json.dumps(output)}"
            eval_data = await self.evaluate_with_agent(SeoEvaluatorAgent, prompt)
            return self._make_result("seo", biz, eval_data, duration)
        except Exception as e:
            logger.error(f"[QA] SEO test failed for {biz['name']}: {e}")
            return self._make_result("seo", biz, {"score": 0, "issues": [str(e)]}, 0)

    async def _test_traffic(self, biz: dict) -> dict | None:
        from hephae_agents.traffic_forecaster.runner import run_traffic_forecast

        start = datetime.now(timezone.utc)
        try:
            output = await run_traffic_forecast(biz)
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            prompt = f"BUSINESS_IDENTITY: {json.dumps(biz)}\nACTUAL_OUTPUT: {json.dumps(output)}"
            eval_data = await self.evaluate_with_agent(TrafficEvaluatorAgent, prompt)
            return self._make_result("traffic", biz, eval_data, duration)
        except Exception as e:
            logger.error(f"[QA] Traffic test failed for {biz['name']}: {e}")
            return self._make_result("traffic", biz, {"score": 0, "issues": [str(e)]}, 0)

    async def _test_competitive(self, biz: dict) -> dict | None:
        from hephae_agents.competitive_analysis.runner import run_competitive_analysis

        if not biz.get("competitors"):
            return None
        start = datetime.now(timezone.utc)
        try:
            output = await run_competitive_analysis(biz)
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            prompt = f"BUSINESS_IDENTITY: {json.dumps(biz)}\nACTUAL_OUTPUT: {json.dumps(output)}"
            eval_data = await self.evaluate_with_agent(CompetitiveEvaluatorAgent, prompt)
            return self._make_result("competitive", biz, eval_data, duration)
        except Exception as e:
            logger.error(f"[QA] Competitive test failed for {biz['name']}: {e}")
            return self._make_result("competitive", biz, {"score": 0, "issues": [str(e)]}, 0)

    async def _test_margin(self, biz: dict) -> dict | None:
        from hephae_agents.margin_analyzer.runner import run_margin_analysis

        start = datetime.now(timezone.utc)
        try:
            output = await run_margin_analysis(biz, advanced_mode=False)
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            prompt = f"BUSINESS_IDENTITY: {json.dumps(biz)}\nACTUAL_OUTPUT: {json.dumps(output)}"
            eval_data = await self.evaluate_with_agent(MarginSurgeonEvaluatorAgent, prompt)
            return self._make_result("margin", biz, eval_data, duration)
        except Exception as e:
            logger.error(f"[QA] Margin test failed for {biz['name']}: {e}")
            return self._make_result("margin", biz, {"score": 0, "issues": [str(e)]}, 0)

    async def run_all_tests(self) -> dict[str, Any]:
        """Run all 4 capabilities against test businesses and persist results."""
        logger.info("[QA] Starting full test suite (4 capabilities)")
        results: list[dict] = []

        for biz in self.businesses:
            logger.info(f"[QA] Testing: {biz['name']}")

            # Run all 4 capability tests
            seo_result = await self._test_seo(biz)
            traffic_result = await self._test_traffic(biz)
            competitive_result = await self._test_competitive(biz)
            margin_result = await self._test_margin(biz)

            for r in (seo_result, traffic_result, competitive_result, margin_result):
                if r is not None:
                    results.append(r)

        passed = [r for r in results if r["score"] >= 80 and not r["isHallucinated"]]

        summary = {
            "runId": f"run_{int(datetime.now(timezone.utc).timestamp())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "totalTests": len(results),
            "passedTests": len(passed),
            "failedTests": len(results) - len(passed),
            "results": results,
        }

        # Persist to Firestore (fire and forget — don't block response)
        try:
            from hephae_db.firestore.test_runs import save_test_run
            await save_test_run(summary)
        except Exception as e:
            logger.warning(f"[QA] Failed to persist test run: {e}")

        logger.info(f"[QA] Suite complete: {len(passed)}/{len(results)} passed")
        return summary


test_runner = HephaeTestRunner()
