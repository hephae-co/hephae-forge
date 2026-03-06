"""
Firebase Admin SDK initialization — singleton pattern.
Exports Firestore client (db) and GCS bucket (storage).
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage

from backend.config import StorageConfig

_PROJECT_ID = "hephae-co-dev"

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(
            credentials.ApplicationDefault(),
            {
                "projectId": _PROJECT_ID,
                "storageBucket": StorageConfig.BUCKET,
            },
        )
        print("[Firebase] Admin SDK Initialized correctly.")
    except Exception as e:
        print(f"[Firebase] Error initializing Admin SDK: {e}")

db = firestore.client()
gcs_bucket = storage.bucket(StorageConfig.BUCKET)
