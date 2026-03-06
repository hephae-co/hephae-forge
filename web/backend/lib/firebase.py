"""
Firebase Admin SDK — re-exports from hephae_common.

Existing code does `from backend.lib.firebase import db, gcs_bucket`.
This shim preserves that interface.
"""

from hephae_common.firebase import get_db, get_bucket

db = get_db()
gcs_bucket = get_bucket()
