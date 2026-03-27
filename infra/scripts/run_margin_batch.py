"""
Batch margin surgery runner — fetches 10 NJ restaurants and runs analysis.

Usage:
    cd /Users/sarthak/Desktop/hephae/hephae-forge
    pip install -e lib/common -e lib/db -e lib/integrations -e agents -e apps/api -q
    python infra/scripts/run_margin_batch.py

Output:
    - Console: per-restaurant summary table
    - File:    /tmp/margin_batch_results.json
    - Firestore: writes to margin_surgery_results/{slug} (if --save flag set)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Make sure local packages are importable
ROOT = Path(__file__).parent.parent.parent
for pkg in ["lib/common", "lib/db", "lib/integrations", "agents", "apps/api"]:
    p = str(ROOT / pkg)
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Target restaurants ────────────────────────────────────────────────────────
TARGET_SLUGS = [
    "460-bistro",
    "bucco-bloomfield",
    "italiana-by-zod",
    "llewellyn-parq-bar-and-grill",
    "montclair-house-grill",
    "popolari-pizza-pasta-bar",
    "stamna-taverna",
    "state-street-grill",
    "man-hing-restaurant",
    "cafe-by-us",
]


def _ev(f):
    """Recursive Firestore REST field extractor."""
    if not f:
        return None
    for k, v in f.items():
        if k == "stringValue":   return v
        if k == "integerValue":  return int(v)
        if k == "doubleValue":   return float(v)
        if k == "booleanValue":  return v
        if k == "nullValue":     return None
        if k == "timestampValue": return v
        if k == "mapValue":      return {kk: _ev(vv) for kk, vv in v.get("fields", {}).items()}
        if k == "arrayValue":    return [_ev(vv) for vv in v.get("values", [])]
    return None


def fetch_business(slug: str) -> dict | None:
    """Pull a business document from Firestore via REST API."""
    import urllib.request

    token = os.popen("gcloud auth print-access-token").read().strip()
    project = os.popen("gcloud config get-value project 2>/dev/null").read().strip()
    url = (
        f"https://firestore.googleapis.com/v1/projects/{project}"
        f"/databases/(default)/documents/businesses/{slug}"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        fields = {k: _ev(v) for k, v in data.get("fields", {}).items()}
        return fields
    except Exception as e:
        print(f"  [fetch] {slug}: {e}")
        return None


async def run_one(slug: str, fields: dict) -> dict:
    """Run margin surgery on a single restaurant."""
    from hephae_agents.margin_analyzer.runner import run_margin_analysis

    identity = fields.get("identity") or {}
    name = identity.get("name", slug)

    # Build minimal identity dict for the runner
    identity_input = {
        "name": name,
        "address": identity.get("address", ""),
        "menuUrl": identity.get("menuUrl", ""),
        "menuScreenshotBase64": identity.get("menuScreenshotBase64"),
        "competitors": identity.get("competitors") or [],
    }

    if not identity_input["menuUrl"] and not identity_input["menuScreenshotBase64"]:
        return {"slug": slug, "name": name, "error": "no_menu", "status": "skipped"}

    print(f"  [{slug}] Running surgery (menu: {identity_input['menuUrl'][:60]})...")
    t0 = time.time()

    try:
        result = await run_margin_analysis(
            identity=identity_input,
            business_context=None,
            advanced_mode=False,   # fast mode: cuisine estimates + real BLS commodity data
        )
        elapsed = round(time.time() - t0, 1)

        # Build summary
        menu_items = result.get("menu_items", [])
        advice = result.get("strategic_advice") or {}
        if isinstance(advice, list):
            recs = advice
            overall_health = "unknown"
            headline = ""
        else:
            recs = advice.get("recommendations", [])
            overall_health = advice.get("overall_health", "unknown")
            headline = advice.get("headline", "")

        # Find worst item
        critical_items = [i for i in menu_items if (i.get("food_cost_pct") or 0) >= 35]
        avg_food_cost = (
            round(sum(i.get("food_cost_pct") or 0 for i in menu_items) / len(menu_items), 1)
            if menu_items else 0
        )
        total_leakage = sum(i.get("price_leakage") or 0 for i in menu_items)

        return {
            "slug": slug,
            "name": name,
            "status": "ok",
            "elapsed_s": elapsed,
            "overall_score": result.get("overall_score"),
            "overall_health": overall_health,
            "headline": headline,
            "item_count": len(menu_items),
            "avg_food_cost_pct": avg_food_cost,
            "critical_items": len(critical_items),
            "total_leakage_per_menu": round(total_leakage, 2),
            "top_recommendations": recs[:3],
            "full_result": result,
        }

    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        print(f"  [{slug}] ERROR after {elapsed}s: {e}")
        import traceback
        return {
            "slug": slug,
            "name": name,
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_s": elapsed,
        }


def print_summary(results: list[dict]):
    """Print a formatted summary table."""
    print("\n" + "=" * 100)
    print(f"{'Restaurant':<35} {'Status':<8} {'Items':<6} {'Avg FC%':<8} {'Critical':<9} {'Leakage/Menu':<14} {'Health':<10} {'Time'}")
    print("-" * 100)
    for r in results:
        if r["status"] == "ok":
            print(
                f"{r['name'][:34]:<35} "
                f"{'OK':<8} "
                f"{r.get('item_count', 0):<6} "
                f"{r.get('avg_food_cost_pct', 0):<8.1f} "
                f"{r.get('critical_items', 0):<9} "
                f"${r.get('total_leakage_per_menu', 0):<13.2f} "
                f"{r.get('overall_health', 'unknown'):<10} "
                f"{r.get('elapsed_s', 0)}s"
            )
            if r.get("headline"):
                print(f"  → {r['headline']}")
            for rec in r.get("top_recommendations", [])[:2]:
                if isinstance(rec, dict):
                    print(f"    • {rec.get('title','')}: {rec.get('description','')[:80]}")
            print()
        else:
            print(f"{r['name'][:34]:<35} {'SKIP/ERR':<8} — {r.get('error','')[:60]}")
    print("=" * 100)


async def main():
    save_to_firestore = "--save" in sys.argv

    print(f"\nHephae Margin Surgery — Batch Run")
    print(f"Target: {len(TARGET_SLUGS)} restaurants")
    print(f"Mode: fast (cuisine-aware estimates + real BLS commodities)\n")

    # Fetch all business docs
    print("Fetching business documents from Firestore...")
    businesses = {}
    for slug in TARGET_SLUGS:
        fields = fetch_business(slug)
        if fields:
            businesses[slug] = fields
            identity = fields.get("identity") or {}
            print(f"  ✓ {identity.get('name', slug)}")
        else:
            print(f"  ✗ {slug} — not found")

    print(f"\nRunning surgery on {len(businesses)} restaurants...\n")

    # Run sequentially (Playwright screenshot + BLS calls; parallel causes rate limits)
    results = []
    for slug, fields in businesses.items():
        result = await run_one(slug, fields)
        results.append(result)

    # Print summary
    print_summary(results)

    # Save to file
    output_path = "/tmp/margin_batch_results.json"
    with open(output_path, "w") as f:
        # Don't serialize base64 screenshots
        def _clean(r):
            r = dict(r)
            if "full_result" in r:
                fr = dict(r["full_result"])
                if "identity" in fr:
                    identity = dict(fr["identity"])
                    identity.pop("menuScreenshotBase64", None)
                    fr["identity"] = identity
                r["full_result"] = fr
            return r
        json.dump([_clean(r) for r in results], f, indent=2, default=str)
    print(f"\nFull results saved to: {output_path}")

    # Optionally save to Firestore
    if save_to_firestore:
        print("\nSaving to Firestore margin_surgery_results/...")
        try:
            from hephae_common.firebase import get_db
            db = get_db()
            from datetime import datetime, timezone
            for r in results:
                if r["status"] == "ok":
                    doc_data = {
                        "slug": r["slug"],
                        "name": r["name"],
                        "overallScore": r.get("overall_score"),
                        "overallHealth": r.get("overall_health"),
                        "headline": r.get("headline"),
                        "avgFoodCostPct": r.get("avg_food_cost_pct"),
                        "criticalItems": r.get("critical_items"),
                        "itemCount": r.get("item_count"),
                        "recommendations": r.get("top_recommendations"),
                        "generatedAt": datetime.now(timezone.utc),
                    }
                    db.collection("margin_surgery_results").document(r["slug"]).set(doc_data)
                    print(f"  ✓ Saved {r['slug']}")
        except Exception as e:
            print(f"  Firestore save failed: {e}")

    # Stats
    ok = [r for r in results if r["status"] == "ok"]
    print(f"\nStats: {len(ok)}/{len(results)} succeeded")
    if ok:
        avg_fc = sum(r.get("avg_food_cost_pct", 0) for r in ok) / len(ok)
        total_critical = sum(r.get("critical_items", 0) for r in ok)
        print(f"Average food cost across all restaurants: {avg_fc:.1f}%")
        print(f"Total critical items (>35% food cost): {total_critical}")


if __name__ == "__main__":
    asyncio.run(main())
