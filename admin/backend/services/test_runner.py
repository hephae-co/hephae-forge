import httpx
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from backend.agents.evaluators.seo_evaluator import SeoEvaluatorAgent
from backend.agents.evaluators.traffic_evaluator import TrafficEvaluatorAgent
from backend.agents.evaluators.competitive_evaluator import CompetitiveEvaluatorAgent
from backend.config import settings
from backend.lib.forge_auth import forge_hmac_headers

class HephaeAdminRunner:
    def __init__(self):
        # In a real app, you'd load these from a file or DB
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

        # Simple extraction
        try:
            return json.loads(text_out.replace("```json", "").replace("```", "").strip())
        except:
            return {"score": 0, "isHallucinated": True, "issues": ["Failed to parse agent output"]}

    async def run_all_tests(self) -> Dict[str, Any]:
        print(f"Starting test suite targeting {settings.FORGE_URL}")
        results = []
        
        async with httpx.AsyncClient() as client:
            for biz in self.businesses:
                print(f"Testing business: {biz['name']}")
                
                # 1. SEO
                if biz.get("officialUrl"):
                    start = datetime.utcnow()
                    try:
                        res = await client.post(
                            f"{settings.FORGE_URL}/api/capabilities/seo",
                            json={"identity": biz},
                            timeout=60.0,
                            headers=forge_hmac_headers(),
                        )
                        output = res.json()
                        duration = (datetime.utcnow() - start).total_seconds() * 1000
                        
                        prompt = f"""TARGET_URL: {biz['officialUrl']}
ACTUAL_OUTPUT: {json.dumps(output)}"""
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
                    res = await client.post(
                        f"{settings.FORGE_URL}/api/capabilities/traffic",
                        json={"identity": biz},
                        timeout=60.0,
                        headers=forge_hmac_headers(),
                    )
                    output = res.json()
                    duration = (datetime.utcnow() - start).total_seconds() * 1000
                    
                    prompt = f"""BUSINESS_IDENTITY: {json.dumps(biz)}
ACTUAL_OUTPUT: {json.dumps(output)}"""
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

test_runner = HephaeAdminRunner()