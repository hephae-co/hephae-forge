"""
Backfill tech intelligence tool URLs — finds official product URLs for
aiOpportunities entries that are missing the `url` field, then patches
the Firestore documents in place.

Usage:
    cd /Users/sarthak/Desktop/hephae/hephae-forge
    source .venv/bin/activate
    python infra/scripts/backfill_tech_intel_urls.py
    python infra/scripts/backfill_tech_intel_urls.py --dry-run   # preview only, no writes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
for pkg in ["lib/common", "lib/db", "lib/integrations", "agents", "apps/api"]:
    p = str(ROOT / pkg)
    if p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL lookup via Gemini + Google Search grounding
# ---------------------------------------------------------------------------

async def _lookup_urls_for_tools(tools: list[dict], vertical: str) -> dict[str, str]:
    """
    Given a list of aiOpportunity dicts (with 'tool' field), return a mapping
    {tool_name: official_url} using Gemini with Google Search grounding.

    Batches all tools in a single LLM call to minimise API usage.
    """
    if not tools:
        return {}

    from google import genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)

    tool_names = [t["tool"] for t in tools if t.get("tool")]
    if not tool_names:
        return {}

    tool_list_str = "\n".join(f"- {name}" for name in tool_names)

    prompt = f"""For each software product listed below, provide the official product/landing-page URL.
These are technology tools used by {vertical} businesses.
Return ONLY a JSON object mapping tool name → URL. No extra text, no markdown fencing.
If you are not confident about a URL, use null.

Tools:
{tool_list_str}

Example output format:
{{"Toast POS": "https://pos.toasttab.com", "Square for Restaurants": "https://squareup.com/us/en/restaurants"}}
"""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            temperature=0,
        ),
    )

    raw = response.text.strip() if response.text else ""
    # Strip any accidental markdown fencing
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return {k: v for k, v in result.items() if isinstance(v, str) and v.startswith("http")}
    except json.JSONDecodeError:
        logger.warning(f"  Could not parse URL response for {vertical}: {raw[:200]}")

    return {}


# ---------------------------------------------------------------------------
# Main backfill logic
# ---------------------------------------------------------------------------

async def backfill(dry_run: bool = False) -> None:
    from hephae_common.firebase import get_db
    from hephae_db.firestore.tech_intelligence import list_tech_intelligence

    logger.info("Loading all tech_intelligence documents from Firestore…")
    docs = await list_tech_intelligence(vertical=None, limit=500)
    logger.info(f"Found {len(docs)} documents")

    db = get_db()
    total_tools_found = 0
    total_tools_updated = 0

    for doc in docs:
        doc_id = doc.get("id", "unknown")
        vertical = doc.get("vertical", "unknown")
        ai_opps: list[dict] = doc.get("aiOpportunities", [])

        if not ai_opps:
            logger.info(f"  {doc_id}: no aiOpportunities — skipping")
            continue

        missing = [o for o in ai_opps if isinstance(o, dict) and not o.get("url") and o.get("tool")]
        if not missing:
            logger.info(f"  {doc_id}: all {len(ai_opps)} tools already have URLs — skipping")
            continue

        logger.info(
            f"  {doc_id} ({vertical}): {len(missing)}/{len(ai_opps)} tools missing URLs — "
            f"looking up: {', '.join(o['tool'] for o in missing)}"
        )

        try:
            url_map = await _lookup_urls_for_tools(missing, vertical)
        except Exception as e:
            logger.error(f"  {doc_id}: URL lookup failed — {e}")
            continue

        if not url_map:
            logger.warning(f"  {doc_id}: no URLs found")
            continue

        logger.info(f"  {doc_id}: found {len(url_map)} URL(s):")
        for tool, url in url_map.items():
            logger.info(f"    {tool} → {url}")

        total_tools_found += len(url_map)

        # Patch the aiOpportunities array
        updated_opps = []
        changed = 0
        for opp in ai_opps:
            if isinstance(opp, dict):
                tool_name = opp.get("tool", "")
                if not opp.get("url") and tool_name in url_map:
                    opp = {**opp, "url": url_map[tool_name]}
                    changed += 1
            updated_opps.append(opp)

        if changed == 0:
            logger.info(f"  {doc_id}: no matching tools to patch")
            continue

        total_tools_updated += changed

        if dry_run:
            logger.info(f"  [DRY RUN] Would patch {doc_id} with {changed} URL(s)")
            continue

        # Write back to Firestore (update only the aiOpportunities field)
        try:
            ref = db.collection("tech_intelligence").document(doc_id)
            await asyncio.to_thread(ref.update, {"aiOpportunities": updated_opps})
            logger.info(f"  {doc_id}: patched {changed} URL(s) ✓")
        except Exception as e:
            logger.error(f"  {doc_id}: Firestore write failed — {e}")

    suffix = " (DRY RUN)" if dry_run else ""
    logger.info(
        f"\nDone{suffix}: {total_tools_found} URLs found, "
        f"{total_tools_updated} tool entries updated across {len(docs)} documents"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Backfill tech intelligence tool URLs")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Firestore",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode — no writes to Firestore")

    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
