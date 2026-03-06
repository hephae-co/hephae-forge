"""Firebase Admin SDK initialization — singleton Firestore client."""

import firebase_admin
from firebase_admin import credentials, firestore

_app = None
_db = None


def _init():
    global _app, _db
    if _app is None:
        try:
            _app = firebase_admin.initialize_app(
                credentials.ApplicationDefault(),
                {"projectId": "hephae-co"},
            )
            print("[Firebase] Admin SDK initialized correctly.")
        except Exception as e:
            print(f"[Firebase] Error initializing Admin SDK: {e}")
            raise
    if _db is None:
        _db = firestore.client()
    return _db


def get_db() -> firestore.firestore.Client:
    """Return the singleton Firestore client, initializing on first call."""
    return _init()
