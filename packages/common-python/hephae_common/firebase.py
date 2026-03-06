"""
Firebase Admin SDK initialization — singleton pattern.

Provides lazy-initialized Firestore client and optional GCS bucket.
Both web/ and admin/ import from here.
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage

from hephae_common.model_config import StorageConfig

_PROJECT_ID = "hephae-co-dev"
_app = None
_db = None
_bucket = None


def _init_app():
    global _app
    if _app is None:
        if not firebase_admin._apps:
            try:
                _app = firebase_admin.initialize_app(
                    credentials.ApplicationDefault(),
                    {
                        "projectId": _PROJECT_ID,
                        "storageBucket": StorageConfig.BUCKET,
                    },
                )
                print("[Firebase] Admin SDK initialized correctly.")
            except Exception as e:
                print(f"[Firebase] Error initializing Admin SDK: {e}")
                raise
        else:
            _app = firebase_admin.get_app()
    return _app


def get_db() -> firestore.firestore.Client:
    """Return the singleton Firestore client, initializing on first call."""
    global _db
    if _db is None:
        _init_app()
        _db = firestore.client()
    return _db


def get_bucket():
    """Return the singleton GCS bucket, initializing on first call."""
    global _bucket
    if _bucket is None:
        _init_app()
        _bucket = storage.bucket(StorageConfig.BUCKET)
    return _bucket
