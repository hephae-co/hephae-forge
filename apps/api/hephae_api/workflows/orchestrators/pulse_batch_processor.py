"""Pulse batch processor — 5-stage Vertex AI batch pipeline for county-level pulse generation.

Stages:
  0. Data Fetch (Python, no LLM) — fetch all signals per zip with cache-through
  1. Research Batch (Vertex Batch Job #1) — social_pulse + local_catalyst per zip
  2. Pre-Synthesis Batch (Vertex Batch Job #2) — historian + economist + scout per zip
  3. Synthesis Batch (Vertex Batch Job #3) — WeeklyPulseAgent per zip
  4. Critique Batch (Vertex Batch Job #4) — critique per zip
  4b. Rewrite Batch (conditional) — rewrite failed zips

Entry point: run_pulse_batch(batch_id) — called from Cloud Run Job.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


async def run_pulse_batch(batch_id: str) -> dict[str, Any]:
    """Execute the full 5-stage batch pipeline for a pulse batch.

    Args:
        batch_id: The batch ID (e.g., "pulse-essex-2026-W12").

    Returns:
        Summary dict with completion stats.
    """
    from hephae_db.firestore.pulse_batch import (
        get_all_work_items,
        get_batch_summary,
        update_work_item,
    )
    from hephae_db.firestore.weekly_pulse import save_weekly_pulse
    from hephae_db.firestore.signal_archive import save_signal_archive

    logger.info(f"[PulseBatch] Starting batch {batch_id}")
    started_at = datetime.utcnow()

    # Load all work items
    items = await get_all_work_items(batch_id)
    if not items:
        logger.warning(f"[PulseBatch] No work items found for {batch_id}")
        return {"batchId": batch_id, "error": "No work items found"}

    logger.info(f"[PulseBatch] Processing {len(items)} work items")

    # ── Stage 0: Data Fetch (Python, no LLM) ─────────────────────────
    await _stage0_fetch(batch_id, items)

    # Reload items with fetched data
    items = await get_all_work_items(batch_id)
    fetched = [i for i in items if i.get("status") != "FAILED"]

    if not fetched:
        logger.error(f"[PulseBatch] All items failed at fetch stage")
        return await get_batch_summary(batch_id)

    # ── Stage 1: Research Batch (social_pulse + local_catalyst) ───────
    await _stage1_research(batch_id, fetched)

    # ── Stage 2: Pre-Synthesis Batch (historian + economist + scout) ──
    items = await get_all_work_items(batch_id)
    active = [i for i in items if i.get("status") not in ("FAILED", "COMPLETED")]
    await _stage2_pre_synthesis(batch_id, active)

    # ── Stage 3: Synthesis Batch ──────────────────────────────────────
    items = await get_all_work_items(batch_id)
    active = [i for i in items if i.get("status") not in ("FAILED", "COMPLETED")]
    await _stage3_synthesis(batch_id, active)

    # ── Stage 4: Critique Batch ───────────────────────────────────────
    items = await get_all_work_items(batch_id)
    active = [i for i in items if i.get("status") not in ("FAILED", "COMPLETED")]
    await _stage4_critique(batch_id, active)

    # ── Save completed pulses ─────────────────────────────────────────
    items = await get_all_work_items(batch_id)
    saved = 0
    for item in items:
        if item.get("status") == "COMPLETED" and item.get("synthesisOutput"):
            try:
                pulse_id = await save_weekly_pulse(
                    zip_code=item["zipCode"],
                    business_type=item["businessType"],
                    week_of=item["weekOf"],
                    pulse=item["synthesisOutput"],
                    signals_used=list((item.get("rawSignals") or {}).keys()),
                    diagnostics={
                        "batchId": batch_id,
                        "critiquePass": item.get("critiqueResult", {}).get("overall_pass", False),
                        "pipeline": "vertex_batch_v1",
                    },
                )
                # Archive signals
                if item.get("rawSignals"):
                    archive = {
                        k: {"raw": v, "fetchedAt": datetime.utcnow().isoformat(), "version": "v1"}
                        for k, v in item["rawSignals"].items() if v
                    }
                    await save_signal_archive(
                        item["zipCode"], item["weekOf"], archive,
                        item.get("preComputedImpact"),
                    )
                saved += 1
            except Exception as e:
                logger.error(f"[PulseBatch] Failed to save pulse for {item['zipCode']}: {e}")

    elapsed = (datetime.utcnow() - started_at).total_seconds()
    summary = await get_batch_summary(batch_id)
    summary["savedPulses"] = saved
    summary["elapsedSeconds"] = round(elapsed, 1)

    logger.info(
        f"[PulseBatch] Batch {batch_id} complete: {saved}/{len(items)} saved, "
        f"{elapsed:.0f}s elapsed"
    )
    return summary


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


async def _stage0_fetch(batch_id: str, items: list[dict[str, Any]]) -> None:
    """Stage 0: Fetch all signals for each zip code."""
    from hephae_db.firestore.pulse_batch import update_work_item
    from hephae_db.bigquery.public_data import resolve_zip_geography
    from hephae_api.workflows.orchestrators.pulse_fetch_tools import fetch_all_signals
    from hephae_api.workflows.orchestrators.pulse_playbooks import (
        compute_impact_multipliers,
        match_playbooks,
    )

    STATE_TO_DMA = {
        "NJ": "New York", "NY": "New York", "CT": "New York",
        "PA": "Philadelphia", "DE": "Philadelphia",
        "CA": "Los Angeles", "IL": "Chicago", "TX": "Dallas",
        "MA": "Boston", "FL": "Miami", "GA": "Atlanta",
        "WA": "Seattle", "CO": "Denver", "AZ": "Phoenix",
        "DC": "Washington", "MD": "Washington", "VA": "Washington",
    }

    logger.info(f"[PulseBatch] Stage 0: Fetching signals for {len(items)} zips")

    for item in items:
        zip_code = item["zipCode"]
        business_type = item["businessType"]
        try:
            await update_work_item(batch_id, zip_code, {"status": "FETCHING"})

            # Resolve geography
            geo = await resolve_zip_geography(zip_code)
            city = geo.city if geo else ""
            state = geo.state_code if geo else ""
            county = geo.county if geo else ""
            lat = geo.latitude if geo else 0.0
            lon = geo.longitude if geo else 0.0
            dma = STATE_TO_DMA.get(state, "")

            signals = await fetch_all_signals(
                zip_code, business_type, city, state, county, lat, lon, dma,
            )

            pre_computed = compute_impact_multipliers(signals)
            playbooks = match_playbooks(pre_computed, signals, business_type)

            await update_work_item(batch_id, zip_code, {
                "status": "RESEARCH",
                "rawSignals": signals,
                "preComputedImpact": pre_computed,
                "matchedPlaybooks": playbooks,
                "geo": {"city": city, "state": state, "county": county, "dma": dma},
            })
        except Exception as e:
            logger.error(f"[PulseBatch] Stage 0 failed for {zip_code}: {e}")
            await update_work_item(batch_id, zip_code, {
                "status": "FAILED",
                "lastError": str(e),
            })


async def _stage1_research(batch_id: str, items: list[dict[str, Any]]) -> None:
    """Stage 1: Run social_pulse + local_catalyst via Vertex batch."""
    from hephae_common.gemini_batch import submit_vertex_batch, batch_generate
    from hephae_db.firestore.pulse_batch import update_work_item
    from hephae_agents.research.social_pulse import SOCIAL_PULSE_INSTRUCTION
    from hephae_agents.research.local_catalyst import LOCAL_CATALYST_INSTRUCTION

    logger.info(f"[PulseBatch] Stage 1: Research batch for {len(items)} zips")

    requests: list[dict[str, Any]] = []
    for item in items:
        zip_code = item["zipCode"]
        biz = item["businessType"]
        geo = item.get("geo", {})
        city = geo.get("city", "")
        state = geo.get("state", "")

        # Social pulse prompt
        requests.append({
            "request_id": f"{batch_id}:{zip_code}:social_pulse",
            "contents": [{"role": "user", "parts": [{"text": (
                f"{SOCIAL_PULSE_INSTRUCTION}\n\n"
                f"TOWN/CITY: {city}\nSTATE: {state}\nZIP CODE: {zip_code}\n"
                f"CURRENT DATE: {datetime.utcnow().strftime('%Y-%m-%d')}"
            )}]}],
            "tools": [{"google_search_retrieval": {
                "dynamic_retrieval_config": {"mode": "MODE_DYNAMIC"},
            }}],
        })

        # Local catalyst prompt
        requests.append({
            "request_id": f"{batch_id}:{zip_code}:local_catalyst",
            "contents": [{"role": "user", "parts": [{"text": (
                f"{LOCAL_CATALYST_INSTRUCTION}\n\n"
                f"TOWN/CITY: {city}\nSTATE: {state}\nBUSINESS TYPE: {biz}\n"
                f"CURRENT DATE: {datetime.utcnow().strftime('%Y-%m-%d')}"
            )}]}],
            "tools": [{"google_search_retrieval": {
                "dynamic_retrieval_config": {"mode": "MODE_DYNAMIC"},
            }}],
        })

    # Submit batch
    if len(requests) > 50:
        results = await submit_vertex_batch(requests, timeout_seconds=600)
    else:
        # Convert to batch_generate format
        prompts = [
            {"request_id": r["request_id"], "prompt": r["contents"][0]["parts"][0]["text"]}
            for r in requests
        ]
        results = await batch_generate(prompts, timeout_seconds=300)

    if not results:
        logger.warning("[PulseBatch] Stage 1 batch returned no results")
        return

    # Map results back to work items
    for item in items:
        zip_code = item["zipCode"]
        social_key = f"{batch_id}:{zip_code}:social_pulse"
        catalyst_key = f"{batch_id}:{zip_code}:local_catalyst"

        updates: dict[str, Any] = {"status": "PRE_SYNTHESIS"}
        if social_key in results and results[social_key]:
            r = results[social_key]
            updates["socialPulse"] = r.get("raw_text", json.dumps(r)) if isinstance(r, dict) else str(r)
        if catalyst_key in results and results[catalyst_key]:
            r = results[catalyst_key]
            updates["localCatalysts"] = r.get("raw_text", json.dumps(r)) if isinstance(r, dict) else str(r)

        await update_work_item(batch_id, zip_code, updates)


async def _stage2_pre_synthesis(batch_id: str, items: list[dict[str, Any]]) -> None:
    """Stage 2: Run historian + economist + scout via Vertex batch."""
    from hephae_common.gemini_batch import submit_vertex_batch, batch_generate
    from hephae_db.firestore.pulse_batch import update_work_item

    logger.info(f"[PulseBatch] Stage 2: Pre-synthesis for {len(items)} zips")

    requests: list[dict[str, Any]] = []
    for item in items:
        zip_code = item["zipCode"]
        biz = item["businessType"]
        signals = item.get("rawSignals", {})
        pre_computed = item.get("preComputedImpact", {})
        geo = item.get("geo", {})

        # Economist prompt
        econ_data = json.dumps({
            k: signals.get(k) for k in [
                "blsCpi", "priceDeltas", "censusDemographics", "irsIncome",
                "sbaLoans", "qcewEmployment", "housePriceIndex", "healthMetrics", "trends"
            ] if signals.get(k)
        }, default=str)[:4000]

        requests.append({
            "request_id": f"{batch_id}:{zip_code}:economist",
            "contents": [{"role": "user", "parts": [{"text": (
                f"You are a Local Business Economist for {biz} in zip {zip_code}.\n"
                f"Produce a macro report covering price pressure, spending power, labor market, demand signals.\n\n"
                f"ECONOMIC DATA:\n{econ_data}\n\n"
                f"PRE-COMPUTED IMPACT:\n{json.dumps(pre_computed, default=str)}"
            )}]}],
        })

        # Local scout prompt
        local_data = json.dumps({
            k: signals.get(k) for k in [
                "weather", "weatherHistory", "localNews", "legalNotices"
            ] if signals.get(k)
        }, default=str)[:3000]
        social = item.get("socialPulse", "")
        catalysts = item.get("localCatalysts", "")

        requests.append({
            "request_id": f"{batch_id}:{zip_code}:local_scout",
            "contents": [{"role": "user", "parts": [{"text": (
                f"You are a Local Scout for {biz} in {geo.get('city', '')}, {geo.get('state', '')} ({zip_code}).\n"
                f"Produce a local report covering weather, events, community sentiment, news.\n\n"
                f"LOCAL DATA:\n{local_data}\n\n"
                f"SOCIAL PULSE:\n{social[:1500] if social else 'N/A'}\n\n"
                f"LOCAL CATALYSTS:\n{catalysts[:1500] if catalysts else 'N/A'}"
            )}]}],
        })

        # Historian prompt (lightweight — just summarize past insights)
        requests.append({
            "request_id": f"{batch_id}:{zip_code}:historian",
            "contents": [{"role": "user", "parts": [{"text": (
                f"You are a Trend Historian for {biz} in zip {zip_code}.\n"
                f"This is a batch run — no historical pulse data is available.\n"
                f"Respond briefly: 'No historical data available for trend analysis. "
                f"This is a baseline pulse generation.'"
            )}]}],
        })

    if len(requests) > 50:
        results = await submit_vertex_batch(requests, timeout_seconds=600)
    else:
        prompts = [
            {"request_id": r["request_id"], "prompt": r["contents"][0]["parts"][0]["text"]}
            for r in requests
        ]
        results = await batch_generate(prompts, timeout_seconds=300)

    if not results:
        logger.warning("[PulseBatch] Stage 2 batch returned no results")
        return

    for item in items:
        zip_code = item["zipCode"]
        updates: dict[str, Any] = {"status": "SYNTHESIS"}

        for stage_name, key in [("economist", "macroReport"), ("local_scout", "localReport"), ("historian", "trendNarrative")]:
            req_id = f"{batch_id}:{zip_code}:{stage_name}"
            if req_id in results and results[req_id]:
                r = results[req_id]
                updates[key] = r.get("raw_text", json.dumps(r)) if isinstance(r, dict) else str(r)

        await update_work_item(batch_id, zip_code, updates)


async def _stage3_synthesis(batch_id: str, items: list[dict[str, Any]]) -> None:
    """Stage 3: Run synthesis via Vertex batch."""
    from hephae_common.gemini_batch import submit_vertex_batch, batch_generate
    from hephae_db.firestore.pulse_batch import update_work_item
    from hephae_db.schemas import WeeklyPulseOutput

    logger.info(f"[PulseBatch] Stage 3: Synthesis for {len(items)} zips")

    # Build JSON schema from Pydantic model for Vertex batch response_schema
    response_schema = WeeklyPulseOutput.model_json_schema()

    requests: list[dict[str, Any]] = []
    for item in items:
        zip_code = item["zipCode"]
        biz = item["businessType"]
        week_of = item["weekOf"]
        pre_computed = item.get("preComputedImpact", {})
        playbooks = item.get("matchedPlaybooks", [])

        macro = item.get("macroReport", "No macro report available.")
        local = item.get("localReport", "No local report available.")
        trend = item.get("trendNarrative", "No trend data available.")

        playbook_text = ""
        if playbooks:
            playbook_text = "\n".join(f"- [{pb['name']}] ({pb['category']}): {pb['play']}" for pb in playbooks)

        prompt = (
            f"ZIP CODE: {zip_code}\nBUSINESS TYPE: {biz}\nWEEK OF: {week_of}\n\n"
            f"=== ECONOMIST REPORT ===\n{macro[:2000]}\n\n"
            f"=== LOCAL SCOUT REPORT ===\n{local[:2000]}\n\n"
            f"=== TREND NARRATIVE ===\n{trend[:1000]}\n\n"
            f"=== PRE-COMPUTED IMPACT ===\n{json.dumps(pre_computed, default=str)}\n\n"
        )
        if playbook_text:
            prompt += f"=== MATCHED PLAYBOOKS ===\n{playbook_text}\n\n"

        prompt += (
            "Generate 3-5 ranked insight cards. Each must cite 2+ data sources. "
            "Use pre-computed numbers as facts. Be specific and actionable."
        )

        requests.append({
            "request_id": f"{batch_id}:{zip_code}:synthesis",
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "config": {
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            },
        })

    if len(requests) > 50:
        results = await submit_vertex_batch(requests, timeout_seconds=600)
    else:
        prompts = [
            {"request_id": r["request_id"], "prompt": r["contents"][0]["parts"][0]["text"]}
            for r in requests
        ]
        results = await batch_generate(prompts, timeout_seconds=300)

    if not results:
        logger.warning("[PulseBatch] Stage 3 batch returned no results")
        return

    for item in items:
        zip_code = item["zipCode"]
        req_id = f"{batch_id}:{zip_code}:synthesis"
        if req_id in results and results[req_id]:
            await update_work_item(batch_id, zip_code, {
                "status": "CRITIQUE",
                "synthesisOutput": results[req_id],
            })
        else:
            await update_work_item(batch_id, zip_code, {
                "status": "FAILED",
                "lastError": "Synthesis returned no output",
            })


async def _stage4_critique(batch_id: str, items: list[dict[str, Any]]) -> None:
    """Stage 4: Run critique + optional rewrite via batch."""
    from hephae_common.gemini_batch import submit_vertex_batch, batch_generate
    from hephae_db.firestore.pulse_batch import update_work_item

    logger.info(f"[PulseBatch] Stage 4: Critique for {len(items)} zips")

    requests: list[dict[str, Any]] = []
    for item in items:
        zip_code = item["zipCode"]
        synthesis = item.get("synthesisOutput", {})
        synthesis_text = json.dumps(synthesis, default=str)[:4000]

        prompt = (
            "You are a Cynical Local Business Owner. Review each insight:\n"
            "Test 1: Walking Down the Street (obviousness, < 30 to pass)\n"
            "Test 2: So What? (actionability, >= 70 to pass)\n"
            "Test 3: Show Your Work (cross-signal, >= 60 to pass)\n\n"
            f"PULSE OUTPUT:\n{synthesis_text}\n\n"
            "Return JSON: {{\"overall_pass\": bool, \"insights\": ["
            "{{\"insight_rank\": int, \"obviousness_score\": int, "
            "\"actionability_score\": int, \"cross_signal_score\": int, "
            "\"verdict\": \"PASS\"|\"REWRITE\"|\"DROP\", \"rewrite_instruction\": str}}]}}"
        )

        requests.append({
            "request_id": f"{batch_id}:{zip_code}:critique",
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "config": {"response_mime_type": "application/json"},
        })

    if len(requests) > 50:
        results = await submit_vertex_batch(requests, timeout_seconds=600)
    else:
        prompts = [
            {"request_id": r["request_id"], "prompt": r["contents"][0]["parts"][0]["text"]}
            for r in requests
        ]
        results = await batch_generate(prompts, timeout_seconds=300)

    if not results:
        logger.warning("[PulseBatch] Stage 4 batch returned no results")
        # Mark all as completed without critique
        for item in items:
            await update_work_item(batch_id, item["zipCode"], {"status": "COMPLETED"})
        return

    # Process results — separate pass vs fail
    failed_items = []
    for item in items:
        zip_code = item["zipCode"]
        req_id = f"{batch_id}:{zip_code}:critique"
        critique = results.get(req_id)

        if not critique:
            await update_work_item(batch_id, zip_code, {"status": "COMPLETED"})
            continue

        if isinstance(critique, dict) and critique.get("overall_pass"):
            await update_work_item(batch_id, zip_code, {
                "status": "COMPLETED",
                "critiqueResult": critique,
            })
        else:
            failed_items.append((item, critique))
            await update_work_item(batch_id, zip_code, {"critiqueResult": critique})

    # Stage 4b: Rewrite batch for failed items
    if failed_items:
        await _stage4b_rewrite(batch_id, failed_items)


async def _stage4b_rewrite(
    batch_id: str,
    failed_items: list[tuple[dict[str, Any], Any]],
) -> None:
    """Stage 4b: Rewrite failed zips with critique feedback."""
    from hephae_common.gemini_batch import batch_generate
    from hephae_db.firestore.pulse_batch import update_work_item

    logger.info(f"[PulseBatch] Stage 4b: Rewriting {len(failed_items)} failed zips")

    prompts = []
    for item, critique in failed_items:
        zip_code = item["zipCode"]
        biz = item["businessType"]
        synthesis = item.get("synthesisOutput", {})
        macro = item.get("macroReport", "")
        local = item.get("localReport", "")
        pre_computed = item.get("preComputedImpact", {})

        # Build rewrite feedback from critique
        feedback_parts = []
        if isinstance(critique, dict):
            for ic in critique.get("insights", []):
                if ic.get("verdict") in ("REWRITE", "DROP"):
                    feedback_parts.append(
                        f"Insight #{ic.get('insight_rank', '?')}: {ic['verdict']} — "
                        f"{ic.get('rewrite_instruction', 'Improve quality')}"
                    )

        feedback = "\n".join(feedback_parts) or "Improve insight quality."

        prompt = (
            f"ZIP CODE: {zip_code}\nBUSINESS TYPE: {biz}\n\n"
            f"=== REWRITE MODE ===\n{feedback}\n\n"
            f"=== YOUR PREVIOUS OUTPUT ===\n{json.dumps(synthesis, default=str)[:2000]}\n\n"
            f"=== CONTEXT ===\n"
            f"Macro: {macro[:1000] if macro else 'N/A'}\n"
            f"Local: {local[:1000] if local else 'N/A'}\n"
            f"Impact: {json.dumps(pre_computed, default=str)}\n\n"
            f"Revise ONLY the failing insights. Keep passing ones unchanged."
        )

        prompts.append({"request_id": f"{batch_id}:{zip_code}:rewrite", "prompt": prompt})

    results = await batch_generate(prompts, timeout_seconds=180,
                                   config={"response_mime_type": "application/json"})

    for item, _ in failed_items:
        zip_code = item["zipCode"]
        req_id = f"{batch_id}:{zip_code}:rewrite"
        if req_id in results and results[req_id]:
            await update_work_item(batch_id, zip_code, {
                "status": "COMPLETED",
                "synthesisOutput": results[req_id],
            })
        else:
            # Mark as completed anyway — ship the original output
            await update_work_item(batch_id, zip_code, {"status": "COMPLETED"})
