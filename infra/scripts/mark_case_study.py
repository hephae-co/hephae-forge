#!/usr/bin/env python3
"""
Mark a business as a case study (add isCaseStudy flag to Firestore).

Usage:
    python3 infra/scripts/mark_case_study.py meal-nj-07110-07110

Or programmatically:
    from hephae_db.firestore.case_studies import mark_case_study
    import asyncio
    asyncio.run(mark_case_study("meal-nj-07110-07110", "2026-03-29T..."))
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hephae_db.firestore.case_studies import _mark_case_study_sync


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 infra/scripts/mark_case_study.py <slug> [published_at]")
        print("\nExample:")
        print("  python3 infra/scripts/mark_case_study.py meal-nj-07110-07110")
        print("  python3 infra/scripts/mark_case_study.py meal-nj-07110-07110 2026-03-29T12:00:00Z")
        sys.exit(1)

    slug = sys.argv[1]
    published_at = sys.argv[2] if len(sys.argv) > 2 else datetime.utcnow().isoformat() + "Z"

    print(f"Marking {slug} as case study...")
    print(f"  Published at: {published_at}")

    _mark_case_study_sync(slug, published_at, status="published")

    print("✓ Done! Case study is now published.")
    print(f"\nView at: https://hephae.co/case-studies/{slug}")


if __name__ == "__main__":
    main()
