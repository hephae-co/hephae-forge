"""Test runner — runs capability runners + evaluators directly (no HTTP)."""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from backend.workflows.agents.evaluators.seo_evaluator import SeoEvaluatorAgent
from backend.workflows.agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent
from backend.workflows.agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent


class HephaeTestRunner:
    def __init__(self):
        self.businesses = [
            {"id": "test-1", "name": "Test Biz", "officialUrl": "https://example.com", "competitors": [{"name": "Comp A"}]}
        ]

    async def evaluate_with_agent(self, agent, prompt: str):
        session_service = InMemorySessionService()
        runner = Runner(agent=agent, session_service=session_service, app_name="HephaeAdmin")

        session_id = f"eval-{int(datetime.utcnow().timestamp())}"
        user_id = "tester"
        await session_service.create_session(app_name="HephaeAdmin", session_id=session_id, user_id=user_id)

        text_out = ""
        async for event in runner.run_async(
            session_id=session_id,
            user_id=user_id,
            new_message=prompt
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        text_out += part.text

        try:
            return json.loads(text_out.replace("```json", "").replace("```", "").strip())
        except Exception:
            return {"score": 0, "isHallucinated": True, "issues": ["Failed to parse agent output"]}

    async def run_all_tests(self) -> Dict[str, Any]:
        from hephae_capabilities.seo_auditor.runner import run_seo_audit
        from hephae_capabilities.traffic_forecaster.runner import run_traffic_forecast

        print("Starting test suite (direct runner calls)")
        results = []

        for biz in self.businesses:
            print(f"Testing business: {biz['name']}")

            # 1. SEO
            if biz.get("officialUrl"):
                start = datetime.utcnow()
                try:
                    output = await run_seo_audit(biz)
                    duration = (datetime.utcnow() - start).total_seconds() * 1000

                    prompt = f"TARGET_URL: {biz['officialUrl']}\nACTUAL_OUTPUT: {json.dumps(output)}"
                    eval_data = await self.evaluate_with_agent(SeoEvaluatorAgent, prompt)

                    results.append({
                        "capability": "seo",
                        "businessId": biz["id"],
                        "businessName": biz["name"],
                        "score": eval_data.get("score", 0),
                        "isHallucinated": eval_data.get("isHallucinated", False),
                        "issues": eval_data.get("issues", []),
                        "timestamp": datetime.utcnow().isoformat(),
                        "responseTimeMs": duration
                    })
                except Exception as e:
                    print(f"SEO test failed for {biz['name']}: {str(e)}")

            # 2. Traffic
            start = datetime.utcnow()
            try:
                output = await run_traffic_forecast(biz)
                duration = (datetime.utcnow() - start).total_seconds() * 1000

                prompt = f"BUSINESS_IDENTITY: {json.dumps(biz)}\nACTUAL_OUTPUT: {json.dumps(output)}"
                eval_data = await self.evaluate_with_agent(TrafficEvaluatorAgent, prompt)

                results.append({
                    "capability": "traffic",
                    "businessId": biz["id"],
                    "businessName": biz["name"],
                    "score": eval_data.get("score", 0),
                    "isHallucinated": eval_data.get("isHallucinated", False),
                    "issues": eval_data.get("issues", []),
                    "timestamp": datetime.utcnow().isoformat(),
                    "responseTimeMs": duration
                })
            except Exception as e:
                print(f"Traffic test failed for {biz['name']}: {str(e)}")

        passed = [r for r in results if r["score"] >= 80 and not r["isHallucinated"]]

        summary = {
            "runId": f"run_{int(datetime.utcnow().timestamp())}",
            "timestamp": datetime.utcnow().isoformat(),
            "totalTests": len(results),
            "passedTests": len(passed),
            "failedTests": len(results) - len(passed),
            "results": results
        }

        return summary


test_runner = HephaeTestRunner()
